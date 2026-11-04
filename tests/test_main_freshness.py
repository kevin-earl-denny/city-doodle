"""CITY-641 (ported from sarto-db SAR-150): the staleness warning is guarded, because its whole value is firing unprompted.

A check that runs at SessionStart and prints nothing is indistinguishable from a check
that is current, a check that is broken, and a check that is not wired up at all. Nobody
notices it stop. So the tests here build real git repositories on disk and put them into
each state, rather than mocking `git` and proving only that the mock was called.

The `advise()` cases pin behaviour that is easy to regress into bad advice: a diverged
`main` must not be told to run `git pull --ff-only`, because that command refuses to run
on a diverged branch and the reader lands on an error instead of a fix.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_main_freshness import (  # noqa: E402
    advise,
    check,
    current_branch,
    default_branch,
    divergence,
    primary_repo_root,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def commit(repo: Path, message: str) -> None:
    (repo / "file.txt").write_text(message)
    git(repo, "add", "file.txt")
    git(repo, "commit", "-m", message)


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """An `origin` with one commit, and a clone of it. Returns the clone."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "--initial-branch=main")
    git(upstream, "config", "user.email", "test@example.com")
    git(upstream, "config", "user.name", "Test")
    commit(upstream, "one")

    local = tmp_path / "local"
    git(tmp_path, "clone", str(upstream), str(local))
    git(local, "config", "user.email", "test@example.com")
    git(local, "config", "user.name", "Test")
    return local


def advance_upstream(clone_path: Path, count: int) -> None:
    """Add `count` commits to the origin the clone points at, then fetch them."""
    upstream = Path(git(clone_path, "remote", "get-url", "origin"))
    for index in range(count):
        commit(upstream, f"upstream-{index}")
    git(clone_path, "fetch", "origin", "main")


class TestDivergence:
    def test_reports_zero_when_current(self, clone: Path) -> None:
        assert divergence(clone, "main") == (0, 0)

    def test_counts_commits_the_clone_lacks(self, clone: Path) -> None:
        advance_upstream(clone, 4)
        assert divergence(clone, "main") == (4, 0)

    def test_counts_unpushed_commits_as_ahead(self, clone: Path) -> None:
        commit(clone, "local-only")
        assert divergence(clone, "main") == (0, 1)

    def test_reports_both_sides_when_diverged(self, clone: Path) -> None:
        advance_upstream(clone, 2)
        commit(clone, "local-only")
        assert divergence(clone, "main") == (2, 1)

    def test_returns_none_when_the_remote_ref_is_missing(self, tmp_path: Path) -> None:
        solo = tmp_path / "solo"
        solo.mkdir()
        git(solo, "init", "--initial-branch=main")
        git(solo, "config", "user.email", "test@example.com")
        git(solo, "config", "user.name", "Test")
        commit(solo, "one")
        assert divergence(solo, "main") is None


class TestRepoResolution:
    def test_resolves_the_primary_checkout_from_inside_a_worktree(
        self, clone: Path, tmp_path: Path
    ) -> None:
        tree = tmp_path / "wt"
        git(clone, "worktree", "add", "-b", "CITY-641-x", str(tree))
        assert primary_repo_root(tree) == clone.resolve()

    def test_returns_none_outside_a_repository(self, tmp_path: Path) -> None:
        outside = tmp_path / "plain"
        outside.mkdir()
        assert primary_repo_root(outside) is None

    def test_default_branch_falls_back_to_main(self, clone: Path) -> None:
        assert default_branch(clone) == "main"

    def test_current_branch_reports_the_checked_out_branch(self, clone: Path) -> None:
        assert current_branch(clone) == "main"


class TestAdvise:
    """The contract `advise()` must hold, whatever wording it chooses."""

    def test_silent_when_current(self, tmp_path: Path) -> None:
        assert advise(0, 0, "main", "main", tmp_path) is None

    def test_warns_when_behind(self, tmp_path: Path) -> None:
        message = advise(4, 0, "main", "main", tmp_path)
        assert message, "a behind-by-4 checkout must produce a message"
        assert "4" in message, "the message must name how far behind the checkout is"

    def test_recommends_a_runnable_fix_when_plainly_behind(self, tmp_path: Path) -> None:
        message = advise(4, 0, "main", "main", tmp_path)
        assert message is not None
        assert "pull --ff-only" in message

    def test_does_not_recommend_ff_only_when_diverged(self, tmp_path: Path) -> None:
        """`git pull --ff-only` refuses on a diverged branch: it is not a fix here."""
        message = advise(2, 1, "main", "main", tmp_path)
        assert message, "a diverged checkout must still produce a message"
        assert "pull --ff-only" not in message


class TestCheckEndToEnd:
    def test_silent_against_a_current_clone(self, clone: Path) -> None:
        assert check(clone, do_fetch=False) is None

    def test_reports_against_a_stale_clone(self, clone: Path) -> None:
        advance_upstream(clone, 3)
        message = check(clone, do_fetch=False)
        assert message and "3" in message

    def test_survives_a_repo_with_no_remote(self, tmp_path: Path) -> None:
        solo = tmp_path / "solo"
        solo.mkdir()
        git(solo, "init", "--initial-branch=main")
        git(solo, "config", "user.email", "test@example.com")
        git(solo, "config", "user.name", "Test")
        commit(solo, "one")
        assert check(solo, do_fetch=False) is None


