#!/usr/bin/env python3
"""Say out loud when the checkout is behind origin/main (CITY-641, ported from sarto-db SAR-150).

With several agent sessions merging in parallel, a local `main` that trails `origin/main`
is the normal state of this checkout, not an edge case (on 2026-11-03 local main was 86
commits behind). A session that reads files on a stale `main` reasons about them as
current, and nothing says anything.

`bin/vibe do` already gets this right: it fetches and bases the new worktree on
`origin/main`. The leak is every other way a session starts — answering a question
against files on `main` without branching, resuming a worktree whose base has since
moved, or cutting a branch by hand.

This runs from a SessionStart hook (.claude/settings.json), so its stdout becomes session
context. It warns and exits 0 — always. A blocking check here would wedge intentional
old-base debugging and any offline session, to prevent a mistake that costs one `git pull`.
Must stay parseable by the system python3 (3.9 on macOS).

Usage:  python3 scripts/check_main_freshness.py [--no-fetch]
        --no-fetch compares against the refs already on disk (for tests, and offline).
Exit:   0 always. This check reports; it never blocks.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

FETCH_TIMEOUT_SECONDS = 10

# Kept narrow on purpose: a session that starts with no network, no remote, or a
# half-initialised repo should print nothing and get out of the way.
GIT_ERRORS = (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError)


def git(repo: Path, *args: str, timeout: int | None = None) -> str:
    """Run a git command in `repo` and return stripped stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def primary_repo_root(start: Path) -> Path | None:
    """Resolve the main checkout, even when called from inside a worktree.

    `--git-common-dir` points at the shared `.git` of the primary checkout, where a
    worktree's own `--git-dir` points at `.git/worktrees/<name>`. The local `main` branch
    lives in the shared store, so this is the tree whose freshness is worth reporting.
    """
    try:
        common = Path(git(start, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    except GIT_ERRORS:
        return None
    return common.parent if common.name == ".git" else None


def default_branch(repo: Path) -> str:
    """The remote's own idea of its default branch, falling back to `main`."""
    try:
        ref = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    except GIT_ERRORS:
        return "main"
    return ref.rsplit("/", 1)[-1] or "main"


def fetch(repo: Path, branch: str) -> bool:
    """Update `origin/<branch>`. False when the network or the remote is unavailable."""
    try:
        git(repo, "fetch", "origin", branch, timeout=FETCH_TIMEOUT_SECONDS)
    except GIT_ERRORS:
        return False
    return True


def divergence(repo: Path, branch: str) -> tuple[int, int] | None:
    """(behind, ahead) of local `branch` relative to `origin/branch`.

    None when either ref is missing — a fresh clone with no local `main`, or a repo with
    no `origin`. Both are legitimate states, and neither is worth a warning.
    """
    try:
        counts = git(repo, "rev-list", "--left-right", "--count", f"origin/{branch}...{branch}")
    except GIT_ERRORS:
        return None
    try:
        behind, ahead = (int(part) for part in counts.split())
    except ValueError:
        return None
    return behind, ahead


def current_branch(repo: Path) -> str:
    """The checked-out branch, or an empty string when detached."""
    try:
        return git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    except GIT_ERRORS:
        return ""


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def advise(behind: int, ahead: int, branch: str, main: str, repo: Path) -> str | None:
    """Decide what, if anything, to tell the session about a stale `main`.

    Returns the message to print, or None to stay silent.

    Four states, and they do not share a fix:

      current             say nothing.
      plainly behind      `pull --ff-only` closes it.
      diverged            `pull --ff-only` REFUSES on a diverged branch, so recommending
                          it sends the reader into an error instead of a fix. A local
                          `main` carrying unpushed commits also means someone worked on
                          `main` instead of a ticket branch.
      behind, elsewhere   the reader is in a worktree. Pulling `main` is not the useful
                          action; their own branch base is the thing likely to be stale,
                          and this check cannot see that.
    """
    on_main = branch == main
    gap = f"{plural(behind, 'commit')} behind origin/{main}"

    if behind and ahead:
        return (
            f"{main} has diverged from origin/{main}: {behind} behind, {ahead} ahead.\n"
            f"  {plural(ahead, 'commit')} on local {main} was never pushed; work belongs on "
            f"ticket branches, not `{main}`.\n"
            f"  Inspect before reconciling: git -C {repo} log --oneline origin/{main}..{main}"
        )

    if behind and on_main:
        return f"{main} is {gap}.\n  git -C {repo} pull --ff-only"

    if behind:
        return (
            f"{main} is {gap}, and you are on {branch}.\n"
            f"  Pulling {main} is probably not what you want. Your branch base may be stale "
            f"too, which this check cannot see:\n"
            f"  git -C {repo} log --oneline HEAD..origin/{main}"
        )

    if ahead:
        return (
            f"{main} has {plural(ahead, 'unpushed commit')}; work belongs on ticket "
            f"branches, not `{main}`.\n"
            f"  Inspect: git -C {repo} log --oneline origin/{main}..{main}"
        )

    return None


def check(repo: Path, do_fetch: bool = True) -> str | None:
    """Full check against `repo`. Returns the message to print, or None."""
    main = default_branch(repo)
    if do_fetch and not fetch(repo, main):
        return None  # Offline or no remote. Not the session's problem to solve.

    counts = divergence(repo, main)
    if counts is None:
        return None
    behind, ahead = counts

    return advise(behind, ahead, current_branch(repo), main, repo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-fetch", action="store_true", help="compare against on-disk refs")
    args = parser.parse_args(argv)

    try:
        repo = primary_repo_root(Path.cwd())
        if repo is None:
            return 0
        message = check(repo, do_fetch=not args.no_fetch)
    except Exception:  # noqa: BLE001 - a SessionStart hook must never fail the session
        return 0
    if message:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
