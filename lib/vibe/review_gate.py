"""Merge-bar counting for the required `review-gate` status (CITY-637).

A PR is mergeable when, on its current head SHA, either

* CodeRabbit's latest state-changing review is APPROVED, or
* at least ``REQUIRED_AGENT_REVIEWS`` distinct agent reviewers, none of them the
  PR's author, posted a ``pass`` or ``minor`` review,

and nothing blocks the head: any ``major`` (or invalid / edited agent review) on
the head blocks it until a new head is pushed. There are no risk tiers.

An agent review is a PR review (event COMMENT, pinned to the reviewed SHA) whose
LAST non-empty line is exactly

    <!-- city-agent-review v1 reviewer=<id> head=<sha> verdict=pass|minor|major -->

No markdown is parsed. If ``city-agent-review`` appears anywhere else in the body
(compared after NFKC normalization, case-insensitively), or the last line doesn't
parse, or the review was edited after posting (GitHub's edit history), the
review is invalid and blocks its head like a major: reviews must not quote
marker examples, and a verdict can't be changed by editing.

Distinct reviewers are distinct *roots*: an id and its subagents (``<id>/...``),
compared NFKC-normalized and case-folded, are one reviewer (latest review wins;
any major among them blocks).

The PR body names its authoring agent, whose reviews (and its subagents',
``<author>/...``, in any case) never count, on a line of its own (two different ids on such
lines fail the gate; ``bin/vibe pr`` adds it):

    <!-- city-author session=<id> -->

A pure rebase keeps its agent reviews (never CodeRabbit's) when a PR comment
line records it with full SHAs *and* the workflow verifies that both heads carry
the same patch (``scripts/review_gate.py``); an unverified carry is ignored:

    <!-- city-rebase-carry v1 from=<old-sha> to=<new-sha> -->

Agents all post as one GitHub account, so markers are trusted only from the
logins in ``TRUSTED_LOGINS`` (honor system).

Pure logic, stdlib only: ``scripts/review_gate.py`` fetches from GitHub and sets
the status. Tests: ``tests/test_review_gate.py``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

REQUIRED_AGENT_REVIEWS = 2
TRUSTED_LOGINS = frozenset({"kdenny"})
# The REST login of CodeRabbit's GitHub App. Bare `coderabbitai` is an
# organization, so it must never be trusted as CodeRabbit.
CODERABBIT_LOGINS = frozenset({"coderabbitai[bot]"})
VERDICTS = ("pass", "minor", "major")
STATUS_CONTEXT = "review-gate"

_SHA = r"[0-9a-f]{7,40}"
# Session / reviewer ids: rejects placeholders like "<id>".
_ID = r"[A-Za-z0-9][A-Za-z0-9._/-]*"
_AGENT_MARKER = re.compile(r"<!--\s*city-agent-review\s(.*?)-->")
_AGENT_KEYWORD = "city-agent-review"
_AUTHOR_MARKER = re.compile(rf"<!--\s*city-author\s+session=({_ID})\s*-->")
# Full SHAs only: the workflow fetches both commits to verify the rebase.
_CARRY_MARKER = re.compile(
    r"<!--\s*city-rebase-carry\s+v1\s+from=([0-9a-f]{40})\s+to=([0-9a-f]{40})\s*-->"
)
# CodeRabbit "COMMENTED" reviews don't change its approval state, same as GitHub.
_STATEFUL = frozenset({"APPROVED", "CHANGES_REQUESTED", "DISMISSED"})


# verify(old_sha, new_sha) -> None when the rebase is pure, else why it isn't.
CarryVerifier = Callable[[str, str], "str | None"]


@dataclass(frozen=True)
class Review:
    """A PR review (``kind="review"``) or a PR conversation comment (``kind="comment"``)."""

    id: int
    login: str
    body: str
    submitted_at: str  # ISO 8601; sorts chronologically as a string
    kind: str = "review"
    state: str = "COMMENTED"  # reviews only
    commit_id: str = ""  # reviews only
    #: Edited after posting (GitHub's ``lastEditedAt``), and the earlier versions'
    #: full text (``userContentEdits``). ``history_complete`` is False when GitHub
    #: didn't return every version; the gate then assumes the worst.
    edited: bool = False
    history: tuple[str, ...] = ()
    history_complete: bool = True


@dataclass(frozen=True)
class Marker:
    reviewer: str
    head: str
    verdict: str


@dataclass
class Line:
    """One row of the summary: a review that counted, or didn't and why."""

    source: str
    reviewer: str
    head: str
    verdict: str
    note: str