class TestNeverBlocks:
    def test_main_exits_zero_outside_a_repository(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts.check_main_freshness import main

        monkeypatch.chdir(tmp_path)
        assert main(["--no-fetch"]) == 0

    def test_main_exits_zero_and_prints_when_stale(
        self, clone: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from scripts.check_main_freshness import main

        advance_upstream(clone, 2)
        monkeypatch.chdir(clone)
        assert main(["--no-fetch"]) == 0
        assert "2 commits behind origin/main" in capsys.readouterr().out

    def test_script_parses_on_python39(self) -> None:
        """The hook runs under the system python3 (3.9 on macOS)."""
        import ast

        source = (REPO_ROOT / "scripts" / "check_main_freshness.py").read_text()
        ast.parse(source, feature_version=(3, 9))


class TestSessionBranch:
    """The advice depends on the session's branch, not the primary checkout's."""

    def test_worktree_session_on_stale_main_gets_worktree_advice(
        self,
        clone: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from scripts.check_main_freshness import main

        tree = tmp_path / "wt"
        git(clone, "worktree", "add", "-b", "CITY-641", str(tree))
        advance_upstream(clone, 2)  # primary checkout stays on `main`
        monkeypatch.chdir(tree)
        assert main(["--no-fetch"]) == 0
        out = capsys.readouterr().out
        assert "you are on CITY-641" in out
        assert "pull --ff-only" not in out

    def test_names_the_session_branch_when_primary_is_elsewhere(
        self,
        clone: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from scripts.check_main_freshness import main

        git(clone, "checkout", "-b", "other-branch")
        tree = tmp_path / "wt"
        git(clone, "worktree", "add", "-b", "CITY-641", str(tree))
        advance_upstream(clone, 1)
        monkeypatch.chdir(tree)
        assert main(["--no-fetch"]) == 0
        out = capsys.readouterr().out
        assert "you are on CITY-641" in out
        assert "other-branch" not in out


class TestWorktreeAdviceAndOffline:
    def test_worktree_advice_names_the_session_branch(self, tmp_path: Path) -> None:
        # `git -C <primary> log HEAD..` would resolve the primary checkout's HEAD.
        message = advise(3, 0, "CITY-641", "main", tmp_path)
        assert message is not None
        assert "CITY-641..origin/main" in message
        assert "HEAD..origin/main" not in message

    def test_detached_head_is_named_and_uses_session_head(self, tmp_path: Path) -> None:
        message = advise(3, 0, "", "main", tmp_path)
        assert message is not None
        assert "detached HEAD" in message
        assert f"-C {tmp_path}" not in message

    def test_current_branch_is_empty_when_detached(self, clone: Path) -> None:
        git(clone, "checkout", "--detach")
        assert current_branch(clone) == ""

    def test_failed_fetch_still_compares_on_disk_refs(self, clone: Path) -> None:
        advance_upstream(clone, 2)  # origin/main already known to be 2 ahead
        git(clone, "remote", "set-url", "origin", str(clone.parent / "gone"))
        message = check(clone, do_fetch=True)
        assert message and "2 commits behind" in message
        assert "fetch failed" in message


class TestDiagnostics:
    def test_unexpected_error_is_reported_on_stderr_and_exits_zero(
        self,
        clone: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import scripts.check_main_freshness as mod

        def boom(*args: object, **kwargs: object) -> None:
            raise ValueError("kaboom")

        monkeypatch.setattr(mod, "check", boom)
        monkeypatch.chdir(clone)
        assert mod.main(["--no-fetch"]) == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "check skipped (ValueError: kaboom)" in captured.err

    def test_silent_outside_a_repository(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from scripts.check_main_freshness import main

        monkeypatch.chdir(tmp_path)
        assert main(["--no-fetch"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "" and captured.err == ""


class TestHookWiring:
    """A correct script that nothing invokes is the failure this ticket exists to fix."""

    def test_settings_registers_the_check_on_session_start(self) -> None:
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
        commands = [
            hook["command"]
            for entry in settings["hooks"]["SessionStart"]
            for hook in entry["hooks"]
        ]
        assert any("check_main_freshness.py" in command for command in commands)

    def test_hook_has_a_timeout(self) -> None:
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
        hooks = [h for e in settings["hooks"]["SessionStart"] for h in e["hooks"]]
        fresh = [h for h in hooks if "check_main_freshness.py" in h["command"]]
        assert fresh and all(h.get("timeout") for h in fresh)

    def test_the_registered_script_exists(self) -> None:
        assert (REPO_ROOT / "scripts" / "check_main_freshness.py").is_file()

    def test_no_blocking_hook_is_registered(self) -> None:
        """Warning-only is the decision. A PreToolUse deny would wedge sessions."""
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
        assert "PreToolUse" not in settings.get("hooks", {})
