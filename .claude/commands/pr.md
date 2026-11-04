---
description: Create a pull request for the current branch with a filled-in body, the review-gate author marker, and ticket linkage
---

# /pr - Create a pull request

Open a pull request for the current branch/worktree.

## Usage

```
/pr
/pr --draft
/pr --title "Custom title"
```

## What it does

1. Ensures all changes are committed
2. Pushes the branch to origin
3. Creates a PR with a filled-in body ending in the review-gate author marker
4. Links to the ticket in the PR description

## Instructions

When the user invokes `/pr`:

1. Check the current branch name for the ticket ID (e.g., `CITY-123`).
2. Ensure changes are committed (prompt if uncommitted changes exist). Stage explicit paths, never `git add -A`.
3. Push the branch: `git push -u origin <branch>`
4. Write the body to a file and create the PR. For a stacked PR, pass the base ticket branch: `--base CITY-122`.
   ```bash
   gh pr create --repo kevin-earl-denny/city-doodle --base main --head <branch> \
     --title "CITY-123: <ticket title>" --body-file <body file>
   ```
   Or `bin/vibe pr --title "..." --body "..." --author <your session id>`, which appends the author marker for you (default id: `$CLAUDE_SESSION_NAME`). With neither, and no marker already in the body, it refuses (exit 1): the id must be the one you review under, or your own reviews would count.

   **Fill in the body.** Don't leave a template skeleton, and keep the prose plain:
   - **Summary**: what changed and why, linked to the ticket.
   - **Changes**: bullets of what changed.
   - **Verification**: what you actually ran and the results (tests, lint, type checks, manual checks). For a frontend-testable change, click-ready manual steps with the expected result per scenario (data present vs absent, empty/loading/error states).
   - **Gotchas**: anything surprising a reviewer or the next agent should know.
   - **Secrets**: new env vars or secrets, or "None".
   - **Cleanup**: cloud resources (Neon branches, Fly apps/machines, docker containers, Vercel deployments/env vars) the work created, each "deleted ✓", or "None".
   - Then `Linear: CITY-123`, then the Claude Code attribution footer.
   - **Last line, exactly:** `<!-- city-author session=<your session id> -->`. One author line only, on its own line; never quote another author marker in the body.
5. **Don't request reviewers.** Review is agents only (review agents + CodeRabbit): never pass `--reviewer`, and never merge your own PR.
6. Report the PR URL and number.

## After opening: the merge bar

The required `review-gate` status (`.github/workflows/review-gate.yml`, rules in `lib/vibe/review_gate.py`) passes when, on the **current head SHA**:

- CodeRabbit's latest state-changing review is **APPROVED**, **or**
- at least **2 distinct agent reviewers** who aren't the PR author posted `pass` or `minor` reviews (PR reviews ending in a `city-agent-review` marker; see `/review`).

Any `major` on the head blocks it until a new head is pushed. A missing or conflicting author marker fails the gate. Every push resets the count; after a pure rebase, carry agent reviews with a `city-rebase-carry` comment (see `/fixup`).

CodeRabbit auto-reviews only the first push of a non-draft PR (`auto_pause_after_reviewed_commits: 1`). After pushing fixes, request a re-review once per round with a PR comment: `@coderabbitai review`.

Check progress any time with `bin/vibe review-gate <n>`: it lists what counted and why the rest didn't.

## Example

```bash
git push -u origin CITY-123
gh pr create --repo kevin-earl-denny/city-doodle --base main --head CITY-123 \
  --title "CITY-123: Add road snapping" --body-file /tmp/pr-body.md
bin/vibe review-gate <number>
```
