"""Guards for the lint gate configuration (CITY-651).

`ruff format` output can change between ruff releases, so the version CI runs
must be pinned, and must be the same one the dev extra installs locally.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINT_WORKFLOW = ROOT / ".github" / "workflows" / "lint.yml"


def _dev_ruff_pin() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    pins = [d for d in data["project"]["optional-dependencies"]["dev"] if d.startswith("ruff")]
    assert len(pins) == 1, pins
    match = re.fullmatch(r"ruff==(\d+\.\d+\.\d+)", pins[0])
    assert match, f"dev extra must pin ruff exactly (ruff==X.Y.Z), got {pins[0]!r}"
    return match.group(1)


def test_ci_ruff_pin_matches_dev_extra() -> None:
    workflow = LINT_WORKFLOW.read_text()
    ci_pins = re.findall(r"ruff==(\d+\.\d+\.\d+)", workflow)
    assert ci_pins, "lint.yml must install an exact ruff version"
    assert set(ci_pins) == {_dev_ruff_pin()}
    # No unpinned install sneaking in alongside the pinned one.
    assert not re.search(r"pip install[^\n]*\bruff\b(?!==)", workflow)
