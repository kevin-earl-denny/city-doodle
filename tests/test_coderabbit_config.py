"""Guard tests for .coderabbit.yaml (CITY-636).

CodeRabbit silently ignores settings it can't use: a path_instructions glob that
matches nothing looks exactly like a live one, and an over-long tone is
truncated. These tests make those failures loud.
"""

import fnmatch
import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((REPO_ROOT / ".coderabbit.yaml").read_text())


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def _expand_braces(pattern: str) -> list[str]:
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end() :]
    return [
        expanded
        for option in match.group(1).split(",")
        for expanded in _expand_braces(head + option + tail)
    ]


def test_tone_instructions_within_coderabbit_cap():
    assert len(CONFIG["tone_instructions"]) <= 250


def test_merge_bar_settings():
    # The merge bar counts CodeRabbit's APPROVED review; COMMENTED reviews can't count.
    reviews = CONFIG["reviews"]
    assert reviews["request_changes_workflow"] is True
    assert reviews["auto_review"]["enabled"] is True


def test_every_path_instruction_matches_a_tracked_file():
    files = _tracked_files()
    dead = [
        entry["path"]
        for entry in CONFIG["reviews"]["path_instructions"]
        if not any(
            fnmatch.fnmatch(f, pattern) for pattern in _expand_braces(entry["path"]) for f in files
        )
    ]
    assert not dead, f"path_instructions globs match no tracked file: {dead}"
