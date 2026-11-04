"""GitHub workflow hardening guards (CITY-640).

- Every action reference (job-level `uses:` and step `uses:`) is
  `owner/repo@<40-hex sha>` with a `# vX.Y.Z` comment on the same line, so a
  tag can't be moved under us and Dependabot bumps stay reviewable.
- Every workflow and every job declares `permissions:` explicitly, and none
  uses the `write-all` / `read-all` shorthands.
- Every job has `timeout-minutes` (the default is 6 hours).
- No job runs on a `*-latest` image: it moves under us (ubuntu-latest became
  26.04 and broke Playwright installs, CITY-649).

`uses:` values come from the parsed YAML, so quoted keys (`'uses': ...`) or
flow-style steps can't slip past a line regex.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))

SHA_REF_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
VERSION_COMMENT_RE = re.compile(r"#\s*v\d")


def action_refs(workflow: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (location, uses-value) for every job and step `uses` in a workflow."""
    refs = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        if "uses" in job:
            refs.append((f"jobs.{job_name}", str(job["uses"])))
        for i, step in enumerate(job.get("steps") or []):
            if isinstance(step, dict) and "uses" in step:
                refs.append((f"jobs.{job_name}.steps[{i}]", str(step["uses"])))
    return refs


def pin_problems(text: str) -> list[str]:
    """Return a description of every action reference in `text` that isn't pinned."""
    problems = []
    lines = text.splitlines()
    for where, ref in action_refs(yaml.safe_load(text)):
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        if not SHA_REF_RE.fullmatch(ref):
            problems.append(f"{where}: {ref!r} is not owner/repo@<40-hex sha>")
            continue
        # The version comment lives on the source line holding this exact ref.
        holders = [line for line in lines if ref in line]
        if not holders or not all(VERSION_COMMENT_RE.search(line) for line in holders):
            problems.append(f"{where}: {ref!r} has no `# vX.Y.Z` comment")
    return problems


def test_workflows_exist() -> None:
    assert WORKFLOWS, "no workflows found; is ROOT wrong?"


def test_every_action_is_sha_pinned_with_version_comment() -> None:
    bad = [f"{wf.name}: {p}" for wf in WORKFLOWS for p in pin_problems(wf.read_text())]
    assert not bad, "actions must be `owner/repo@<40-hex sha> # vX.Y.Z`:\n" + "\n".join(bad)


SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"


def _wf(steps: str) -> str:
    return f"on: push\njobs:\n  a:\n    runs-on: ubuntu-24.04\n    steps:\n{steps}"


@pytest.mark.parametrize(
    "steps",
    [
        "      - uses: actions/checkout@v6\n",
        "      - uses: actions/checkout@main # v6\n",
        f"      - uses: actions/checkout@{SHA}\n",
        "      - uses: actions/checkout\n",
        "      - 'uses': actions/checkout@v6\n",
        '      - {"uses": "actions/checkout@v6"}\n',
        f"      - uses: actions/checkout@{SHA[:39]} # v6.1.0\n",
    ],
)
def test_pin_check_rejects_unpinned(steps: str) -> None:
    assert pin_problems(_wf(steps))


def test_pin_check_rejects_unpinned_reusable_workflow() -> None:
    text = "on: push\njobs:\n  a:\n    uses: org/repo/.github/workflows/x.yml@main\n"
    assert pin_problems(text)


@pytest.mark.parametrize(
    "steps",
    [
        f"      - uses: actions/checkout@{SHA} # v6.1.0\n",
        f"      - 'uses': actions/checkout@{SHA} # v6.1.0\n",
        "      - uses: ./.github/actions/local\n",
        "      - run: \"echo 'uses: actions/checkout@v6'\"\n",
    ],
)
def test_pin_check_accepts_pinned_and_local(steps: str) -> None:
    assert not pin_problems(_wf(steps))


def _permission_problems(where: str, perms: Any) -> list[str]:
    if isinstance(perms, str):
        return [f"{where}: `permissions: {perms}` shorthand; list scopes explicitly"]
    return []


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_and_every_job_declare_permissions(wf: Path) -> None:
    data = yaml.safe_load(wf.read_text())
    problems = []
    if "permissions" not in data:
        problems.append("top level: missing `permissions:`")
    else:
        problems += _permission_problems("top level", data["permissions"])
    for name, job in (data.get("jobs") or {}).items():
        if "permissions" not in job:
            problems.append(f"jobs.{name}: missing job-level `permissions:`")
        else:
            problems += _permission_problems(f"jobs.{name}", job["permissions"])
    assert not problems, f"{wf.name}:\n" + "\n".join(problems)


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_timeout_and_pinned_runner(wf: Path) -> None:
    data = yaml.safe_load(wf.read_text())
    problems = []
    for name, job in (data.get("jobs") or {}).items():
        if "uses" in job:  # reusable-workflow call: no runner of its own
            continue
        if "timeout-minutes" not in job:
            problems.append(f"{name}: missing timeout-minutes")
        if "latest" in str(job.get("runs-on", "")):
            problems.append(f"{name}: runs-on {job['runs-on']!r}; pin a version (ubuntu-24.04)")
    assert not problems, f"{wf.name}:\n" + "\n".join(problems)


@pytest.mark.parametrize("perms", ["write-all", "read-all"])
def test_permission_shorthands_are_rejected(perms: str) -> None:
    assert _permission_problems("jobs.a", perms)


def test_explicit_permission_scopes_are_accepted() -> None:
    assert not _permission_problems("jobs.a", {"contents": "read"})
    assert not _permission_problems("jobs.a", {})
