"""CITY-641: the Linear tracker and `bin/ticket` fail loudly instead of looking empty.

Before: with LINEAR_API_KEY missing or invalid, `bin/ticket list` printed
"No tickets found" and exited 0, and `bin/ticket labels` printed "No labels found"
even with a valid key (its query failed GraphQL validation and the error was dropped).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lib.vibe.cli import ticket as ticket_cli
from lib.vibe.trackers.linear import LinearTracker, _format_graphql_errors

TEAM = "48a87c3c-6f07-4af2-b5aa-4e100919ba26"


def _response(status: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    if status >= 400:
        import requests

        resp.raise_for_status.side_effect = requests.HTTPError(f"{status} Client Error")
    return resp


AUTH_ERROR = {
    "errors": [
        {
            "message": "Authentication required, not authenticated",
            "extensions": {
                "code": "AUTHENTICATION_ERROR",
                "userPresentableMessage": "You need to authenticate to access this operation.",
            },
        }
    ]
}


# --- tracker ------------------------------------------------------------------


def test_missing_key_raises_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    tracker = LinearTracker(team_id=TEAM)
    with patch("lib.vibe.trackers.linear.requests.post") as post:
        with pytest.raises(RuntimeError, match="LINEAR_API_KEY not set"):
            tracker.list_tickets()
        with pytest.raises(RuntimeError, match="LINEAR_API_KEY not set"):
            tracker.list_labels()
        with pytest.raises(RuntimeError, match="LINEAR_API_KEY not set"):
            tracker.get_ticket("CITY-1")
    post.assert_not_called()


def test_invalid_key_raises_clear_error() -> None:
    tracker = LinearTracker(api_key="lin_api_bogus", team_id=TEAM)
    with patch("lib.vibe.trackers.linear.requests.post", return_value=_response(401, AUTH_ERROR)):
        with pytest.raises(RuntimeError, match=r"rejected LINEAR_API_KEY \(HTTP 401\)"):
            tracker.list_tickets()


def test_graphql_errors_on_http_200_raise() -> None:
    tracker = LinearTracker(api_key="k", team_id=TEAM)
    body = {"errors": [{"message": "Variable $teamId of type String expecting ID"}]}
    with patch("lib.vibe.trackers.linear.requests.post", return_value=_response(200, body)):
        with pytest.raises(RuntimeError, match="expecting ID"):
            tracker.list_labels()


def test_unknown_ticket_is_none_not_error() -> None:
    tracker = LinearTracker(api_key="k", team_id=TEAM)
    body = {"errors": [{"message": "Entity not found: Issue"}], "data": None}
    with patch("lib.vibe.trackers.linear.requests.post", return_value=_response(200, body)):
        assert tracker.get_ticket("CITY-99999") is None


def test_authenticate_returns_false_on_bad_key() -> None:
    tracker = LinearTracker(api_key="lin_api_bogus", team_id=TEAM)
    with patch("lib.vibe.trackers.linear.requests.post", return_value=_response(401, AUTH_ERROR)):
        assert tracker.authenticate() is False


def test_team_visible() -> None:
    tracker = LinearTracker(api_key="k", team_id=TEAM)
    with patch.object(tracker, "_execute_query", return_value={"data": {"team": {"id": TEAM}}}):
        assert tracker.team_visible() is True
    with patch.object(
        tracker, "_execute_query", side_effect=RuntimeError("Entity not found: Team")
    ):
        assert tracker.team_visible() is False
    assert LinearTracker(api_key="k").team_visible() is None


def test_format_graphql_errors_unwraps_presentable_message() -> None:
    assert _format_graphql_errors(AUTH_ERROR["errors"]) == (
        "Authentication required, not authenticated: "
        "You need to authenticate to access this operation."
    )
    assert _format_graphql_errors(None) == "Unknown error"


# --- bin/ticket CLI -------------------------------------------------------------


@pytest.fixture
def keyless_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    monkeypatch.setattr(
        ticket_cli, "ensure_tracker_configured", lambda: LinearTracker(team_id=TEAM)
    )


@pytest.mark.parametrize("args", [["list"], ["labels"], ["get", "CITY-1"]])
def test_cli_missing_key_exits_1_with_message(keyless_cli: None, args: list[str]) -> None:
    result = CliRunner().invoke(ticket_cli.main, args)
    assert result.exit_code == 1, result.output
    assert "LINEAR_API_KEY not set" in result.output
    assert "No tickets found" not in result.output
    assert "No labels found" not in result.output


def test_cli_labels_lists_team_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    tracker = LinearTracker(api_key="k", team_id=TEAM)
    body = {
        "data": {
            "team": {
                "labels": {
                    "nodes": [
                        {"id": "l1", "name": "Infra", "color": "#000"},
                        {"id": "l2", "name": "Improvement", "color": "#fff"},
                    ]
                }
            }
        }
    }
    monkeypatch.setattr(ticket_cli, "ensure_tracker_configured", lambda: tracker)
    with patch("lib.vibe.trackers.linear.requests.post", return_value=_response(200, body)):
        result = CliRunner().invoke(ticket_cli.main, ["labels"])
    assert result.exit_code == 0, result.output
    assert "Infra" in result.output and "Improvement" in result.output


def test_cli_empty_list_with_invisible_team_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    tracker = MagicMock()
    tracker.list_tickets.return_value = []
    tracker.team_visible.return_value = False
    tracker._team_id = TEAM
    monkeypatch.setattr(ticket_cli, "ensure_tracker_configured", lambda: tracker)
    result = CliRunner().invoke(ticket_cli.main, ["list"])
    assert result.exit_code == 1
    assert "cannot see the configured Linear team" in result.output


def test_cli_genuinely_empty_list_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    tracker = MagicMock()
    tracker.list_tickets.return_value = []
    tracker.team_visible.return_value = True
    monkeypatch.setattr(ticket_cli, "ensure_tracker_configured", lambda: tracker)
    result = CliRunner().invoke(ticket_cli.main, ["list"])
    assert result.exit_code == 0
    assert "No tickets found" in result.output


# --- project resolution never silently drops a filter (CodeRabbit #472) ----------


def test_unknown_project_raises_instead_of_dropping_filter() -> None:
    tracker = LinearTracker(api_key="k", team_id=TEAM)
    with patch.object(tracker, "list_projects", return_value=[]):
        with pytest.raises(RuntimeError, match="Project not found: Roadmap"):
            tracker.list_tickets(project="Roadmap")


def test_list_projects_propagates_api_errors() -> None:
    tracker = LinearTracker(api_key="k", team_id=TEAM)
    with patch.object(tracker, "_execute_query", side_effect=RuntimeError("Linear API error")):
        with pytest.raises(RuntimeError, match="Linear API error"):
            tracker.list_projects()


def test_get_project_falls_back_to_name_only_on_not_found() -> None:
    from lib.vibe.trackers.base import Project

    tracker = LinearTracker(api_key="k", team_id=TEAM)
    proj = Project(id="p1", name="Roadmap", description="", state="started", url="", raw={})
    with (
        patch.object(
            tracker, "_execute_query", side_effect=RuntimeError("Entity not found: Project")
        ),
        patch.object(tracker, "list_projects", return_value=[proj]),
    ):
        assert tracker.get_project("Roadmap") == proj
    with patch.object(
        tracker, "_execute_query", side_effect=RuntimeError("Linear rejected LINEAR_API_KEY")
    ):
        with pytest.raises(RuntimeError, match="LINEAR_API_KEY"):
            tracker.get_project("Roadmap")
