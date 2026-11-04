"""Regression tests for .githooks/, bin/migrations and the head-guard workflow (CITY-666).

The hooks run against throwaway git repos in tmp_path, never this checkout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PRE_COMMIT = ROOT / ".githooks" / "pre-commit"
PRE_PUSH = ROOT / ".githooks" / "pre-push"
MIGRATIONS = ROOT / "bin" / "migrations"
HEAD_GUARD = ROOT / ".github" / "workflows" / "migrations-head-guard.yml"
ZERO = "0" * 40

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None, reason="needs bash and git"
)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    # Deterministic git identity; ruff from this interpreter's venv first.
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
        GIT_CONFIG_GLOBAL=os.devnull,
        PATH=f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}",
    )
    return env


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, env=_env(), check=True, capture_output=True, text=True
    ).stdout.strip()


def _run(cmd: list[str], cwd: Path, stdin: str = "", **env: str):
    return subprocess.run(
        cmd, cwd=cwd, input=stdin, env={**_env(), **env}, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "README.md").write_text("x\n")
    # pre-commit runs gitleaks with this config when gitleaks is installed.
    shutil.copy(ROOT / ".gitleaks.toml", r / ".gitleaks.toml")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "init")
    return r


# ── pre-commit ────────────────────────────────────────────────────────────────


def _stage(repo: Path, rel: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("SECRET=1\n")
    _git(repo, "add", "-f", "--", rel)


@pytest.mark.parametrize(
    ("rel", "blocked"),
    [
        ("données/.env", True),  # was C-quoted past the guard before -z
        (".env.production", True),
        ("dir é/.env.local", True),
        ("données/.env.example", False),
        (".envrc", False),
    ],
)
def test_pre_commit_env_guard(repo: Path, rel: str, blocked: bool) -> None:
    _stage(repo, rel)
    result = _run(["bash", str(PRE_COMMIT)], repo)
    assert (result.returncode == 1) is blocked, result.stderr
    assert ("refusing to commit an env file" in result.stderr) is blocked


def test_pre_commit_fails_closed_when_listing_fails(repo: Path, tmp_path: Path) -> None:
    _stage(repo, "données/.env")
    bad_index = tmp_path / "corrupt-index"
    bad_index.write_text("not an index")
    result = _run(["bash", str(PRE_COMMIT)], repo, GIT_INDEX_FILE=str(bad_index))
    assert result.returncode == 1
    assert "could not list staged files" in result.stderr


# ── pre-push ──────────────────────────────────────────────────────────────────

needs_ruff = pytest.mark.skipif(
    shutil.which("ruff", path=_env()["PATH"]) is None, reason="needs ruff"
)


@pytest.fixture
def py_repo(repo: Path) -> Path:
    (repo / "pyproject.toml").write_text('[tool.ruff.lint]\nselect = ["F"]\n')
    (repo / "lib").mkdir()
    (repo / "lib" / "ok.py").write_text("X = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "py")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def _commit_off_branch(repo: Path, rel: str, content: str) -> str:
    """Commit `content` at `rel` on a detached commit, then return to main."""
    _git(repo, "checkout", "-q", "--detach")
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-qm", rel)
    sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    return sha


def _push(repo: Path, *shas: str):
    stdin = "".join(f"refs/heads/r{i} {s} refs/heads/r{i} {ZERO}\n" for i, s in enumerate(shas))
    return _run(["bash", str(PRE_PUSH)], repo, stdin)


@needs_ruff
def test_pre_push_checks_pushed_ref_not_working_tree(py_repo: Path) -> None:
    # The broken commit is not checked out; the working tree is clean.
    bad = _commit_off_branch(py_repo, "lib/bad.py", "import os\n")
    result = _push(py_repo, bad)
    assert result.returncode == 1, result.stdout
    assert "ruff check" in result.stdout


@needs_ruff
def test_pre_push_ignores_uncommitted_edits(py_repo: Path) -> None:
    good = _commit_off_branch(py_repo, "lib/good.py", "Y = 2\n")
    (py_repo / "lib" / "ok.py").write_text("import os\n")  # dirty, not pushed
    result = _push(py_repo, good)
    assert result.returncode == 0, result.stdout


@needs_ruff
def test_pre_push_lints_non_ascii_paths(py_repo: Path) -> None:
    bad = _commit_off_branch(py_repo, "lib/donnée_é.py", "import os\n")
    result = _push(py_repo, bad)
    assert result.returncode == 1, result.stdout
    assert "ruff check" in result.stdout


@needs_ruff
def test_pre_push_skips_a_tree_it_already_checked(py_repo: Path) -> None:
    good = _commit_off_branch(py_repo, "lib/good.py", "Y = 2\n")
    result = _push(py_repo, good, good)
    assert result.returncode == 0, result.stdout
    assert result.stdout.count("ruff (") == 1
    assert "skipping" in result.stdout


def test_pre_push_fails_closed_when_diff_fails(py_repo: Path) -> None:
    # A sha git can't resolve: the diff listing fails and must block the push.
    result = _push(py_repo, "1234567890abcdef1234567890abcdef12345678")
    assert result.returncode == 1
    assert "git diff failed" in result.stdout


def _commit_on_main(repo: Path, rel: str, content: str) -> None:
    """Commit onto main and move origin/main with it (an already-merged file)."""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-qm", rel)
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")


@needs_ruff
def test_pre_push_lints_files_the_push_did_not_touch(py_repo: Path) -> None:
    # CITY-651: lint is whole-tree. A lint error already on main, in a file
    # this push doesn't change, still blocks once any Python file changes.
    _commit_on_main(py_repo, "lib/legacy.py", "import os\n")
    good = _commit_off_branch(py_repo, "lib/good.py", "Y = 2\n")
    result = _push(py_repo, good)
    assert result.returncode == 1, result.stdout
    assert "lib/legacy.py" in result.stdout
    assert "ruff (whole tree: lib)" in result.stdout


@needs_ruff
def test_pre_push_ruff_config_change_relints_the_tree(py_repo: Path) -> None:
    # Tightening the ruff config touches no .py file but can break any of them.
    _commit_on_main(py_repo, "lib/legacy.py", "def f(l):\n    return l\n")
    stricter = _commit_off_branch(
        py_repo, "pyproject.toml", '[tool.ruff.lint]\nselect = ["F", "E741"]\n'
    )
    result = _push(py_repo, stricter)
    assert result.returncode == 1, result.stdout
    assert "E741" in result.stdout


@needs_ruff
def test_pre_push_skips_lint_when_no_python_changed(py_repo: Path) -> None:
    _commit_on_main(py_repo, "lib/legacy.py", "import os\n")
    docs = _commit_off_branch(py_repo, "docs/notes.md", "notes\n")
    result = _push(py_repo, docs)
    assert result.returncode == 0, result.stdout
    assert "ruff (" not in result.stdout


@needs_ruff
def test_pre_push_warns_when_local_ruff_differs_from_pin(py_repo: Path) -> None:
    pinned = _commit_off_branch(
        py_repo,
        "pyproject.toml",
        '[project.optional-dependencies]\ndev = ["ruff==0.0.1"]\n\n'
        '[tool.ruff.lint]\nselect = ["F"]\n',
    )
    result = _push(py_repo, pinned)
    assert result.returncode == 0, result.stdout
    assert "but CI pins 0.0.1" in result.stdout


# ── bin/migrations ────────────────────────────────────────────────────────────

_MIGRATION = 'revision = "{rev}"\ndown_revision = {down}\n'


def _migrations_tree(tmp_path: Path, revisions: dict[str, str]) -> Path:
    tree = tmp_path / "mig"
    (tree / "bin").mkdir(parents=True)
    shutil.copy(MIGRATIONS, tree / "bin" / "migrations")
    versions = tree / "apps" / "api" / "alembic" / "versions"
    versions.mkdir(parents=True)
    for name, body in revisions.items():
        (versions / name).write_text(body)
    return tree


@pytest.mark.parametrize(
    "down",
    ['"0xx_missing"', '("001", "nope")'],
    ids=["string-parent", "merge-tuple-parent"],
)
def test_migrations_dangling_down_revision_exits_1(tmp_path: Path, down: str) -> None:
    tree = _migrations_tree(
        tmp_path,
        {
            "001_a.py": _MIGRATION.format(rev="001", down="None"),
            "002_b.py": _MIGRATION.format(rev="002", down=down),
        },
    )
    # ALEMBIC_CMD would fail (exit 2) if reached: the dangling check must come first.
    result = _run(
        ["bash", str(tree / "bin" / "migrations"), "check"], tree, ALEMBIC_CMD="/nonexistent"
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "002_b.py" in result.stdout


# ── head-guard workflow ───────────────────────────────────────────────────────


def test_head_guard_runs_on_retarget_and_pins_deps() -> None:
    data = yaml.safe_load(HEAD_GUARD.read_text())
    on = data.get(True, data.get("on"))  # YAML 1.1 reads `on:` as True
    assert "edited" in on["pull_request"]["types"]  # base retargeted to main
    install = next(
        step["run"]
        for step in data["jobs"]["guard"]["steps"]
        if "pip install" in step.get("run", "")
    )
    for pin in ('"alembic>=1.13,<2"', '"sqlalchemy[asyncio]>=2.0,<2.2"'):
        assert pin in install
