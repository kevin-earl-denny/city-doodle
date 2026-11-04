#!/usr/bin/env python3
"""Evaluate the merge bar for one PR and set the `review-gate` status (CITY-637).

    python3 scripts/review_gate.py --pr 12               # print the verdict (dry run)
    python3 scripts/review_gate.py --pr 12 --set-status  # CI: also set the commit status
    python3 scripts/review_gate.py --sha <head> --set-status   # CI: PRs whose head is <sha>

Counting rules (and the policy) live in ``lib/vibe/review_gate.py``.
The status is a commit status on the PR's *current* head (read from the API, not
from the triggering event), so a run triggered by a stale review or a comment
still judges the right commit.

Fail closed: with --set-status the head gets `pending` before anything is
evaluated, and any exception turns it into `error`, so a stale `success` never
survives a run that couldn't finish.

Rebase carries are verified here with git, never trusted: the cumulative patch
of merge-base(base, old)..old must have the same `git patch-id --verbatim` as
merge-base(base, new)..new. Git only reads the commits; no PR code runs.

Token: ``GITHUB_TOKEN`` / ``GH_TOKEN``, else ``gh auth token``. CI uses the
workflow's own GITHUB_TOKEN; no repository secret is involved.

Exit codes: 0 gate passes (or, with --set-status, the status was set either way),
1 gate fails (dry run), 2 GitHub API error (an incident).
Stdlib only, so CI can run it without installing the project.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.vibe.review_gate import (  # noqa: E402
    STATUS_CONTEXT,
    GateResult,
    Review,
    evaluate,
    summary_markdown,
)

API = "https://api.github.com"
GIT_DIR = REPO_ROOT  # where carries are verified; tests point it at a scratch repo


class ApiError(Exception):
    pass


def _token() -> str:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ApiError("no GITHUB_TOKEN/GH_TOKEN and `gh auth token` failed") from exc
    return out.stdout.strip()


def _request(token: str, method: str, url: str, payload: dict | None = None) -> tuple[object, str]:
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "city-review-gate",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"null"), resp.headers.get("Link", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise ApiError(f"{method} {url} → HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"{method} {url} → {exc.reason}") from exc


def _paginate(token: str, url: str) -> list[dict]:
    items: list[dict] = []
    next_url: str | None = f"{url}?per_page=100"
    while next_url:
        data, link = _request(token, "GET", next_url)
        if not isinstance(data, list):
            raise ApiError(f"GET {next_url} returned {type(data).__name__}, expected a list")
        items.extend(data)
        next_url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                next_url = part[part.index("<") + 1 : part.index(">")]
    return items


def _login(obj: dict) -> str:
    # A deleted account ("ghost") comes back as user: null.
    return str((obj.get("user") or {}).get("login") or "")


EDITS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      %s(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          databaseId
          lastEditedAt
          userContentEdits(first: 100) { totalCount nodes { diff } }
        }
      }
    }
  }
}
"""

EditInfo = tuple[bool, tuple[str, ...], bool]  # edited, earlier versions, history complete


def edit_history(token: str, repo: str, number: int, connection: str) -> dict[int, EditInfo]:
    """Edit status and every earlier version of each PR review or comment (GraphQL).

    REST shows only the current body; a verdict edited after posting must not
    count, so the gate needs the history. ``connection`` is ``reviews`` or ``comments``.
    """
    owner, name = repo.split("/", 1)
    out: dict[int, EditInfo] = {}
    after: str | None = None
    while True:
        variables = {"owner": owner, "name": name, "number": number, "after": after}
        data, _ = _request(
            token,
            "POST",
            f"{API}/graphql",
            {"query": EDITS_QUERY % connection, "variables": variables},
        )
        if not isinstance(data, dict) or data.get("errors") or not data.get("data"):
            raise ApiError(f"GraphQL {connection} edit history: {str(data)[:200]}")
        page = data["data"]["repository"]["pullRequest"][connection]
        for node in page["nodes"]:
            edits = node.get("userContentEdits") or {"totalCount": 0, "nodes": []}
            versions = tuple((e.get("diff") or "") for e in edits["nodes"])
            out[node["databaseId"]] = (
                node.get("lastEditedAt") is not None,
                versions,
                edits["totalCount"] <= len(edits["nodes"]),
            )
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def fetch(token: str, repo: str, number: int) -> dict:
    base = f"{API}/repos/{repo}"
    pr, _ = _request(token, "GET", f"{base}/pulls/{number}")
    if not isinstance(pr, dict):
        raise ApiError(f"PR #{number}: unexpected response")
    review_edits = edit_history(token, repo, number, "reviews")
    comment_edits = edit_history(token, repo, number, "comments")
    unedited: EditInfo = (False, (), True)
    reviews = [
        Review(
            id=r["id"],
            login=_login(r),
            body=r.get("body") or "",
            submitted_at=r.get("submitted_at") or "",
            kind="review",
            state=r.get("state", ""),
            commit_id=r.get("commit_id") or "",
            edited=(e := review_edits.get(r["id"], unedited))[0],
            history=e[1],
            history_complete=e[2],
        )
        for r in _paginate(token, f"{base}/pulls/{number}/reviews")
        if r.get("state") != "PENDING"
    ]
    comments = [
        Review(
            id=c["id"],
            login=_login(c),
            body=c.get("body") or "",
            submitted_at=c.get("created_at") or "",
            kind="comment",
            edited=(e := comment_edits.get(c["id"], unedited))[0],
            history=e[1],
            history_complete=e[2],
        )
        for c in _paginate(token, f"{base}/issues/{number}/comments")
    ]
    return {
        "head": pr["head"]["sha"],
        "body": pr.get("body") or "",
        "reviews": reviews,
        "comments": comments,
    }


