"""GitHub workflow hardening guards (CITY-640).

- Every `uses:` is `owner/repo@<40-hex sha> # vX.Y.Z`, so a tag can't be moved
  under us and Dependabot bumps stay reviewable.
- Every workflow declares top-level `permissions:` (least privilege instead of
  the repo default token scope).
- Every job has `timeout-minutes` (the default is 6 hours).
- No job runs on `ubuntu-latest`: the image moves under us (26.04 broke
  Playwright installs, CITY-649), so runners are pinned to a version.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))

USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")


def unpinned_uses(text: str) -> list[str]:
    """Return `uses:` lines that aren't SHA-pinned with a version comment."""
    bad = []
    for n, line in enumerate(text.splitlines(), 1):
        m = USES_RE.match(line)
        if not m or m.group(1).startswith("./"):
            continue
        ref, rest = m.group(1), m.group(2)
        sha = ref.rsplit("@", 1)[-1] if "@" in ref else ""
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.search(r"#\s*v\d", rest):
            bad.append(f"{n}: {line.strip()}")
    return bad


def test_workflows_exist() -> None:
    assert WORKFLOWS, "no workflows found; is ROOT wrong?"


def test_every_action_is_sha_pinned_with_version_comment() -> None:
    bad = [f"{wf.name}:{b}" for wf in WORKFLOWS for b in unpinned_uses(wf.read_text())]
    assert not bad, "actions must be `owner/repo@<40-hex sha> # vX.Y.Z`:\n" + "\n".join(bad)


@pytest.mark.parametrize(
    "line",
    [
        "      - uses: actions/checkout@v6",
        "        uses: actions/checkout@main # v6",
        "        uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
        "        uses: actions/checkout",
    ],
)
def test_pin_check_rejects_unpinned(line: str) -> None:
    assert unpinned_uses(line)


@pytest.mark.parametrize(
    "line",
    [
        "      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0",
        "        uses: ./.github/actions/local",
        "        run: echo 'uses: actions/checkout@v6'",
    ],
)
def test_pin_check_accepts_pinned_and_local(line: str) -> None:
    assert not unpinned_uses(line)


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_declares_permissions(wf: Path) -> None:
    data = yaml.safe_load(wf.read_text())
    assert "permissions" in data, f"{wf.name}: add a top-level `permissions:` block"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_timeout_and_pinned_runner(wf: Path) -> None:
    data = yaml.safe_load(wf.read_text())
    problems = []
    for name, job in data.get("jobs", {}).items():
        if "uses" in job:  # reusable-workflow call: no runner of its own
            continue
        if "timeout-minutes" not in job:
            problems.append(f"{name}: missing timeout-minutes")
        if "latest" in str(job.get("runs-on", "")):
            problems.append(f"{name}: runs-on {job['runs-on']!r}; pin a version (ubuntu-24.04)")
    assert not problems, f"{wf.name}:\n" + "\n".join(problems)
