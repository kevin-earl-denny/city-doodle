"""CITY-637: table-driven tests for the review-gate merge bar (lib/vibe/review_gate.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.vibe.review_gate import (
    REQUIRED_AGENT_REVIEWS,
    Marker,
    Review,
    agent_marker,
    author_marker,
    evaluate,
    parse_marker,
    summary_markdown,
)

HEAD = "a" * 40
OLD = "b" * 40
OLDER = "c" * 40
AUTHOR = "city-doodle-7f"
BODY = f"Summary\n\n{author_marker(AUTHOR)}\n"
CR = "coderabbitai[bot]"

_ids = iter(range(1, 10_000))


def agent(reviewer: str, *, verdict: str = "pass", head: str = HEAD, commit: str | None = None,
          login: str = "kdenny", state: str = "COMMENTED", at: str = "2026-10-27T01:00:00Z",
          kind: str = "review") -> Review:  # fmt: skip
    body = (
        f"### Agent review @ {head[:7]}\n\nVerdict: CLEAN\n{agent_marker(reviewer, head, verdict)}"
    )
    return Review(
        id=next(_ids),
        login=login,
        body=body,
        submitted_at=at,
        kind=kind,
        state=state,
        commit_id=(commit or head) if kind == "review" else "",
    )


def coderabbit(state: str = "APPROVED", commit: str = HEAD, at: str = "2026-10-27T00:30:00Z"):
    return Review(id=next(_ids), login=CR, body="", submitted_at=at, state=state, commit_id=commit)


def comment(body: str, at: str = "2026-10-27T00:10:00Z", login: str = "kdenny") -> Review:
    return Review(id=next(_ids), login=login, body=body, submitted_at=at, kind="comment")


def run(reviews: list[Review], comments: list[Review] | None = None, body: str = BODY):
    return evaluate(head=HEAD, pr_body=body, reviews=reviews, comments=comments or [])


def agents(n: int) -> list[Review]:
    return [agent(f"city-doodle-b4/review-{i}") for i in range(n)]


# ── The merge bar: CodeRabbit approval, or 2 agent reviews ─────────────────


@pytest.mark.parametrize(
    ("with_cr", "n_agents", "passed"),
    [
        (True, 0, True),  # CodeRabbit APPROVED on head alone suffices
        (True, 1, True),
        (True, 2, True),
        (False, 2, True),  # 2 distinct agent reviews alone suffice
        (False, 3, True),
        (False, 1, False),
        (False, 0, False),
    ],
)
def test_merge_bar_by_path(with_cr: bool, n_agents: int, passed: bool) -> None:
    reviews = agents(n_agents) + ([coderabbit()] if with_cr else [])
    result = run(reviews)
    assert result.passed is passed
    assert result.required == REQUIRED_AGENT_REVIEWS == 2
    assert result.coderabbit is with_cr
    assert len(result.agents) == n_agents


def test_major_blocks_even_with_coderabbit_approval() -> None:
    result = run([coderabbit(), *agents(2), agent("rx", verdict="major")])
    assert result.coderabbit and not result.passed
    assert any("Major findings from rx" in b for b in result.blockers)


def test_coderabbit_changes_requested_does_not_block_two_agent_reviews() -> None:
    result = run([coderabbit("CHANGES_REQUESTED"), *agents(2)])
    assert result.passed and not result.coderabbit
    assert any(r.verdict == "CHANGES_REQUESTED" for r in result.ignored)


def test_fail_message_says_what_is_missing() -> None:
    result = run([agent("r1")])
    assert not result.passed
    assert result.blockers == [
        "CodeRabbit not approved, 1/2 agent reviews on head: "
        "need CodeRabbit approval or 1 more agent review"
    ]
    assert result.description() == result.blockers[0]
    assert run(agents(2)).description() == "CodeRabbit not approved, 2/2 agent reviews on head"


# ── Reviews that don't count ─────────────────────────────────────────────────


def test_major_not_counted_and_blocks() -> None:
    result = run(agents(2) + [agent("reviewer-x", verdict="major")])
    assert "reviewer-x" not in result.agents
    assert not result.passed
    assert any("Major findings from reviewer-x" in b for b in result.blockers)


@pytest.mark.parametrize(
    "misplaced",
    [
        agent("rx", verdict="major", kind="comment"),  # posted as a PR comment
        agent("rx", verdict="major", commit=OLD),  # marker head != review commit
        agent(AUTHOR, verdict="major"),  # the author flags its own PR
    ],
)
def test_misplaced_major_still_blocks(misplaced: Review) -> None:
    result = run([*agents(2), misplaced])
    assert not result.passed
    assert any(b.startswith("Major findings from") for b in result.blockers)


def test_misplaced_major_on_old_head_does_not_block() -> None:
    assert run([*agents(2), agent("rx", verdict="major", head=OLD, kind="comment")]).passed


def test_minor_counts() -> None:
    assert run([agent("r1", verdict="minor"), agent("r2")]).passed


def test_later_pass_from_same_reviewer_does_not_clear_its_major() -> None:
    reviews = [
        agent("r1", verdict="major", at="2026-10-27T01:00:00Z"),
        agent("r1", verdict="pass", at="2026-10-27T02:00:00Z"),
        agent("r2"),
        agent("r3"),
    ]
    result = run(reviews)
    assert not result.passed and sorted(result.agents) == ["r2", "r3"]
    assert any("Major findings from r1" in b for b in result.blockers)


def test_major_on_old_head_does_not_block_new_head() -> None:
    assert run([agent("r1", verdict="major", head=OLD), *agents(2)]).passed


def test_stale_head_not_counted() -> None:
    result = run([agent("r1"), agent("r2", head=OLD)])
    assert result.agents == ["r1"] and not result.passed
    assert any("stale" in r.note for r in result.ignored)


def test_duplicate_reviewer_counted_once() -> None:
    result = run([agent("r1"), agent("r1", at="2026-10-27T03:00:00Z")])
    assert result.agents == ["r1"] and not result.passed


@pytest.mark.parametrize("reviewer", [AUTHOR, f"{AUTHOR}/self-review"])
def test_author_and_its_subagents_not_counted(reviewer: str) -> None:
    result = run([agent("r1"), agent(reviewer)])
    assert reviewer not in result.agents and not result.passed


def test_author_prefix_is_not_a_substring_match() -> None:
    # city-doodle-7fx is a different session from city-doodle-7f.
    assert run([agent("r1"), agent(f"{AUTHOR}x")]).passed


def test_coderabbit_approval_on_old_head_not_counted() -> None:
    result = run([coderabbit(commit=OLD), agent("r1")])
    assert not result.coderabbit and not result.passed


def test_coderabbit_latest_state_wins_and_comments_dont_reset_it() -> None:
    approved_then_commented = [
        coderabbit("APPROVED", at="2026-10-27T00:30:00Z"),
        coderabbit("COMMENTED", at="2026-10-27T00:40:00Z"),
    ]
    assert run(approved_then_commented + [agent("r1")]).coderabbit
    approved_then_changes = [
        coderabbit("APPROVED", at="2026-10-27T00:30:00Z"),
        coderabbit("CHANGES_REQUESTED", at="2026-10-27T00:40:00Z"),
    ]
    assert not run(approved_then_changes + [agent("r1")]).coderabbit


def test_marker_head_must_match_review_commit() -> None:
    result = run([agent("r1"), agent("r2", head=HEAD, commit=OLD)])
    assert result.agents == ["r1"]
    assert any("doesn't match" in r.note for r in result.ignored)


def test_marker_in_plain_comment_not_counted() -> None:
    result = run([agent("r1"), agent("r2", kind="comment")])
    assert result.agents == ["r1"]


def test_untrusted_login_not_counted() -> None:
    result = run([agent("r1"), agent("r2", login="someone-else")])
    assert result.agents == ["r1"]


def test_dismissed_review_not_counted() -> None:
    result = run([agent("r1"), agent("r2", state="DISMISSED")])
    assert result.agents == ["r1"]


def test_short_sha_marker_counts() -> None:
    assert run([agent("r1", head=HEAD[:7]), agent("r2")]).passed


# ── The author marker ────────────────────────────────────────────────────────


def test_author_marker_inline_in_prose_does_not_count() -> None:
    body = "Docs: add `<!-- city-author session=someone -->` to the body."
    result = run(agents(2), body=body)
    assert result.author is None and not result.passed


def test_quoted_author_line_conflicts_and_fails_closed() -> None:
    # No markdown parsing: a quoted marker on its own line is a second author → fail.
    body = f"```\n<!-- city-author session=other -->\n```\n\n{author_marker(AUTHOR)}\n"
    result = run(agents(2), body=body)
    assert result.author is None and not result.passed
    assert any("conflicting author markers" in b for b in result.blockers)


def test_same_author_line_twice_is_fine() -> None:
    body = f"{author_marker(AUTHOR)}\n\n{author_marker(AUTHOR)}\n"
    assert run(agents(2), body=body).author == AUTHOR


def test_missing_author_marker_fails() -> None:
    result = run(agents(2), body="no marker here")
    assert not result.passed and result.author is None
    assert any("author marker" in b for b in result.blockers)


# ── Rebase carry-over ────────────────────────────────────────────────────────


def carry(old: str, new: str, at: str = "2026-10-27T05:00:00Z", login: str = "kdenny"):
    return comment(f"range-diff all `=`\n<!-- city-rebase-carry v1 from={old} to={new} -->", at, login)  # fmt: skip


def pure(old: str, new: str) -> str | None:
    return None


def run_carry(reviews, comments, verify=pure):
    return evaluate(
        head=HEAD, pr_body=BODY, reviews=reviews, comments=comments, verify_carry=verify
    )


def test_verified_carry_counts_old_head_agent_reviews_transitively() -> None:
    reviews = [agent("r1", head=OLDER), agent("r2", head=OLD), agent("r3")]
    result = run_carry(reviews, [carry(OLDER, OLD), carry(OLD, HEAD)])
    assert result.passed and sorted(result.agents) == ["r1", "r2", "r3"]


def test_coderabbit_approval_never_carries() -> None:
    result = run_carry([coderabbit(commit=OLD), agent("r1")], [carry(OLD, HEAD)])
    assert not result.coderabbit and not result.passed


def test_carry_rejected_by_verifier_is_ignored_with_reason() -> None:
    def changed(old: str, new: str) -> str:
        return "not a pure rebase: the patch differs between the two heads"

    result = run_carry([agent("r1", head=OLD), agent("r2")], [carry(OLD, HEAD)], verify=changed)
    assert result.agents == ["r2"]
    assert any("not a pure rebase" in r.note for r in result.ignored)


def test_carry_without_a_verifier_is_never_honored() -> None:
    result = run_carry([agent("r1", head=OLD), agent("r2")], [carry(OLD, HEAD)], verify=None)
    assert result.agents == ["r2"]
    assert any("can't verify" in r.note for r in result.ignored)


def test_major_on_carried_head_still_blocks() -> None:
    reviews = [agent("r1", head=OLD, verdict="major"), *agents(2)]
    assert not run_carry(reviews, [carry(OLD, HEAD)]).passed


def test_short_sha_carry_marker_is_not_parsed() -> None:
    result = run_carry([agent("r1", head=OLD), agent("r2")], [carry(OLD[:7], HEAD)])
    assert result.agents == ["r2"]


def test_rebase_carry_ignored_from_untrusted_login() -> None:
    result = run_carry([agent("r1", head=OLD), agent("r2")], [carry(OLD, HEAD, login="x")])
    assert result.agents == ["r2"]


def test_carry_from_unrelated_head_does_nothing() -> None:
    result = run_carry([agent("r1", head=OLDER), agent("r2")], [carry(OLDER, OLD)])
    assert result.agents == ["r2"]


# ── Marker grammar ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("<!-- city-agent-review v2 reviewer=a head=aaaaaaa verdict=pass -->", "version"),
        ("<!-- city-agent-review v1 reviewer=a head=aaaaaaa verdict=ok -->", "bad verdict"),
        ("<!-- city-agent-review v1 reviewer=a head=xyz verdict=pass -->", "bad head"),
        ("<!-- city-agent-review v1 reviewer=a head=aaaaaaa -->", "missing verdict"),
        ("<!-- city-agent-review v1 reviewer=a head=aaaaaaa verdict=pass x=1 -->", "unknown"),
    ],
)
def test_parse_marker_errors(body: str, error: str) -> None:
    out = parse_marker(body)
    assert isinstance(out, str) and error in out


MAJOR = "<!-- city-agent-review v1 reviewer=a head=aaaaaaa verdict=major -->"
PASS = "<!-- city-agent-review v1 reviewer=a head=aaaaaaa verdict=pass -->"


def test_body_without_the_keyword_is_not_a_marker_review() -> None:
    assert parse_marker("### Agent review\n\nVerdict: CLEAN") is None


def test_marker_must_be_the_last_non_empty_line() -> None:
    out = parse_marker(f"Review text\n\n{PASS}\n\n   \n")
    assert isinstance(out, Marker) and out.verdict == "pass"
    out = parse_marker(f"{PASS}\n\nVerdict: CLEAN")
    assert isinstance(out, str) and "last line" in out


@pytest.mark.parametrize(
    "body",
    [
        # Any second mention invalidates the review, however it's quoted.
        f"Grammar: `{PASS}`\n\n{PASS}",
        f"```\n{MAJOR}\n```\n\n{PASS}",
        f"- item\n  ```\n  {MAJOR}\n  ```\n\n{PASS}",  # fence opened in a list item
        f"```md\n```not-a-closer\n{MAJOR}\n```\n{PASS}",  # info-string "closer"
        f"    {MAJOR}\n\n{PASS}",  # indented code
        f"{MAJOR}\n{PASS}",  # last line pass, body has a major marker
        f"see CITY-AGENT-REVIEW docs\n{PASS}",  # case-insensitive
        f"\uff43\uff49\uff54\uff59-agent-review (fullwidth)\n{PASS}",  # NFKC
        f"city\u200b-agent-review (zero-width)\n{PASS}",  # invisible format chars
    ],
)
def test_any_other_mention_makes_the_review_invalid(body: str) -> None:
    out = parse_marker(body)
    assert isinstance(out, str) and out.startswith("invalid")


def test_invalid_review_on_head_blocks_like_a_major() -> None:
    bad = Review(
        id=999, login="kdenny", body=f"Example: `{PASS}`\n\n{agent_marker('rx', HEAD, 'pass')}",
        submitted_at="2026-10-27T03:00:00Z", commit_id=HEAD,
    )  # fmt: skip
    result = run([*agents(2), bad])
    assert not result.passed
    assert any("Invalid agent review" in b for b in result.blockers)


def test_invalid_review_on_old_head_does_not_block() -> None:
    bad = Review(
        id=998, login="kdenny", body=f"x `{PASS}`\n{PASS}", submitted_at="2026-10-27T03:00:00Z",
        commit_id=OLD,
    )  # fmt: skip
    assert run([*agents(2), bad]).passed


def test_pr_comments_quoting_markers_never_block() -> None:
    fix_map = comment(f"Fix map: reviews now end with `{MAJOR}`.")
    assert run(agents(2), [fix_map]).passed


def test_malformed_reviewer_id_outside_code_is_rejected() -> None:
    out = parse_marker("<!-- city-agent-review v1 reviewer=<id> head=aaaaaaa verdict=pass -->")
    assert isinstance(out, str) and "bad reviewer id" in out
    out = parse_marker("<!-- city-agent-review v1 reviewer=-x head=aaaaaaa verdict=pass -->")
    assert isinstance(out, str) and "bad reviewer id" in out


def test_conflicting_author_markers_fail() -> None:
    body = f"{author_marker(AUTHOR)}\n{author_marker('someone-else')}\n"
    result = run(agents(2), body=body)
    assert result.author is None and not result.passed
    assert any("conflicting author markers" in b for b in result.blockers)


def test_agent_marker_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        agent_marker("r1", HEAD, "clean")


def test_summary_lists_policy_counted_and_not_counted() -> None:
    result = run([agent("r1"), agent("r2", head=OLD)])
    text = summary_markdown(result)
    assert "Policy:" in text and "### Counted" in text and "### Not counted" in text
    assert "stale" in text and "1/2" in text


def test_status_description_fits_github_limit() -> None:
    result = run([], body="x" * 500)
    assert len(result.description()) <= 140


# ── Workflow wiring ──────────────────────────────────────────────────────────

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "review-gate.yml"


def test_workflow_never_runs_pr_code_and_holds_no_secrets() -> None:
    yaml = pytest.importorskip("yaml")
    text = WORKFLOW.read_text()
    doc = yaml.safe_load(text)
    on = doc.get("on", doc.get(True))
    # Base-side triggers only: pull_request / pull_request_review would run the PR's own gate.
    assert set(on) == {"pull_request_target", "issue_comment", "workflow_run"}
    assert {"opened", "synchronize", "ready_for_review", "edited"} <= set(
        on["pull_request_target"]["types"]
    )
    assert on["workflow_run"]["workflows"] == ["Review gate trigger"]
    group = doc["concurrency"]["group"]
    assert "workflow_run.pull_requests[0].number" in group  # same PR → same queue
    assert doc["concurrency"]["cancel-in-progress"] is False
    steps = doc["jobs"]["evaluate"]["steps"]
    checkout = next(s for s in steps if "actions/checkout" in s.get("uses", ""))
    assert "ref" not in checkout["with"], "checkout must stay on the base/default ref"
    assert checkout["with"]["persist-credentials"] is False
    for needle in ("secrets.", "head.ref", "refs/pull", "merge_commit_sha"):
        assert needle not in text, needle
    assert doc["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
        "issues": "read",
        "statuses": "write",
    }


def test_trigger_workflow_has_no_permissions_and_runs_nothing_from_the_pr() -> None:
    yaml = pytest.importorskip("yaml")
    trigger = WORKFLOW.with_name("review-gate-trigger.yml")
    doc = yaml.safe_load(trigger.read_text())
    on = doc.get("on", doc.get(True))
    assert doc["name"] == "Review gate trigger"
    assert {"submitted", "dismissed"} <= set(on["pull_request_review"]["types"])
    assert doc["permissions"] == {}
    steps = doc["jobs"]["relay"]["steps"]
    assert all("uses" not in s for s in steps)


# ── bin/vibe helpers ─────────────────────────────────────────────────────────


def test_review_marker_cli_round_trips() -> None:
    from click.testing import CliRunner

    from lib.vibe.cli.main import main

    out = CliRunner().invoke(
        main, ["review-marker", "--reviewer", "b4/r1", "--verdict", "minor", "--head", HEAD]
    )
    assert out.exit_code == 0
    marker = parse_marker(out.output)
    assert not isinstance(marker, str) and (marker.reviewer, marker.verdict) == ("b4/r1", "minor")
    bad = CliRunner().invoke(
        main, ["review-marker", "--reviewer", "b4", "--verdict", "pass", "--head", "zzz"]
    )
    assert bad.exit_code == 1


def test_workflows_pin_actions_by_sha_and_install_nothing() -> None:
    import re

    for path in (WORKFLOW, WORKFLOW.with_name("review-gate-trigger.yml")):
        text = path.read_text()
        for uses in re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", text, re.M):
            assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uses), uses
        # Stdlib only: the runner's python3, no setup-python / pip / uv.
        for needle in ("pip install", "setup-python", "uv "):
            assert needle not in text, (path.name, needle)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Summary", f"Summary\n\n{author_marker('s1')}\n"),
        ("", f"\n\n{author_marker('s1')}\n"),
        (f"Summary\n{author_marker('other')}\n", f"Summary\n{author_marker('other')}\n"),
    ],
)
def test_with_author_marker_appends_once(body: str, expected: str) -> None:
    from lib.vibe.cli.main import _with_author_marker

    assert _with_author_marker(body, "s1") == expected


def test_with_author_marker_rejects_placeholder_ids() -> None:
    from lib.vibe.cli.main import _with_author_marker

    with pytest.raises(ValueError):
        _with_author_marker("x", "<id>")


@pytest.mark.parametrize(
    ("author_args", "env", "expected"),
    [
        (["--author", "city-doodle-a1"], {}, "city-doodle-a1"),
        ([], {"CLAUDE_SESSION_NAME": "city-doodle-b2"}, "city-doodle-b2"),
        ([], {}, None),  # generated: pr-<8 hex>
    ],
)
def test_vibe_pr_adds_the_author_marker(
    monkeypatch: pytest.MonkeyPatch, author_args: list[str], env: dict, expected: str | None
) -> None:
    import re
    import subprocess
    from unittest.mock import patch

    from click.testing import CliRunner

    from lib.vibe.cli import main as cli
    from lib.vibe.review_gate import parse_author

    monkeypatch.delenv("CLAUDE_SESSION_NAME", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    calls: list[list[str]] = []

    def fake_run(args, **_kw):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="https://x/pull/1\n", stderr="")

    with (
        patch("lib.vibe.git.branches.get_main_branch", return_value="main"),
        patch("lib.vibe.git.branches.current_branch", return_value="CITY-637"),
        patch("lib.vibe.config.load_config", return_value={}),
        patch.object(cli, "_warn_duplicate_prs", return_value=True),
        patch.object(cli, "_autolink_pr_to_ticket"),
        patch("subprocess.run", side_effect=fake_run),
    ):
        out = CliRunner().invoke(cli.main, ["pr", "--title", "t", "--body", "Body", *author_args])
    assert out.exit_code == 0, out.output
    gh = calls[-1]
    body = gh[gh.index("--body") + 1]
    author = parse_author(body)
    assert body.startswith("Body\n\n") and body.rstrip().endswith("-->")
    if expected:
        assert author == expected
    else:
        assert author and re.fullmatch(r"pr-[0-9a-f]{8}", author)


def test_vibe_pr_rejects_a_bad_author() -> None:
    from click.testing import CliRunner

    from lib.vibe.cli.main import main

    out = CliRunner().invoke(main, ["pr", "--author", "<id>"])
    assert out.exit_code == 1 and "Invalid --author" in out.output


# ── scripts/review_gate.py: fail closed + real-git carry verification ────────


def _script():
    import importlib

    return importlib.import_module("scripts.review_gate")


class FakeGitHub:
    """Stands in for the GitHub calls scripts/review_gate.py makes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, gate, prs: dict[int, list[dict]]):
        # prs: number -> successive fetch() snapshots (the last one repeats)
        self.statuses: list[tuple[str, str, str]] = []
        self.prs = prs
        monkeypatch.setattr(gate, "_token", lambda: "tok")
        monkeypatch.setattr(gate, "set_status", self.set_status)
        monkeypatch.setattr(gate, "_get_pr", self.get_pr)
        monkeypatch.setattr(gate, "prs_for_sha", self.prs_for_sha)
        monkeypatch.setattr(gate, "fetch", self.fetch)
        monkeypatch.setattr(gate, "carry_verifier", lambda *a, **k: None)

    def set_status(self, _t, _r, sha, state, description):
        self.statuses.append((sha, state, description))

    def snapshot(self, number: int) -> dict:
        snaps = self.prs[number]
        return snaps[0] if len(snaps) == 1 else snaps.pop(0)

    def get_pr(self, _t, _r, number):
        snap = self.prs[number][0]
        return {"state": "open", "head": {"sha": snap["head"]}, "base": {"ref": "main"}}

    def prs_for_sha(self, _t, _r, sha):
        return [n for n, snaps in self.prs.items() if snaps[0]["head"] == sha]

    def fetch(self, _t, _r, number):
        return self.snapshot(number)