@dataclass
class GateResult:
    passed: bool
    head: str
    author: str | None
    coderabbit: bool
    agents: list[str]
    required: int = REQUIRED_AGENT_REVIEWS
    blockers: list[str] = field(default_factory=list)
    counted: list[Line] = field(default_factory=list)
    ignored: list[Line] = field(default_factory=list)

    def tally(self) -> str:
        cr = "CodeRabbit approved" if self.coderabbit else "CodeRabbit not approved"
        return f"{cr}, {len(self.agents)}/{self.required} agent reviews on head"

    def description(self) -> str:
        """Commit-status description (GitHub caps it at 140 chars)."""
        text = self.blockers[0] if self.blockers and not self.passed else self.tally()
        return text if len(text) <= 140 else text[:139] + "…"


def _normalized(text: str) -> str:
    """NFKC, case-folded, with invisible format characters (zero-width etc.) removed."""
    text = unicodedata.normalize("NFKC", text or "")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf").casefold()


def _full_lines(text: str, pattern: re.Pattern[str]) -> list[re.Match[str]]:
    """Lines that are, apart from surrounding whitespace, exactly one marker."""
    return [m for line in (text or "").splitlines() if (m := pattern.fullmatch(line.strip()))]


def _parse_one(raw: str) -> Marker | str:
    tokens = raw.split()
    if not tokens or tokens[0] != "v1":
        return f"unsupported marker version {tokens[0] if tokens else '(none)'!r}"
    fields: dict[str, str] = {}
    for tok in tokens[1:]:
        key, sep, value = tok.partition("=")
        if not sep or not value:
            return f"malformed marker field {tok!r}"
        if key not in ("reviewer", "head", "verdict"):
            return f"unknown marker field {key!r}"
        if key in fields:
            return f"duplicate marker field {key!r}"
        fields[key] = value
    missing = [k for k in ("reviewer", "head", "verdict") if k not in fields]
    if missing:
        return f"marker missing {', '.join(missing)}"
    if not re.fullmatch(_ID, fields["reviewer"]):
        return f"bad reviewer id {fields['reviewer']!r}"
    if not re.fullmatch(_SHA, fields["head"]):
        return f"bad head sha {fields['head']!r}"
    if fields["verdict"] not in VERDICTS:
        return f"bad verdict {fields['verdict']!r} (pass|minor|major)"
    return Marker(fields["reviewer"], fields["head"], fields["verdict"])


def _last_line_marker(body: str) -> Marker | None:
    """The marker on the last non-empty line, ignoring any other mentions."""
    lines = (body or "").rstrip().splitlines()
    m = _AGENT_MARKER.fullmatch(lines[-1].strip()) if lines else None
    parsed = _parse_one(m.group(1)) if m else None
    return parsed if isinstance(parsed, Marker) else None


def _ever_mentioned(r: Review) -> bool:
    """Did any version of ``r`` mention city-agent-review? Unknown history counts as yes."""
    if r.edited and not r.history_complete:
        return True
    return any(_AGENT_KEYWORD in _normalized(v) for v in (r.body, *r.history))


def parse_marker(body: str) -> Marker | str | None:
    """Read an agent review's verdict from its last non-empty line.

    None: the body never mentions ``city-agent-review`` (not a marker review).
    str: the review is invalid (why); it blocks its head like a major.
    Marker: the one valid marker, and the body mentions it nowhere else.
    """
    mentions = _normalized(body).count(_AGENT_KEYWORD)
    if mentions == 0:
        return None
    lines = (body or "").rstrip().splitlines()
    last = lines[-1].strip() if lines else ""
    m = _AGENT_MARKER.fullmatch(last)
    if m is None:
        return "invalid: the last line isn't a city-agent-review marker"
    if mentions > 1:
        return f"invalid: {mentions} city-agent-review mentions; only the last line may have one"
    parsed = _parse_one(m.group(1))
    return parsed if isinstance(parsed, Marker) else f"invalid: {parsed}"


