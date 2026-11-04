"""Safe worktree cleanup — classify worktrees by their Linear ticket status.

Ported from the sibling vibe repos (foreclosure-finder / sarto-db) for CITY-641.

Background (DEAL-3854): the previous cleanup logic classified a worktree as
stale via `git branch --merged origin/main` (or "branch missing on remote").
A branch created seconds ago has zero unique commits, so git reports it as
already merged — indistinguishable from a genuinely merged branch. Concurrent
agents running `bin/vibe do` therefore destroyed each other's freshly-created,
not-yet-committed worktrees.

The fix: a worktree is removable ONLY on positive proof of completion — its
Linear ticket sits in a terminal workflow state (Done / Deployed / Canceled).
A freshly-created worktree's ticket is still In Progress, so it is never swept.
Three independent guards must all pass before removal:

  1. the branch maps to a Linear ticket in a terminal state,
  2. the worktree has no uncommitted changes, and
  3. the worktree is provably older than a 30-minute grace period (an
     undeterminable age counts as "too new").

`git branch --merged` is never consulted. Every ambiguous case resolves to
"protect" — cleanup must never destroy a worktree it cannot prove is finished.

Because the repo uses native Linear<>GitHub integration, merging a PR moves
its ticket to Done, so "ticket is terminal" is a reliable proxy for "work is
merged" — and, unlike git heuristics, it cannot misfire on a fresh branch.
"""

from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from lib.vibe.state import load_state, remove_worktree

if TYPE_CHECKING:
    from lib.vibe.trackers.base import Ticket, TrackerBase

GRACE_PERIOD_MINUTES = 30

# Linear WorkflowState.type values that mean "work is finished".
TERMINAL_STATE_TYPES = frozenset({"completed", "canceled"})

# Display-name match for "work is finished". Checked IN ADDITION to the
# `type` above (not merely as a fallback): a team's custom "Deployed" state
# has Linear type `started`, yet a Deployed ticket's worktree is done.
TERMINAL_STATE_NAMES = frozenset(
    {"done", "canceled", "cancelled", "complete", "completed", "deployed", "shipped"}
)

# Status names that already mean "an agent has claimed this" — used to avoid
# redundant status writes when starting work on a ticket.
STARTED_STATE_NAMES = frozenset({"in progress", "in review"})

_TICKET_ID_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")


@dataclass
class WorktreeStatus:
    """The cleanup verdict for a single worktree."""

    path: str
    branch: str
    ticket_id: str | None
    decision: str  # "remove" or "protect"
    reason: str

    @property
    def removable(self) -> bool:
        return self.decision == "remove"


def extract_ticket_id(branch: str) -> str | None:
    """Pull a ticket identifier (e.g. ``DEAL-3854``) out of a branch name."""
    match = _TICKET_ID_RE.search(branch or "")
    return match.group(0) if match else None


def is_terminal_status(ticket: Ticket) -> bool:
    """True when the ticket represents finished work.

    Terminal if EITHER Linear's workflow-state ``type`` is completed/canceled,
    OR the display name is a known "done" name. The name check is not merely a
    fallback: a team's custom "Deployed" state has Linear type ``started`` but
    a Deployed ticket's worktree is finished and should be cleaned up.
    """
    if (ticket.status_type or "").strip().lower() in TERMINAL_STATE_TYPES:
        return True
    return ticket.status.strip().lower() in TERMINAL_STATE_NAMES


def is_started_status(ticket: Ticket) -> bool:
    """True when the ticket is already In Progress / In Review."""
    if (ticket.status_type or "").strip().lower() == "started":
        return True
    return ticket.status.strip().lower() in STARTED_STATE_NAMES


def decide_worktree_fate(
    *,
    ticket_id: str | None,
    has_uncommitted_changes: bool,
    age_minutes: float | None,
    ticket: Ticket | None,
) -> tuple[str, str]:
    """Pure decision function — returns ``("remove" | "protect", reason)``.

    Removal requires positive proof the work is done (a terminal ticket).
    Uncommitted changes and the grace period are checked first so that a
    completed ticket can never override unsaved work or a brand-new worktree.
    """
    if not ticket_id:
        return "protect", "branch name carries no ticket id — cannot verify status"
    if has_uncommitted_changes:
        return "protect", "has uncommitted changes"
    if age_minutes is None:
        # Can't prove the worktree is past the grace period -> don't guess.
        return "protect", "creation time unknown — cannot prove it is past the grace period"
    if age_minutes < GRACE_PERIOD_MINUTES:
        return (
            "protect",
            f"created {age_minutes:.0f} min ago (within {GRACE_PERIOD_MINUTES}-min grace period)",
        )
    if ticket is None:
        return "protect", f"could not resolve {ticket_id} in Linear — refusing to guess"
    if is_terminal_status(ticket):
        return "remove", f"{ticket_id} is {ticket.status!r}"
    return "protect", f"{ticket_id} is {ticket.status!r} (active)"


def _has_uncommitted_changes(worktree_path: str) -> bool:
    """True if the worktree is dirty. Failures resolve to True (protect)."""
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError):
        return True
    if result.returncode != 0:
        return True
    return bool(result.stdout.strip())