def snap(*reviews: Review, head: str = HEAD) -> dict:
    return {
        "head": head,
        "body": BODY,
        "reviews": list(reviews),
        "comments": [],
    }


def test_clean_pr_gets_success(monkeypatch: pytest.MonkeyPatch) -> None:
    gh = FakeGitHub(monkeypatch, _script(), {14: [snap(*agents(2))]})
    assert _script().main(["--pr", "14", "--repo", "o/r", "--set-status"]) == 0
    assert [st for _, st, _ in gh.statuses] == ["pending", "success"]


def test_any_exception_after_pending_sets_error(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _script()
    gh = FakeGitHub(monkeypatch, gate, {14: [snap(*agents(2))]})
    monkeypatch.setattr(gate, "fetch", lambda *a: (_ for _ in ()).throw(KeyError("head")))
    assert gate.main(["--pr", "14", "--repo", "o/r", "--set-status"]) == 2
    assert [st for _, st, _ in gh.statuses] == ["pending", "error"]


def test_pr_lookup_failure_sets_error_on_the_event_head(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _script()
    gh = FakeGitHub(monkeypatch, gate, {})
    monkeypatch.setattr(gate, "_get_pr", lambda *a: (_ for _ in ()).throw(ValueError("x")))
    args = ["--pr", "14", "--repo", "o/r", "--set-status", "--head-hint", HEAD]
    assert gate.main(args) == 2
    assert [(sha, st) for sha, st, _ in gh.statuses] == [(HEAD, "pending"), (HEAD, "error")]


def test_sha_lookup_failure_sets_error(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _script()
    gh = FakeGitHub(monkeypatch, gate, {})
    monkeypatch.setattr(gate, "prs_for_sha", lambda *a: (_ for _ in ()).throw(KeyError("x")))
    assert gate.main(["--sha", HEAD, "--repo", "o/r", "--set-status"]) == 2
    assert [(sha, st) for sha, st, _ in gh.statuses] == [(HEAD, "pending"), (HEAD, "error")]


def test_sha_with_no_open_pr_sets_error(monkeypatch: pytest.MonkeyPatch) -> None:
    gh = FakeGitHub(monkeypatch, _script(), {})
    assert _script().main(["--sha", HEAD, "--repo", "o/r", "--set-status"]) == 2
    assert [st for _, st, _ in gh.statuses] == ["pending", "error"]
    assert "no open PR" in gh.statuses[-1][2]


def test_prs_sharing_a_head_get_the_strictest_result(monkeypatch: pytest.MonkeyPatch) -> None:
    gh = FakeGitHub(monkeypatch, _script(), {14: [snap(*agents(2))], 20: [snap(agent("r1"))]})
    assert _script().main(["--sha", HEAD, "--repo", "o/r", "--set-status"]) == 0
    sha, state, description = gh.statuses[-1]
    assert (sha, state) == (HEAD, "failure") and description.startswith("PR #20:")


def test_reevaluates_when_the_pr_changes_mid_run(monkeypatch: pytest.MonkeyPatch) -> None:
    clean = snap(*agents(2))
    major = snap(*agents(2), agent("rx", verdict="major"))
    gh = FakeGitHub(monkeypatch, _script(), {14: [clean, major, major]})
    assert _script().main(["--pr", "14", "--repo", "o/r", "--set-status"]) == 0
    assert gh.statuses[-1][1] == "failure"


def test_sha_mode_requires_set_status() -> None:
    with pytest.raises(SystemExit):
        _script().main(["--sha", HEAD])


def _git(repo: Path, *args: str) -> str:
    import subprocess

    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        "HOME": str(repo), "PATH": __import__("os").environ["PATH"],
    }  # fmt: skip
    out = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_carry_verifier_accepts_pure_rebase_and_rejects_changed_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _script()
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("one\ntwo\nthree\n")
    _git(repo, "add", "."), _git(repo, "commit", "-qm", "base")
    _git(repo, "switch", "-qc", "pr")
    (repo / "a.txt").write_text("one\nTWO\nthree\n")
    _git(repo, "commit", "-qam", "pr change")
    old = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-q", "main")
    (repo / "b.txt").write_text("unrelated\n")
    _git(repo, "add", "."), _git(repo, "commit", "-qm", "main moves")
    _git(repo, "update-ref", "refs/remotes/origin/main", "main")
    _git(repo, "switch", "-q", "pr")
    _git(repo, "rebase", "-q", "main")
    rebased = _git(repo, "rev-parse", "HEAD")
    (repo / "a.txt").write_text("one\nTWO!\nthree\n")
    _git(repo, "commit", "-qam", "sneaky change")
    changed = _git(repo, "rev-parse", "HEAD")
    (repo / "a.txt").write_text("one\n  TWO\nthree\n")
    _git(repo, "commit", "-qam", "indent only")
    indented = _git(repo, "rev-parse", "HEAD")

    monkeypatch.setattr(gate, "GIT_DIR", repo)
    verify = gate.carry_verifier(None, "main", fetch=False)
    assert old != rebased
    assert verify(old, rebased) is None
    assert "not a pure rebase" in (verify(old, changed) or "")
    # Indentation is code in Python/YAML: whitespace-only edits must not carry reviews.
    assert "not a pure rebase" in (verify(changed, indented) or "")
    assert "couldn't verify" in (verify("f" * 40, rebased) or "")


# ── Edits can't change a verdict ─────────────────────────────────────────────


def _edited(review: Review, *older: str, complete: bool = True) -> Review:
    from dataclasses import replace

    return replace(review, edited=True, history=older, history_complete=complete)


def test_editing_a_major_to_pass_still_blocks() -> None:
    major = agent("sec", verdict="major")
    flipped = _edited(
        Review(**{**major.__dict__, "body": major.body.replace("verdict=major", "verdict=pass")}),
        major.body,
    )
    before = run([*agents(2), major])
    after = run([*agents(2), flipped])
    assert not before.passed and not after.passed
    assert any("Edited agent review" in b for b in after.blockers)


def test_editing_the_marker_away_still_blocks() -> None:
    major = agent("sec", verdict="major")
    wiped = _edited(Review(**{**major.__dict__, "body": "Never mind."}), major.body)
    assert not run([*agents(2), wiped]).passed


def test_edited_review_with_unknown_history_fails_closed() -> None:
    clean = _edited(agent("r9"), complete=False)
    assert not run([*agents(2), clean]).passed


def test_edited_review_that_never_mentioned_a_marker_is_ignored() -> None:
    plain = Review(
        id=777,
        login="kdenny",
        body="Typo fixed.",
        submitted_at="2026-10-27T04:00:00Z",
        commit_id=HEAD,
    )
    assert run([*agents(2), _edited(plain, "Typo fixd.")]).passed


def test_edited_review_on_an_old_head_does_not_block() -> None:
    old = agent("sec", verdict="major", head=OLD)
    assert run([*agents(2), _edited(old, old.body)]).passed


def test_comment_major_blocks_even_when_it_quotes_markers_or_was_edited_away() -> None:
    real = agent_marker("rx", HEAD, "major")
    quoting = comment(f"The grammar is `{PASS}`.\n\n{real}")
    assert not run(agents(2), [quoting]).passed
    edited_away = Review(
        id=555, login="kdenny", body="Retracted.", submitted_at="2026-10-27T04:00:00Z", kind="comment",
        edited=True, history=(f"Found a bug.\n{real}",),
    )  # fmt: skip
    assert not run(agents(2), [edited_away]).passed


def test_edit_history_reads_versions_paginates_and_flags_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _script()
    pages = iter(
        [
            {"data": {"repository": {"pullRequest": {"reviews": {
                "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                "nodes": [
                    {"databaseId": 1, "lastEditedAt": None, "userContentEdits": {"totalCount": 0, "nodes": []}},
                    {"databaseId": 2, "lastEditedAt": "2026-10-27T04:00:00Z",
                     "userContentEdits": {"totalCount": 2, "nodes": [{"diff": "v2"}, {"diff": "v1"}]}},
                ]}}}}},
            {"data": {"repository": {"pullRequest": {"reviews": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {"databaseId": 3, "lastEditedAt": "2026-10-27T05:00:00Z",
                     "userContentEdits": {"totalCount": 150, "nodes": [{"diff": "x"}]}},
                ]}}}}},
        ]
    )  # fmt: skip
    monkeypatch.setattr(gate, "_request", lambda *a, **k: (next(pages), ""))
    out = gate.edit_history("tok", "o/r", 14, "reviews")
    assert out == {1: (False, (), True), 2: (True, ("v2", "v1"), True), 3: (True, ("x",), False)}


def test_edit_history_graphql_errors_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _script()
    monkeypatch.setattr(gate, "_request", lambda *a, **k: ({"errors": [{"message": "nope"}]}, ""))
    with pytest.raises(gate.ApiError):
        gate.edit_history("tok", "o/r", 14, "comments")


@pytest.mark.parametrize(
    ("url", "repo"),
    [
        ("https://github.com/kevin-earl-denny/city-doodle.git", "kevin-earl-denny/city-doodle"),
        ("git@github.com:kevin-earl-denny/city-doodle.git", "kevin-earl-denny/city-doodle"),
        ("https://github.com/o/r", "o/r"),
    ],
)
def test_default_repo_prefers_env_then_origin(
    monkeypatch: pytest.MonkeyPatch, url: str, repo: str
) -> None:
    gate = _script()
    monkeypatch.setenv("GITHUB_REPOSITORY", "env/repo")
    assert gate._default_repo() == "env/repo"
    monkeypatch.delenv("GITHUB_REPOSITORY")
    monkeypatch.setattr(gate, "_git", lambda *a, **k: url + "\n")
    assert gate._default_repo() == repo