def author_ids(pr_body: str) -> list[str]:
    """Distinct ids from standalone ``city-author`` marker lines, in order."""
    ids: list[str] = []
    for m in _full_lines(pr_body, _AUTHOR_MARKER):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def parse_author(pr_body: str) -> str | None:
    """The author session id, or None when there's none or the markers disagree."""
    ids = author_ids(pr_body)
    return ids[0] if len(ids) == 1 else None


def same_sha(a: str, b: str) -> bool:
    """True when one SHA is a prefix of the other (short SHAs are 7+ hex)."""
    a, b = a.lower(), b.lower()
    return len(a) >= 7 and len(b) >= 7 and (a.startswith(b) or b.startswith(a))


@dataclass(frozen=True)
class Carry:
    source: str
    old: str
    new: str


def parse_carries(items: list[Review]) -> list[Carry]:
    """Rebase-carry markers from trusted, non-dismissed PR comments and reviews."""
    out: list[Carry] = []
    for r in items:
        if r.login in TRUSTED_LOGINS and r.state != "DISMISSED":
            source = f"review {r.id}" if r.kind == "review" else f"comment {r.id}"
            out += [
                Carry(source, m.group(1), m.group(2)) for m in _full_lines(r.body, _CARRY_MARKER)
            ]
    return out


def equivalent_heads(
    head: str, carries: list[Carry], verify: CarryVerifier | None
) -> tuple[list[str], list[Line]]:
    """``head`` plus older heads carried onto it by *verified* pure rebases.

    ``verify(old, new)`` returns None when ``old`` and ``new`` carry the same
    change (see ``scripts/review_gate.py``), else the reason they don't. A carry
    nobody can verify (``verify`` is None) is never honored.
    """
    chain = [head]
    rejected: list[Line] = []
    checked: set[tuple[str, str]] = set()
    changed = True
    while changed:
        changed = False
        for c in carries:
            if (c.old, c.new) in checked or not any(same_sha(c.new, h) for h in chain):
                continue
            checked.add((c.old, c.new))
            if any(same_sha(c.old, h) for h in chain):
                continue
            reason = "can't verify a rebase carry here" if verify is None else verify(c.old, c.new)
            if reason:
                rejected.append(Line(c.source, "(rebase carry)", c.old[:7], "", reason))
                continue
            chain.append(c.old)
            changed = True
    return chain, rejected


def reviewer_root(reviewer: str) -> str:
    """The reviewing agent an id belongs to: ``x``, ``X`` and ``x/deep`` are all ``x``.

    ``<id>/<anything>`` is ``<id>``'s subagent, so distinctness and author
    exclusion compare roots, NFKC-normalized and case-folded.
    """
    return _normalized(reviewer).split("/", 1)[0]


def _is_reviewer_author(reviewer: str, author: str | None) -> bool:
    return author is not None and reviewer_root(reviewer) == reviewer_root(author)