def _worktree_age_minutes(
    worktree_path: str, repo_root: Path, now: datetime | None = None
) -> float | None:
    """Minutes since the worktree was created, or None if undeterminable.

    Prefers the ``created_at`` recorded by ``bin/vibe do`` in local state;
    falls back to the mtime of the worktree's ``.git`` pointer file (written
    once at ``git worktree add`` time).
    """
    now = now or datetime.now()
    created: datetime | None = None

    try:
        state = load_state(base_path=repo_root)
        target = str(Path(worktree_path).resolve())
        for entries in state.get("ticket_branches", {}).values():
            entry_list = entries if isinstance(entries, list) else [entries]
            for entry in entry_list:
                wt = entry.get("worktree_path")
                ts = entry.get("created_at")
                if not (wt and ts):
                    continue
                if str(Path(wt).resolve()) != target:
                    continue
                parsed = datetime.fromisoformat(ts)
                if created is None or parsed > created:
                    created = parsed
    except (OSError, ValueError, TypeError, AttributeError):
        created = None

    if created is None:
        for candidate in (Path(worktree_path) / ".git", Path(worktree_path)):
            try:
                created = datetime.fromtimestamp(candidate.stat().st_mtime)
                break
            except OSError:
                continue

    if created is None:
        return None
    try:
        return max(0.0, (now - created).total_seconds() / 60.0)
    except TypeError:
        # naive/aware datetime mismatch — treat age as unknown
        return None


def list_feature_worktrees(repo_root: Path) -> list[dict[str, str]]:
    """All non-main worktrees as ``{"path", "branch"}`` dicts."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return []

    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[len("worktree ") :]}
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :].replace("refs/heads/", "")
        elif line == "" and current:
            worktrees.append(current)
            current = {}
    if current:
        worktrees.append(current)

    main_path = str(repo_root.resolve())
    return [
        wt
        for wt in worktrees
        if wt.get("path") and wt.get("branch") and str(Path(wt["path"]).resolve()) != main_path
    ]


def _load_linear_tracker(repo_root: Path) -> TrackerBase | None:
    """Best-effort LinearTracker, or None when it can't be constructed.

    Loads ``.env`` / ``.env.local`` from the *primary* repo root first: this
    code routinely runs from a linked worktree, which has no env file of its
    own, so without this the LINEAR_API_KEY would be missing and every
    worktree would resolve to "protect" (cleanup silently no-ops).
    """
    try:
        from lib.vibe.env import load_env_files
        from lib.vibe.trackers.linear import LinearTracker

        load_env_files(project_root=repo_root)
        return LinearTracker()
    except Exception:
        # No tracker available -> classify_worktrees protects everything.
        return None


def classify_worktrees(
    repo_root: Path,
    *,
    tracker: TrackerBase | None = None,
    now: datetime | None = None,
    max_workers: int = 8,
) -> list[WorktreeStatus]:
    """Classify every feature worktree as ``remove`` or ``protect``.

    Cheap local guards (ticket id, uncommitted changes, grace period) are
    evaluated first; only worktrees that survive them incur a Linear lookup.
    Lookups run concurrently. Any lookup failure resolves to ``protect``.
    """
    worktrees = list_feature_worktrees(repo_root)
    if not worktrees:
        return []

    if tracker is None:
        tracker = _load_linear_tracker(repo_root)

    def _classify(wt: dict[str, str]) -> WorktreeStatus:
        path = wt["path"]
        branch = wt.get("branch", "")
        ticket_id = extract_ticket_id(branch)

        has_changes = _has_uncommitted_changes(path)
        age = _worktree_age_minutes(path, repo_root, now=now)

        ticket: Ticket | None = None
        cheap_guard_decides = (
            not ticket_id or has_changes or age is None or age < GRACE_PERIOD_MINUTES
        )
        if not cheap_guard_decides and tracker is not None and ticket_id:
            try:
                ticket = tracker.get_ticket(ticket_id)
            except Exception:
                # Unreachable tracker -> ticket stays None -> protect. The
                # conservative (non-destructive) outcome is surfaced via the
                # decision reason; nothing is silently swallowed.
                ticket = None

        decision, reason = decide_worktree_fate(
            ticket_id=ticket_id,
            has_uncommitted_changes=has_changes,
            age_minutes=age,
            ticket=ticket,
        )
        return WorktreeStatus(
            path=path,
            branch=branch,
            ticket_id=ticket_id,
            decision=decision,
            reason=reason,
        )

    workers = max(1, min(max_workers, len(worktrees)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_classify, worktrees))


def remove_worktree_and_branch(path: str, branch: str, repo_root: Path) -> tuple[bool, str]:
    """Remove a worktree and delete its local branch.

    ``git worktree remove`` is run *without* ``--force`` so it still refuses
    if the worktree turned dirty between classification and removal — a final
    safety net. Returns ``(ok, message)``.
    """
    try:
        subprocess.run(
            ["git", "worktree", "remove", path],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        return False, f"git worktree remove failed: {(e.stderr or '').strip()}"

    remove_worktree(path, base_path=repo_root)

    def _git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=repo_root)

    if _git("branch", "-d", branch).returncode == 0:
        return True, "removed worktree + branch (-d)"
    # `-d` refused: the branch has commits not merged into HEAD. A terminal ticket
    # doesn't prove those commits exist anywhere else (a Canceled ticket can have
    # unpushed work), so force-delete only when the tip is on a remote.
    on_remote = bool(_git("branch", "-r", "--contains", branch).stdout.strip())
    if on_remote and _git("branch", "-D", branch).returncode == 0:
        return True, "removed worktree + branch (-D, tip exists on a remote)"
    return True, f"removed worktree; kept branch {branch} (has commits not on any remote)"
