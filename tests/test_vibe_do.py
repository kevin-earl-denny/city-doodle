"""CITY-641: `bin/vibe do` — bare CITY-NNN branch, validate before side effects, claim.

Ported from foreclosure-finder (FORE-93 / DEAL-4152 tests) and adapted to city-doodle.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from lib.vibe.cli import main as vibe_main
from lib.vibe.cli.main import _already_started_guard_message, _mark_ticket_in_progress
from lib.vibe.git import branches
from lib.vibe.trackers import linear as linear_mod
from lib.vibe.trackers.base import Ticket

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAM = "48a87c3c-6f07-4af2-b5aa-4e100919ba26"


def _ticket(
    status: str = "Todo", status_type: str | None = None, assignee: str | None = None
) -> Ticket:
    return Ticket(
        id="CITY-641",
        title="Make vibe do safe",
        description="",
        status=status,
        labels=[],
        url="",
        raw={},
        status_type=status_type,
        assignee=assignee,
    )


# --------------------------------------------------------------------------- #
# Branch naming                                                               #
# --------------------------------------------------------------------------- #


def _pattern(monkeypatch: pytest.MonkeyPatch, pattern: str) -> None:
    monkeypatch.setattr(branches, "load_config", lambda: {"branching": {"pattern": pattern}})


def test_default_pattern_has_no_title_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    _pattern(monkeypatch, "{PROJ}-{num}")
    assert branches.format_branch_name("CITY-576", "Fix rivers not properly connected") == (
        "CITY-576"
    )
    assert branches.format_branch_name("CITY-576") == "CITY-576"


def test_title_slug_is_opt_in_via_pattern_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _pattern(monkeypatch, "{PROJ}-{num}-{title}")
    assert branches.format_branch_name("CITY-9", "Fix Do!") == "CITY-9-fix-do"
    # No title -> no dangling separator.
    assert branches.format_branch_name("CITY-9") == "CITY-9"


def test_repo_config_pattern_yields_bare_ticket_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)  # real .vibe/config.json
    assert branches.format_branch_name("CITY-641", "Some long title here") == "CITY-641"


# --------------------------------------------------------------------------- #
# `do` command flow                                                           #
# --------------------------------------------------------------------------- #


@pytest.fixture
def do_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """Patch every side effect `do` could have; record what was called."""
    calls: dict = {"cleanup": 0, "create_worktree": 0, "claim": 0, "team_ids": []}
    state: dict = {"ticket": None, "visible": True, "error": None}

    class FakeTracker:
        def __init__(self, api_key: str | None = None, team_id: str | None = None) -> None:
            calls["team_ids"].append(team_id)

        def get_ticket(self, ticket_id: str) -> Ticket | None:
            if state["error"]:
                raise state["error"]
            return state["ticket"]

        def team_visible(self) -> bool | None:
            return state["visible"]

    cfg = {
        "tracker": {"type": "linear", "config": {"team_id": TEAM}},
        "branching": {"pattern": "{PROJ}-{num}"},
    }
    monkeypatch.setattr("lib.vibe.config.load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(linear_mod, "LinearTracker", FakeTracker)
    monkeypatch.setattr("lib.vibe.git.worktrees.get_primary_repo_root", lambda: tmp_path)
    monkeypatch.setattr("lib.vibe.git.worktrees.get_worktree_base_path", lambda: tmp_path / "wts")
    monkeypatch.setattr("lib.vibe.git.branches.load_config", lambda: cfg)

    def fake_cleanup(root: Path) -> None:
        calls["cleanup"] += 1

    def fake_create(branch: str, base_branch: str = "main") -> SimpleNamespace:
        calls["create_worktree"] += 1
        calls["branch"] = branch
        return SimpleNamespace(path=str(tmp_path / "wts" / branch))

    monkeypatch.setattr(vibe_main, "_auto_cleanup_worktrees", fake_cleanup)
    monkeypatch.setattr("lib.vibe.git.worktrees.create_worktree", fake_create)
    monkeypatch.setattr("lib.vibe.git.branches.get_main_branch", lambda: "main")
    monkeypatch.setattr("lib.vibe.state.record_ticket_branch", lambda *a, **k: None)
    monkeypatch.setattr(
        vibe_main, "_mark_ticket_in_progress", lambda t, tk: calls.__setitem__("claim", 1)
    )
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr="")
    )
    return {"calls": calls, "state": state}


def _run(*args: str):
    return CliRunner().invoke(vibe_main.main, ["do", *args])


def _no_side_effects(calls: dict) -> bool:
    return calls["cleanup"] == 0 and calls["create_worktree"] == 0 and calls["claim"] == 0


def test_do_unknown_ticket_exits_1_with_no_side_effects(do_env: dict) -> None:
    result = _run("CITY-99999")
    assert result.exit_code == 1
    assert "ticket not found" in result.output
    assert _no_side_effects(do_env["calls"])


def test_do_tracker_error_exits_1_with_no_side_effects(do_env: dict) -> None:
    do_env["state"]["error"] = RuntimeError("LINEAR_API_KEY not set.")
    result = _run("CITY-641")
    assert result.exit_code == 1
    assert "LINEAR_API_KEY not set" in result.output
    assert _no_side_effects(do_env["calls"])


def test_do_passes_configured_team_id(do_env: dict) -> None:
    _run("CITY-99999")
    assert TEAM in do_env["calls"]["team_ids"]


def test_do_invisible_team_says_so(do_env: dict) -> None:
    do_env["state"]["visible"] = False
    result = _run("CITY-641")
    assert result.exit_code == 1
    assert "cannot see the configured Linear team" in result.output


def test_do_force_on_unknown_ticket_proceeds_without_claim(do_env: dict) -> None:
    result = _run("CITY-99999", "--force")
    assert result.exit_code == 0, result.output
    c = do_env["calls"]
    assert c["create_worktree"] == 1 and c["claim"] == 0
    assert "WITHOUT claiming" in result.output


def test_do_creates_bare_ticket_branch_and_claims(do_env: dict) -> None:
    do_env["state"]["ticket"] = _ticket()
    result = _run("CITY-641")
    assert result.exit_code == 0, result.output
    c = do_env["calls"]
    assert c["branch"] == "CITY-641"
    assert c["cleanup"] == 1 and c["claim"] == 1


def test_do_refuses_already_started_ticket(do_env: dict) -> None:
    do_env["state"]["ticket"] = _ticket(status="In Progress", status_type="started")
    result = _run("CITY-641")
    assert result.exit_code == 1
    assert "--force" in result.output
    assert _no_side_effects(do_env["calls"])


def test_do_force_claims_already_started_ticket(do_env: dict) -> None:
    do_env["state"]["ticket"] = _ticket(status="In Progress", status_type="started")
    result = _run("CITY-641", "--force")
    assert result.exit_code == 0, result.output
    assert do_env["calls"]["create_worktree"] == 1 and do_env["calls"]["claim"] == 1


def test_do_dry_run_prints_branch_and_changes_nothing(do_env: dict) -> None:
    do_env["state"]["ticket"] = _ticket()
    result = _run("CITY-641", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "Branch: CITY-641\n" in result.output
    assert "wts/CITY-641" in result.output
    assert _no_side_effects(do_env["calls"])


# --------------------------------------------------------------------------- #
# Already-started guard + claim                                               #
# --------------------------------------------------------------------------- #


def test_guard_allows_fresh_and_terminal_tickets() -> None:
    assert _already_started_guard_message(_ticket(status="Todo")) is None
    assert _already_started_guard_message(_ticket(status="Backlog")) is None
    assert _already_started_guard_message(_ticket(status="Done")) is None


def test_guard_blocks_started_tickets_and_names_assignee() -> None:
    msg = _already_started_guard_message(_ticket(status="In Review", assignee="Kevin"))
    assert msg is not None and "--force" in msg and "Kevin" in msg
    # Custom state name, started by type.
    assert _already_started_guard_message(_ticket(status="Doing", status_type="started"))


def test_fresh_ticket_is_moved_and_assigned() -> None:
    tracker = MagicMock()
    _mark_ticket_in_progress(tracker, _ticket(status="Todo"))
    tracker.update_ticket.assert_called_once_with("CITY-641", status="In Progress", assignee="me")


def test_started_ticket_is_only_reassigned() -> None:
    tracker = MagicMock()
    _mark_ticket_in_progress(tracker, _ticket(status="In Review"))
    tracker.update_ticket.assert_called_once_with("CITY-641", assignee="me")


def test_terminal_ticket_is_untouched() -> None:
    tracker = MagicMock()
    _mark_ticket_in_progress(tracker, _ticket(status="Done", status_type="completed"))
    tracker.update_ticket.assert_not_called()


def test_claim_failure_is_reported_not_raised() -> None:
    tracker = MagicMock()
    tracker.update_ticket.side_effect = RuntimeError("API down")
    _mark_ticket_in_progress(tracker, _ticket(status="Todo"))  # must not raise