def evaluate(
    *,
    head: str,
    pr_body: str,
    reviews: list[Review],
    comments: list[Review],
    verify_carry: CarryVerifier | None = None,
) -> GateResult:
    """Apply the merge bar to one PR. ``reviews``/``comments`` come straight from the API."""
    author = parse_author(pr_body)
    everything = sorted(reviews + comments, key=lambda r: (r.submitted_at, r.id))
    heads, rejected_carries = equivalent_heads(head, parse_carries(everything), verify_carry)
    result = GateResult(passed=False, head=head, author=author, coderabbit=False, agents=[])
    result.ignored += rejected_carries

    if author is None:
        ids = author_ids(pr_body)
        result.blockers.append(
            f"PR body has conflicting author markers ({', '.join(ids)}): keep exactly one"
            if ids
            else "PR body has no author marker: add a line <!-- city-author session=<id> -->"
        )

    def on_head(sha: str) -> bool:
        return any(same_sha(sha, h) for h in heads)

    # CodeRabbit: its latest state-changing review must be APPROVED on the head
    # itself. Its approval is never carried across a rebase.
    cr = [r for r in everything if r.kind == "review" and r.login in CODERABBIT_LOGINS]
    cr_state = [r for r in cr if r.state in _STATEFUL]
    if cr_state:
        last = cr_state[-1]
        sha = last.commit_id[:7]
        if last.state == "APPROVED" and same_sha(last.commit_id, head):
            result.coderabbit = True
            result.counted.append(Line("CodeRabbit", last.login, sha, "APPROVED", "on head"))
        elif last.state == "APPROVED":
            note = "approval is on an older head: comment `@coderabbitai review`"
            result.ignored.append(Line("CodeRabbit", last.login, sha, "APPROVED", note))
        else:
            note = (
                "not approved (agent reviews can still meet the bar)"
                if last.state == "CHANGES_REQUESTED"
                else "latest review was dismissed"
            )
            result.ignored.append(Line("CodeRabbit", last.login, sha, last.state, note))

    # Agent reviews on the head (or a verified carried head), grouped by reviewing
    # agent: an id and its subagents (`id/...`), in any case, are one reviewer.
    by_reviewer: dict[str, list[tuple[Review, Marker]]] = {}
    for r in everything:
        if r.login in CODERABBIT_LOGINS:
            continue
        source = f"review {r.id}" if r.kind == "review" else f"comment {r.id}"
        if r.login in TRUSTED_LOGINS and r.kind == "comment":
            # A major marker on the last line of any version of a PR comment that
            # names this head blocks it, even if the comment also quotes markers
            # or was edited since. Comments never count toward the bar.
            for version in (r.body, *r.history):
                m = _last_line_marker(version)
                if m and m.verdict == "major" and on_head(m.head):
                    result.blockers.append(
                        f"Major findings from {m.reviewer} on this head ({source})"
                    )
                    result.ignored.append(
                        Line(
                            source,
                            m.reviewer,
                            m.head[:7],
                            "major",
                            "major in a PR comment; blocks this head",
                        )
                    )
                    break
        if r.login in TRUSTED_LOGINS and r.kind == "review" and r.edited and _ever_mentioned(r):
            # A verdict can't be changed by editing: an edited marker review is
            # invalid, so it blocks the head it was posted on.
            row = Line(
                source, "(edited)", r.commit_id[:7], "", "invalid: review edited after posting"
            )
            if r.state != "DISMISSED" and on_head(r.commit_id):
                row.note += "; blocks this head (post a new review on a new head)"
                result.blockers.append(f"Edited agent review on this head ({source})")
            result.ignored.append(row)
            continue
        marker = parse_marker(r.body)
        if marker is None:
            continue
        if r.login not in TRUSTED_LOGINS:
            result.ignored.append(Line(source, r.login, "", "", "author isn't a trusted login"))
            continue
        if r.kind != "review":
            # Comments never count; a major in one was handled above.
            if not any(line.source == source for line in result.ignored):
                note = "PR comment, not a review: ignored"
                result.ignored.append(Line(source, "(comment)", "", "", note))
            continue
        if isinstance(marker, str):
            # Fail closed: a review that mentions the marker but isn't exactly one
            # valid last-line marker blocks the head it was posted on.
            row = Line(source, "(invalid)", r.commit_id[:7], "", marker)
            if r.state != "DISMISSED" and on_head(r.commit_id):
                row.note += "; blocks this head (fix: one marker, as the last line)"
                result.blockers.append(f"Invalid agent review on this head ({source})")
            result.ignored.append(row)
            continue
        row = Line(source, marker.reviewer, marker.head[:7], marker.verdict, "")
        if r.state == "DISMISSED":
            row.note = "review was dismissed"
        elif not same_sha(r.commit_id, marker.head):
            row.note = f"marker head doesn't match the review's commit {r.commit_id[:7]}"
        elif not on_head(marker.head):
            row.note = "stale: not the current head"
        elif _is_reviewer_author(marker.reviewer, author):
            row.note = "reviewer is the PR author"
        if row.note:
            # A major never goes unheard: from a trusted login and naming this
            # head, it blocks even with a mismatched commit or from the author.
            if marker.verdict == "major" and r.state != "DISMISSED" and on_head(marker.head):
                row.note += "; its major still blocks this head"
                result.blockers.append(
                    f"Major findings from {marker.reviewer} on this head ({source})"
                )
            result.ignored.append(row)
            continue
        by_reviewer.setdefault(reviewer_root(marker.reviewer), []).append((r, marker))

    # A major on the head blocks it for good: only a new head clears it, never a
    # later pass from the same reviewer or one of its subagents (fix, push, then
    # fresh reviews).
    for items in by_reviewer.values():
        majors = [m for _, m in items if m.verdict == "major"]
        if majors:
            for r, m in items:
                note = (
                    "major findings: fix, push, and get fresh reviews"
                    if m.verdict == "major"
                    else "this reviewer (or its subagent) posted a major on this head"
                )
                result.ignored.append(
                    Line(f"review {r.id}", m.reviewer, m.head[:7], m.verdict, note)
                )
            result.blockers.append(f"Major findings from {majors[0].reviewer} on this head")
            continue
        *earlier, (r, m) = items
        for er, em in earlier:
            note = f"same reviewer as {m.reviewer} (id/subagent/case): counted once (latest)"
            result.ignored.append(
                Line(f"review {er.id}", em.reviewer, em.head[:7], em.verdict, note)
            )
        note = "on head" if same_sha(m.head, head) else "on head (verified rebase carry-over)"
        result.counted.append(Line(f"review {r.id}", m.reviewer, m.head[:7], m.verdict, note))
        result.agents.append(m.reviewer)

    if not result.coderabbit and len(result.agents) < result.required:
        need = result.required - len(result.agents)
        result.blockers.append(
            f"{result.tally()}: need CodeRabbit approval or {need} more agent review"
            + ("s" if need > 1 else "")
        )
    result.passed = not result.blockers
    return result


