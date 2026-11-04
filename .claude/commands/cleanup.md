---
description: Clean up worktrees whose Linear ticket is complete (ticket-aware, never by merge status)
---

# /cleanup - Clean up finished worktrees

Remove worktrees whose ticket is complete, using `bin/vibe cleanup`.

## Usage

```
/cleanup
/cleanup --dry-run
/cleanup --force
```

## What it does

Runs `bin/vibe cleanup`, the ticket-aware cleanup (`lib/vibe/git/worktree_cleanup.py`). A worktree is removed **only** when all of these hold:

1. its branch carries a ticket id and that Linear ticket is terminal (Done / Canceled),
2. it has no uncommitted changes, and
3. it's provably older than the 30-minute grace period.

Anything ambiguous — no ticket id, Linear unreachable, ticket not found, unknown creation time — is **kept**.

**Never decide staleness from `git branch --merged`.** A fresh branch with zero commits looks "merged" while its ticket is still active, and that's how concurrent agents' worktrees get destroyed.

## Instructions

When the user invokes `/cleanup`:

1. Preview: `bin/vibe cleanup --dry-run`. It lists what would be removed and why each kept worktree is kept.
2. Show the user the list. Unless they passed `--force`, confirm before removing.
3. Run `bin/vibe cleanup` (add `--force` only if the user asked). It runs `bin/vibe doctor` afterwards to sync state.
4. Report what was removed and what was kept, with reasons.

Branch deletion is conservative: `git branch -d` first; `-D` only when the branch tip already exists on a remote. A branch with unpushed commits is kept and reported, never deleted. `git worktree remove` runs without `--force`, so a worktree that turned dirty after classification is still refused.

## Safety checks

- Never remove worktrees with uncommitted changes or a non-terminal ticket
- Never hand-run `git worktree remove` / `git branch -D` on a guess — use `bin/vibe cleanup`
- Always confirm before removing (unless `--force`)

## Example

```
Complete (safe to remove): 2
  CITY-123 — CITY-123 is 'Done'
  CITY-124 — CITY-124 is 'Canceled'

Kept: 2
  CITY-125 — CITY-125 is 'In Progress' (active)
  CITY-126 — has uncommitted changes

Cleaned up 2 worktree(s).
```

## Related

- `/doctor` - Check for stale worktrees
- `/do` - Create new worktrees (also auto-runs this cleanup)