def set_status(token: str, repo: str, sha: str, state: str, description: str) -> None:
    target = None
    if os.environ.get("GITHUB_RUN_ID"):
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        target = f"{server}/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    payload = {"state": state, "context": STATUS_CONTEXT, "description": description[:140]}
    if target:
        payload["target_url"] = target
    _request(token, "POST", f"{API}/repos/{repo}/statuses/{sha}", payload)


#: Where carry verification keeps the base branch it fetched. A private namespace,
#: so a local `bin/vibe review-gate` never moves the user's `refs/remotes/origin/*`.
BASE_REF_NS = "refs/review-gate/base"


def _git(token: str | None, *args: str, stdin: str | None = None, cwd: Path | None = None) -> str:
    env = None
    if token:
        # Auth for this one call only, passed as GIT_CONFIG_* environment entries:
        # never on the command line (any local user can read argv with `ps`) and
        # never written to .git/config.
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env = dict(os.environ)
        n = int(env.get("GIT_CONFIG_COUNT") or 0)  # keep any entries the caller set
        env["GIT_CONFIG_COUNT"] = str(n + 1)
        env[f"GIT_CONFIG_KEY_{n}"] = "http.https://github.com/.extraheader"
        env[f"GIT_CONFIG_VALUE_{n}"] = f"AUTHORIZATION: basic {basic}"
    out = subprocess.run(
        ["git", *args],
        cwd=cwd or GIT_DIR,
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return out.stdout


def carry_verifier(token: str | None, base_ref: str, *, fetch: bool = True):
    """``verify(old, new)`` for evaluate(): None if both heads carry the same patch.

    The base branch is fetched into ``BASE_REF_NS``, never over a remote-tracking
    ref. ``fetch=False`` skips fetching (tests: the commits and that ref are local).
    """
    fetched: set[str] = set()
    base = f"{BASE_REF_NS}/{base_ref}"

    def patch_id(sha: str) -> str:
        merge_base = _git(None, "merge-base", base, sha).strip()
        diff = _git(None, "diff", "--no-ext-diff", "--no-textconv", "--binary", merge_base, sha)
        # --verbatim: whitespace counts (an indent change is a code change in Python/YAML).
        ids = _git(None, "patch-id", "--verbatim", stdin=diff).split()
        return ids[0] if ids else ""

    def verify(old: str, new: str) -> str | None:
        try:
            if fetch and base_ref not in fetched:
                _git(
                    token,
                    "fetch",
                    "--no-tags",
                    "--quiet",
                    "--no-write-fetch-head",
                    # Empty refmap: no "opportunistic" update of origin/* refs.
                    "--refmap=",
                    "origin",
                    f"+refs/heads/{base_ref}:{base}",
                )
                fetched.add(base_ref)
            missing = [sha for sha in (old, new) if sha not in fetched]
            if fetch and missing:
                _git(
                    token,
                    "fetch",
                    "--no-tags",
                    "--quiet",
                    "--no-write-fetch-head",
                    # Empty refmap: no "opportunistic" update of origin/* refs.
                    "--refmap=",
                    "origin",
                    *missing,
                )
                fetched.update(missing)
            old_id, new_id = patch_id(old), patch_id(new)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip().splitlines()[-1:] or ["git failed"]
            return f"couldn't verify the rebase: {detail[0][:100]}"
        if not old_id or old_id != new_id:
            return "not a pure rebase: the patch differs between the two heads"
        return None

    return verify


_REMOTE = re.compile(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$")


def _default_repo() -> str:
    """$GITHUB_REPOSITORY (CI), else the `origin` remote, else .vibe/config.json.

    The origin remote comes before the config because the repo was transferred
    (kdenny → kevin-earl-denny) and the config may still name the old owner.
    """
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    try:
        url = _git(None, "remote", "get-url", "origin").strip()
    except (OSError, subprocess.CalledProcessError):
        url = ""
    if m := _REMOTE.search(url):
        return m.group(1)
    cfg = json.loads((REPO_ROOT / ".vibe" / "config.json").read_text())["github"]
    return f"{cfg['owner']}/{cfg['repo']}"


def prs_for_sha(token: str, repo: str, sha: str) -> list[int]:
    """Open PRs whose head is ``sha`` (workflow_run events may not name the PR)."""
    data, _ = _request(token, "GET", f"{API}/repos/{repo}/commits/{sha}/pulls")
    if not isinstance(data, list):
        raise ApiError(f"commits/{sha}/pulls returned {type(data).__name__}")
    return [p["number"] for p in data if p.get("state") == "open" and p["head"]["sha"] == sha]


def _report(result: GateResult, as_json: bool) -> None:
    summary = summary_markdown(result)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")
    if not as_json:
        print(summary)
        return
    print(
        json.dumps(
            {
                "passed": result.passed,
                "head": result.head,
                "author": result.author,
                "coderabbit": result.coderabbit,
                "agents": result.agents,
                "required_agent_reviews": result.required,
                "blockers": result.blockers,
            },
            indent=2,
        )
    )


def evaluate_pr(token: str, repo: str, number: int, base_ref: str) -> GateResult:
    """Evaluate one PR on data that's still current when we return (re-read up to 3×)."""
    verify = carry_verifier(token, base_ref)
    data = fetch(token, repo, number)
    for _attempt in range(3):
        result = evaluate(
            head=data["head"],
            pr_body=data["body"],
            reviews=data["reviews"],
            comments=data["comments"],
            verify_carry=verify,
        )
        # Write only a verdict that's still current: if a review, body edit or push
        # landed while we evaluated, evaluate again rather than post a stale result.
        fresh = fetch(token, repo, number)
        if fresh == data:
            return result
        data = fresh
    raise ApiError(f"PR #{number} kept changing while it was evaluated; re-run")


def _get_pr(token: str, repo: str, number: int) -> dict:
    pr, _ = _request(token, "GET", f"{API}/repos/{repo}/pulls/{number}")
    if not isinstance(pr, dict):
        raise ApiError(f"PR #{number}: unexpected response")
    return pr


_sleep = time.sleep  # tests stub it out
PR_LOOKUP_ATTEMPTS = 3


def _get_pr_with_retry(token: str, repo: str, number: int) -> dict:
    """``_get_pr`` with backoff: with no event head to mark (issue_comment), a failed
    lookup can't fail closed on the commit, so try harder before giving up."""
    for attempt in range(1, PR_LOOKUP_ATTEMPTS + 1):
        try:
            return _get_pr(token, repo, number)
        except Exception as exc:  # noqa: BLE001
            if attempt == PR_LOOKUP_ATTEMPTS:
                raise
            print(f"review-gate: PR #{number} lookup failed ({exc}); retrying", file=sys.stderr)
            _sleep(2**attempt)
    raise AssertionError("unreachable")


def _error(token: str, repo: str, sha: str | None, message: str) -> int:
    print(f"review-gate: {message}", file=sys.stderr)
    if sha:
        try:
            set_status(token, repo, sha, "error", f"review-gate errored: {message}")
            return 2
        except Exception as inner:  # noqa: BLE001
            print(f"review-gate: also failed to set error status: {inner}", file=sys.stderr)
    # No status could be written, so an earlier `success` on the head may survive:
    # fail the job loudly (an annotation on the run) so it's visible and re-run.
    detail = _escape_command_data(
        f"{message}. The PR head's previous review-gate status may be stale; re-run this job."
    )
    # stdout: where the Actions runner reads workflow commands
    print(f"::error title=review-gate status not updated::{detail}")
    return 2


def _escape_command_data(text: str) -> str:
    """Escape a workflow command's message: a raw newline would end the command
    and spill the rest of the text into the log as plain lines."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def gate_head(token: str, repo: str, head: str, must_include: int | None, as_json: bool) -> int:
    """Set the status on ``head`` from EVERY open PR whose head it is (a status is per
    commit, so PRs sharing a head get the strictest result). Fails closed throughout.
    """
    try:
        set_status(token, repo, head, "pending", "review-gate is evaluating")
        numbers = prs_for_sha(token, repo, head)
        if must_include is not None and must_include not in numbers:
            numbers.append(must_include)  # the API's head index can lag a push
        if not numbers:
            return _error(token, repo, head, f"no open PR has head {head[:7]}")
        verdicts: list[tuple[int, GateResult]] = []
        for number in sorted(numbers):
            pr = _get_pr(token, repo, number)
            if pr.get("state") != "open" or pr["head"]["sha"] != head:
                print(f"PR #{number} no longer has head {head[:7]}; its own run gates it.")
                continue
            result = evaluate_pr(token, repo, number, pr["base"]["ref"])
            if result.head != head:
                print(f"PR #{number} moved to {result.head[:7]}; its own run gates it.")
                continue
            _report(result, as_json)
            verdicts.append((number, result))
        if not verdicts:
            print(f"No open PR still has head {head[:7]}; leaving it pending.")
            return 0
        passed = all(r.passed for _, r in verdicts)
        if len(verdicts) == 1:
            description = verdicts[0][1].description()
        else:
            worst = sorted(verdicts, key=lambda v: v[1].passed)
            description = "; ".join(f"PR #{n}: {r.description()}" for n, r in worst)
        state = "success" if passed else "failure"
        set_status(token, repo, head, state, description)
        print(f"Set {STATUS_CONTEXT}={state} on {head[:7]}: {description}")
        return 0
    except Exception as exc:  # noqa: BLE001 - any failure must leave an error status, not success
        kind = "GitHub API error" if isinstance(exc, ApiError) else type(exc).__name__
        return _error(token, repo, head, f"{kind}: {exc}")


def dry_run(token: str, repo: str, number: int, as_json: bool) -> int:
    """Local check of one PR (any state): exit 0 pass, 1 fail, 2 error."""
    try:
        pr = _get_pr(token, repo, number)
        result = evaluate_pr(token, repo, number, pr["base"]["ref"])
    except Exception as exc:  # noqa: BLE001
        print(f"review-gate: PR #{number}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    _report(result, as_json)
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--pr", type=int, help="PR number")
    target.add_argument("--sha", help="gate every open PR whose head is this SHA (CI)")
    ap.add_argument("--repo", default=None, help="owner/name (default: $GITHUB_REPOSITORY)")
    ap.add_argument(
        "--set-status",
        action="store_true",
        help=f"set the `{STATUS_CONTEXT}` commit status on the head (CI)",
    )
    ap.add_argument("--head-hint", default=None, help="event's head SHA: marked pending first")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)
    if args.sha and not args.set_status:
        ap.error("--sha is for CI and needs --set-status; use --pr for a dry run")
    try:
        repo = args.repo or _default_repo()
        token = _token()
    except Exception as exc:  # noqa: BLE001
        print(f"review-gate: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not args.set_status:
        return dry_run(token, repo, args.pr, args.json)
    if args.sha:
        return gate_head(token, repo, args.sha, None, args.json)
    # --pr: fail closed on the event's head first, then gate the PR's current head.
    hint = args.head_hint
    try:
        if hint:
            set_status(token, repo, hint, "pending", "review-gate is evaluating")
        pr = _get_pr(token, repo, args.pr) if hint else _get_pr_with_retry(token, repo, args.pr)
    except Exception as exc:  # noqa: BLE001
        return _error(token, repo, hint, f"PR #{args.pr}: {type(exc).__name__}: {exc}")
    if pr.get("state") != "open":
        # Closed PRs aren't gated. A leftover `pending` is harmless (fails closed).
        print(f"PR #{args.pr} is {pr.get('state')}; nothing to gate.")
        return 0
    head = pr["head"]["sha"]
    code = gate_head(token, repo, head, args.pr, args.json)
    if hint and hint != head:
        print(f"Event head {hint[:7]} is stale; the PR's head is {head[:7]}.")
    return code


if __name__ == "__main__":
    sys.exit(main())