def summary_markdown(result: GateResult) -> str:
    """Job summary: the policy, the outcome, what counted and what didn't."""
    policy = (
        "Mergeable when CodeRabbit's latest state-changing review is APPROVED on the current "
        f"head, **or** at least {result.required} distinct agent reviewers (not the PR author; an "
        "id and its `id/...` subagents, in any case, are one reviewer) posted `pass`/`minor` "
        "reviews on the current head. Agent reviews also count on a head "
        "carried over by a verified `city-rebase-carry`; CodeRabbit never carries. Any `major` "
        "(or an invalid or edited agent review) on the head blocks it until a new head."
    )
    out = [
        f"## {STATUS_CONTEXT}: {'✅ pass' if result.passed else '❌ fail'}",
        "",
        f"**Head:** `{result.head[:7]}` · **Author:** `{result.author or 'missing'}` · "
        f"**CodeRabbit:** {'approved' if result.coderabbit else 'not approved'} · "
        f"**Agent reviews:** {len(result.agents)}/{result.required}",
        "",
        f"**Policy:** {policy}",
        "",
    ]
    if result.blockers:
        out += ["### Blocking", ""] + [f"- {b}" for b in result.blockers] + [""]
    for title, rows in (("Counted", result.counted), ("Not counted", result.ignored)):
        out += [f"### {title}", ""]
        if not rows:
            out += ["None.", ""]
            continue
        out += ["| Source | Reviewer | Head | Verdict | Note |", "|---|---|---|---|---|"]
        out += [
            f"| {r.source} | `{r.reviewer}` | `{r.head}` | {r.verdict} | {r.note} |" for r in rows
        ]
        out.append("")
    return "\n".join(out)


def agent_marker(reviewer: str, head: str, verdict: str) -> str:
    """The marker line an agent review ends with."""
    if not re.fullmatch(_ID, reviewer):
        raise ValueError(f"bad reviewer id {reviewer!r} (letters, digits, then . _ / -)")
    marker = f"<!-- city-agent-review v1 reviewer={reviewer} head={head} verdict={verdict} -->"
    parsed = parse_marker(marker)
    if isinstance(parsed, str):
        raise ValueError(parsed)
    return marker


def author_marker(session: str) -> str:
    """The PR-body line naming the authoring session."""
    if not re.fullmatch(_ID, session):
        raise ValueError(f"bad session id {session!r}")
    return f"<!-- city-author session={session} -->"
