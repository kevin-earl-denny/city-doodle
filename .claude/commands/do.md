---
description: Start working on a ticket by creating a dedicated git worktree and branch
---

# /do - Start working on a ticket

Start working on a ticket by creating a dedicated git worktree and branch.

## Usage

```
/do CITY-123
/do CITY-123 --dry-run   # show branch + worktree, change nothing
/do CITY-123 -f          # --force: claim a ticket already In Progress / In Review
```

## What it does

1. **Validates the ticket first** — fetches it from Linear before any side effect
2. Auto-cleans *completed* worktrees (ticket-aware; see `/cleanup`)
3. Fetches the latest `origin/main`
4. Creates a worktree at `../<repo>-worktrees/CITY-123/` on branch `CITY-123` — exactly the ticket id, no title slug (a slug is only added if `.vibe/config.json`'s `branching.pattern` contains `{title}`)
5. Records the worktree in `.vibe/local_state.json`
6. **Claims the ticket** — moves it to **In Progress** and **assigns it to you**. That status is the "hands off" signal worktree cleanup keys off, so concurrent agents never sweep each other's worktrees.

### Ticket-not-found guard

If the ticket can't be found, `LINEAR_API_KEY` is missing/invalid, or the key can't see the CITY team, `bin/vibe do` exits 1 and changes nothing. `--force` creates the worktree anyway for a not-found ticket, but **without** claiming anything. It does not override a missing/invalid key or a key that can't see the team; those always exit 1. `--dry-run` prints the branch and worktree path and changes nothing.

### Already-started guard

If the ticket is **already started** (In Progress / In Review), `bin/vibe do` **refuses** before creating a worktree — another agent may already be working it — and prints the status + assignee. Re-run with `--force` to claim it anyway: a forced claim reassigns the ticket to you but **leaves its status** (an In Review ticket isn't dragged back to In Progress). Terminal tickets (Done/Canceled/Duplicate/Deployed) are never reopened.

## Instructions

When the user invokes `/do <ticket_id>`:

1. Optionally preview: `bin/vibe do <ticket_id> --dry-run`
2. Run `bin/vibe do <ticket_id>` (it claims the ticket — In Progress + assigned to you)
3. Report the worktree path to the user
4. Remind them to work in that directory (or use absolute paths)
5. Show the ticket details: `bin/ticket get <ticket_id>`
6. **If `do` aborts because the ticket is already started**, surface its status/assignee and ask the user whether to claim it with `--force` — never force automatically

## Example

```bash
bin/vibe do CITY-123
# Found ticket: Fix river connections (Todo)
# Branch: CITY-123
# Worktree created at: ../city-doodle-worktrees/CITY-123
# Moved CITY-123 to In Progress and assigned it to you.
```

## After completing work

When work is done:
1. Commit changes: `git -C <worktree-path> commit -m "CITY-123: Description"`
2. Push branch: `git -C <worktree-path> push -u origin CITY-123`
3. Open PR: `gh pr create --head CITY-123 --title "CITY-123: Title"`

Or use `/pr` to automate PR creation.
