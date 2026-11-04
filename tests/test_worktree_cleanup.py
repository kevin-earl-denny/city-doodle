"""CITY-641: ticket-aware worktree cleanup (ported from foreclosure-finder DEAL-3854).

Pins the rule: a worktree is removable ONLY on positive proof of completion — a
terminal Linear ticket, a clean tree, and an age provably past the 30-minute grace
period. Every ambiguous case resolves to "protect", so a concurrent agent's
fresh, zero-commit worktree (which `git branch --merged` reports as merged) is
never swept.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib.vibe.git.worktree_cleanup import (
    GRACE_PERIOD_MINUTES,
    classify_worktrees,
    decide_worktree_fate,
    extract_ticket_id,
    is_started_status,
    is_terminal_status,
)
from lib.vibe.trackers.base import Ticket


def _ticket(status: str = "In Progress", status_type: str | None = None) -> Ticket:
    return Ticket(
        id="CITY-641",
        title="t",
        description="",
        status=status,
        labels=[],
        url="",
        raw={},
        status_type=status_type,
    )


# --- extract_ticket_id -------------------------------------------------------


@pytest.mark.parametrize(
    "branch,expected",
    [
        ("CITY-576-fix-rivers-not-properly-connec", "CITY-576"),
        ("CITY-641", "CITY-641"),
        ("feature/CITY-12-foo", "CITY-12"),
        ("no-ticket-here", None),
        ("", None),
        ("main", None),
    ],
)
def test_extract_ticket_id(branch: str, expected: str | None) -> None:
    assert extract_ticket_id(branch) == expected


# --- status helpers ----------------------------------------------------------


def test_is_terminal_status() -> None:
    assert is_terminal_status(_ticket(status="Anything", status_type="completed"))
    assert is_terminal_status(_ticket(status="Anything", status_type="canceled"))
    assert is_terminal_status(_ticket(status="Done", status_type=None))
    assert is_terminal_status(_ticket(status="Deployed", status_type="started"))
    for status, kind in [
        ("In Progress", "started"),
        ("In Review", "started"),
        ("Todo", "unstarted"),
        ("Backlog", "backlog"),
    ]:
        assert not is_terminal_status(_ticket(status=status, status_type=kind))


def test_is_started_status() -> None:
    assert is_started_status(_ticket(status_type="started"))
    assert is_started_status(_ticket(status="In Review", status_type=None))
    assert not is_started_status(_ticket(status="Todo", status_type="unstarted"))
    assert not is_started_status(_ticket(status="Done", status_type="completed"))


# --- decide_worktree_fate (pure decision logic) ------------------------------


def _decide(**overrides: object) -> tuple[str, str]:
    """Decide fate from a known-removable baseline, overriding one factor."""
    kwargs: dict[str, object] = {
        "ticket_id": "CITY-641",
        "has_uncommitted_changes": False,
        "age_minutes": float(GRACE_PERIOD_MINUTES + 10),
        "ticket": _ticket(status="Done", status_type="completed"),
    }
    kwargs.update(overrides)
    return decide_worktree_fate(**kwargs)  # type: ignore[arg-type]


def test_terminal_clean_old_worktree_is_removable() -> None:
    assert _decide()[0] == "remove"
    assert _decide(ticket=_ticket(status="Canceled", status_type="canceled"))[0] == "remove"


@pytest.mark.parametrize(
    "status,status_type",
    [
        ("Backlog", "backlog"),
        ("Todo", "unstarted"),
        ("In Progress", "started"),
        ("In Review", "started"),
    ],
)
def test_non_terminal_ticket_is_never_removed(status: str, status_type: str) -> None:
    decision, reason = _decide(ticket=_ticket(status=status, status_type=status_type))
    assert decision == "protect"
    assert "active" in reason


def test_no_ticket_id_is_protected() -> None:
    assert _decide(ticket_id=None)[0] == "protect"


def test_unresolved_ticket_is_protected() -> None:
    decision, reason = _decide(ticket=None)
    assert decision == "protect"
    assert "CITY-641" in reason


def test_uncommitted_changes_beat_terminal_ticket() -> None:
    decision, reason = _decide(has_uncommitted_changes=True)
    assert decision == "protect"
    assert "uncommitted" in reason


def test_grace_period_beats_terminal_ticket() -> None:
    decision, reason = _decide(age_minutes=2.0)
    assert decision == "protect"
    assert "grace period" in reason


def test_grace_boundary_is_inclusive_of_30_minutes() -> None:
    assert _decide(age_minutes=float(GRACE_PERIOD_MINUTES))[0] == "remove"
    assert _decide(age_minutes=float(GRACE_PERIOD_MINUTES) - 0.1)[0] == "protect"


def test_unknown_age_is_protected() -> None:
    # Removal needs proof the worktree is >30 min old; unknown age is not proof.
    assert _decide(age_minutes=None)[0] == "protect"


# --- classify_worktrees against a real git repo -------------------------------


class _FakeTracker:
    def __init__(self, tickets: dict[str, Ticket | None]) -> None:
        self.tickets = tickets
        self.lookups: list[str] = []

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        self.lookups.append(ticket_id)
        return self.tickets.get(ticket_id)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo_with_worktrees(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README").write_text("x")
    _git(repo, "add", "README")
    _git(repo, "commit", "-q", "-m", "init")
    for branch in ("CITY-1", "CITY-2", "CITY-3", "scratch"):
        _git(repo, "worktree", "add", "-q", "-b", branch, str(tmp_path / "wts" / branch))
    (tmp_path / "wts" / "CITY-3" / "dirty.txt").write_text("unsaved")
    return repo


def test_classify_only_removes_terminal_clean_old_worktrees(repo_with_worktrees: Path) -> None:
    tracker = _FakeTracker(
        {
            "CITY-1": _ticket(status="Done", status_type="completed"),
            "CITY-2": _ticket(status="In Progress", status_type="started"),
            "CITY-3": _ticket(status="Done", status_type="completed"),
        }
    )
    later = datetime.now() + timedelta(minutes=GRACE_PERIOD_MINUTES + 5)
    statuses = {
        s.branch: s
        for s in classify_worktrees(repo_with_worktrees, tracker=tracker, now=later)  # type: ignore[arg-type]
    }

    assert set(statuses) == {"CITY-1", "CITY-2", "CITY-3", "scratch"}  # main excluded
    assert statuses["CITY-1"].removable
    assert not statuses["CITY-2"].removable  # active ticket
    assert "uncommitted" in statuses["CITY-3"].reason  # dirty beats Done
    assert not statuses["CITY-3"].removable
    assert not statuses["scratch"].removable  # no ticket id


def test_classify_protects_fresh_zero_commit_worktree_even_if_done(
    repo_with_worktrees: Path,
) -> None:
    # The concurrent-agent hazard: a just-created branch with zero commits.
    tracker = _FakeTracker({"CITY-1": _ticket(status="Done", status_type="completed")})
    statuses = {
        s.branch: s
        for s in classify_worktrees(repo_with_worktrees, tracker=tracker)  # type: ignore[arg-type]
    }
    assert not any(s.removable for s in statuses.values())
    assert "grace period" in statuses["CITY-1"].reason
    assert tracker.lookups == []  # cheap guards short-circuit the Linear lookup


def test_classify_protects_when_tracker_lookup_fails(repo_with_worktrees: Path) -> None:
    class Boom:
        def get_ticket(self, ticket_id: str) -> Ticket | None:
            raise RuntimeError("LINEAR_API_KEY not set")

    later = datetime.now() + timedelta(minutes=GRACE_PERIOD_MINUTES + 5)
    statuses = classify_worktrees(repo_with_worktrees, tracker=Boom(), now=later)  # type: ignore[arg-type]
    assert statuses and not any(s.removable for s in statuses)


# --- lookup failures are surfaced, not swallowed (CodeRabbit #472) -----------


def test_lookup_error_is_kept_on_status_and_in_reason(repo_with_worktrees: Path) -> None:
    class Boom:
        def get_ticket(self, ticket_id: str) -> Ticket | None:
            raise RuntimeError("LINEAR_API_KEY not set")

    later = datetime.now() + timedelta(minutes=GRACE_PERIOD_MINUTES + 5)
    statuses = {
        s.branch: s
        for s in classify_worktrees(repo_with_worktrees, tracker=Boom(), now=later)  # type: ignore[arg-type]
    }
    # Only worktrees that reached the Linear lookup carry the error.
    assert statuses["CITY-1"].lookup_error == "LINEAR_API_KEY not set"
    assert "LINEAR_API_KEY not set" in statuses["CITY-1"].reason
    assert statuses["CITY-3"].lookup_error is None  # dirty: decided before any lookup
    assert statuses["scratch"].lookup_error is None


def test_unconstructible_tracker_is_reported(
    repo_with_worktrees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lib.vibe.git import worktree_cleanup

    monkeypatch.setattr(
        worktree_cleanup, "_load_linear_tracker", lambda root: (None, "Linear tracker unavailable")
    )
    later = datetime.now() + timedelta(minutes=GRACE_PERIOD_MINUTES + 5)
    statuses = {s.branch: s for s in classify_worktrees(repo_with_worktrees, now=later)}
    assert statuses["CITY-1"].lookup_error == "Linear tracker unavailable"
    assert not statuses["CITY-1"].removable


def test_worktree_containing_cwd_is_never_listed(
    repo_with_worktrees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lib.vibe.git.worktree_cleanup import list_feature_worktrees

    wt = repo_with_worktrees.parent / "wts" / "CITY-1"
    (wt / "sub").mkdir()
    monkeypatch.chdir(wt / "sub")
    branches = {w["branch"] for w in list_feature_worktrees(repo_with_worktrees)}
    assert "CITY-1" not in branches
    assert "CITY-2" in branches


def test_cleanup_cli_exits_1_when_lookups_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from lib.vibe.cli import main as vibe_main
    from lib.vibe.git.worktree_cleanup import WorktreeStatus

    status = WorktreeStatus(
        path=str(tmp_path / "CITY-1"),
        branch="CITY-1",
        ticket_id="CITY-1",
        decision="protect",
        reason="could not resolve CITY-1 in Linear — refusing to guess: LINEAR_API_KEY not set",
        lookup_error="LINEAR_API_KEY not set",
    )
    monkeypatch.setattr("lib.vibe.git.worktrees.get_primary_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "lib.vibe.git.worktree_cleanup.classify_worktrees", lambda root, **kw: [status]
    )
    for args in (["cleanup", "--dry-run"], ["cleanup", "--force"]):
        result = CliRunner().invoke(vibe_main.main, args)
        assert result.exit_code == 1, result.output
        assert "LINEAR_API_KEY not set" in result.output
        assert "Nothing to clean up" not in result.output


# --- agent review round (reviewer-a / reviewer-b, CITY-675) --------------------


def _write_state_entry(repo: Path, ticket_id: str, worktree: Path, created_at: datetime) -> None:
    import json

    state_file = repo / ".vibe" / "local_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "active_worktrees": [],
                "ticket_branches": {
                    ticket_id: [
                        {
                            "branch": ticket_id,
                            "worktree_path": str(worktree),
                            "created_at": created_at.isoformat(),
                        }
                    ]
                },
            }
        )
    )


def test_stale_state_entry_cannot_bypass_grace_period(repo_with_worktrees: Path) -> None:
    # A worktree re-created at an old path: the state entry is 3 days old, the
    # worktree's own `.git` is brand new. The newer timestamp must win.
    wt = repo_with_worktrees.parent / "wts" / "CITY-1"
    _write_state_entry(repo_with_worktrees, "CITY-1", wt, datetime.now() - timedelta(days=3))
    tracker = _FakeTracker({"CITY-1": _ticket(status="Done", status_type="completed")})
    statuses = {
        s.branch: s
        for s in classify_worktrees(repo_with_worktrees, tracker=tracker)  # type: ignore[arg-type]
    }
    assert not statuses["CITY-1"].removable
    assert "grace period" in statuses["CITY-1"].reason


def test_newer_state_entry_wins_over_old_git_mtime(repo_with_worktrees: Path) -> None:
    import os

    from lib.vibe.git.worktree_cleanup import _worktree_age_minutes

    wt = repo_with_worktrees.parent / "wts" / "CITY-1"
    old = (datetime.now() - timedelta(days=3)).timestamp()
    os.utime(wt / ".git", (old, old))
    _write_state_entry(repo_with_worktrees, "CITY-1", wt, datetime.now() - timedelta(minutes=5))
    age = _worktree_age_minutes(str(wt), repo_with_worktrees)
    assert age is not None and age < GRACE_PERIOD_MINUTES


def test_duplicate_state_is_terminal() -> None:
    assert is_terminal_status(_ticket(status="Duplicate", status_type="duplicate"))
    assert is_terminal_status(_ticket(status="Duplicate", status_type=None))
    assert not is_started_status(_ticket(status="Duplicate", status_type="duplicate"))
    assert _decide(ticket=_ticket(status="Duplicate", status_type="duplicate"))[0] == "remove"


def test_caller_cwd_from_wrapper_is_protected(
    repo_with_worktrees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # bin/vibe cds to its own checkout, so Python's cwd is the main repo; the
    # caller's real directory arrives via VIBE_CALLER_CWD.
    from lib.vibe.git.worktree_cleanup import list_feature_worktrees

    monkeypatch.chdir(repo_with_worktrees)
    monkeypatch.setenv("VIBE_CALLER_CWD", str(repo_with_worktrees.parent / "wts" / "CITY-2"))
    branches = {w["branch"] for w in list_feature_worktrees(repo_with_worktrees)}
    assert "CITY-2" not in branches
    assert "CITY-1" in branches


def test_bin_vibe_exports_caller_cwd_before_cd() -> None:
    script = (Path(__file__).resolve().parents[1] / "bin" / "vibe").read_text()
    export_at = script.index('export VIBE_CALLER_CWD="$PWD"')
    assert export_at < script.index('cd "$REPO_ROOT"\n    python -m lib.vibe.cli.main')


def test_cleanup_cli_exits_1_when_a_removal_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from lib.vibe.cli import main as vibe_main
    from lib.vibe.git.worktree_cleanup import WorktreeStatus

    status = WorktreeStatus(
        path=str(tmp_path / "CITY-9"),
        branch="CITY-9",
        ticket_id="CITY-9",
        decision="remove",
        reason="CITY-9 is 'Done'",
    )
    monkeypatch.setattr("lib.vibe.git.worktrees.get_primary_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "lib.vibe.git.worktree_cleanup.classify_worktrees", lambda root, **kw: [status]
    )
    monkeypatch.setattr(
        "lib.vibe.git.worktree_cleanup.remove_worktree_and_branch",
        lambda *a: (False, "git worktree remove failed: locked"),
    )
    monkeypatch.setattr(vibe_main, "run_doctor", lambda *a, **k: [])
    result = CliRunner().invoke(vibe_main.main, ["cleanup", "--force"])
    assert result.exit_code == 1, result.output
    assert "Failed to remove CITY-9" in result.output
