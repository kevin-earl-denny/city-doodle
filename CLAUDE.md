# CLAUDE.md – AI Agent Instructions (City Doodle)

Instructions for every AI agent working in this repo (Claude, Codex, Cursor, ...).
Hand-maintained: edit it directly, in a PR, like any other file.

---

## Project Overview

- **What it is:** a lo-fi vector city builder. Users generate terrain, place districts, roads and transit, and watch the city grow. See `README.md`.
- **Stack:**
  - `apps/web`: React 18 + TypeScript + Vite + PixiJS + Tailwind + TanStack Query, on **Vercel**. Heavy geometry runs in a Web Worker (`src/workers/`).
  - `apps/api`: FastAPI + async SQLAlchemy + Alembic (`apps/api/alembic/`), on **Fly** (`city-doodle-api`).
  - `apps/worker`: Python job worker for terrain and growth generation, on **Fly** (`city-doodle-worker`).
  - `packages/shared`: shared TypeScript types and Python schemas.
  - Database: **Neon** Postgres.
  - `lib/vibe`, `bin/`: developer and agent tooling (vibe CLI).
- **GitHub:** `kevin-earl-denny/city-doodle`. **Linear:** workspace `2wrist`, team **CITY**.

---

## Core Rules

- **Ask** when requirements are ambiguous, several valid approaches exist, or an action is destructive or outward-facing. **Don't ask** when the answer is in the repo, a standard pattern applies, or the action is trivially reversible. If you're more than 80% confident, proceed and state the assumption.
- **HUMAN label = "I cannot proceed without a human."** First check whether you can do it with the CLIs and credentials you have (`gh`, `fly`, `vercel`, `bin/ticket`); if so, do it. HUMAN is for console-only setup, payment, secrets only Kevin holds, and external communication. Every HUMAN ticket has step-by-step instructions.
- **Never work on `main` or in the main checkout.** One worktree per ticket.
- **Prefer absolute paths over `cd`:** `git -C <path>`, `npm --prefix <path>`, `gh --repo kevin-earl-denny/city-doodle`.
- **Sync before you read:** run `git -C <repo> fetch origin` and reason against `origin/main`. Local `main` goes stale quickly; the SessionStart hook warns when it is.
- **Every bug fix ships a regression test** in the same PR, or the PR says why it can't.
- **Never swallow errors.** A caught exception that returns a fallback is worse than a loud failure. Caught DB errors roll back the session.
- **Stage explicit paths** (`git add -- <paths>`), never `git add -A`: other agents may share the checkout.

---

## Tickets (Linear, team CITY)

### "Do ticket CITY-123"
Run `bin/vibe do CITY-123`. It:
- creates `../city-doodle-worktrees/CITY-123` on branch `CITY-123`;
- claims the ticket (In Progress, assigned to you);
- refuses a ticket someone else already started (`--force` overrides);
- with `--dry-run`, prints what it would do and changes nothing.

Do all the work in that worktree and open a PR when done. Don't combine `bin/vibe do` with Claude Code's `isolation: "worktree"` on the same ticket.

### Creating tickets
1. **Search first** (`bin/ticket list`) and prefer updating an existing ticket.
2. **Title:** Verb + Object ("Fix terrain progress hook looking up wrong center tile").
3. **Labels:**
   - one type: `Bug`, `Feature`, `Improvement`, `chore` or `Refactor`;
   - at least one area: `frontend`, `backend`, `Infra`, `Docs`, `database`, `terrain`, `roads`, `transit` or `district`;
   - `Low Risk` when it is; `HUMAN` when a person must act.
   - Priority uses Linear's native field, not labels.
4. **Description:** `## Context` (for bugs, include the root cause), numbered testable `## Acceptance Criteria`, and `## Dependencies`. A ticket with no description is never acceptable.
5. **Dependencies:** link with `bin/ticket relate CITY-1 --blocks CITY-2`.
6. **Descriptions are the source of truth.** Put scope changes in the description, not in comments.

### Status flow
**Backlog** → **Todo** → **In Progress** (`bin/vibe do`) → **In Review** (PR open) → **Deployed** (merged) → **Done** (verified in the running app).

**Merging is Deployed, not Done.** Move a ticket to Done only after checking its acceptance criteria against production. Terminal states: Canceled, Duplicate.

Linear's native GitHub integration moves tickets on PR open and merge. Don't add workflows or hooks that also write those transitions.

---

## Pull Requests

- **Branch** `CITY-<n>`. **Title** `CITY-<n>: <summary>`. Rebase on `main`; never merge `main` into a branch.
- **Body:** fill in `.github/PULL_REQUEST_TEMPLATE.md` with these sections:
  - Summary
  - Changes
  - Verification: what you actually ran, and the results
  - Gotchas
  - Secrets: new env vars and where they're set, or "None"
  - Cleanup: cloud resources created and deleted, or "None"

  Then add `Linear: CITY-<n>`, the Claude Code footer, and, as its own last line, the author marker `<!-- city-author session=<your session name> -->`. `bin/vibe pr` fills this in.
- **Never add `--reviewer`.** Review here is agents plus CodeRabbit only.
- Update the description when follow-up commits change scope.

### Merge bar
A PR may merge when **either** of these holds on the **current head SHA**:
1. **CodeRabbit** has APPROVED it (its latest state-changing review), **or**
2. **two distinct agent reviewers**, neither of them the author session or its subagents, have posted clean reviews (verdict `pass` or `minor`).

Any `major` verdict on the head blocks it until a new push. A push invalidates earlier reviews. The required `review-gate` status enforces this (`bin/vibe review-gate <n>` checks a PR locally).

**Agent review format.** A review is a GitHub PR **review** (event `COMMENT`, since agents can't approve PRs from their own account). Its exact last non-empty line is the marker printed by `bin/vibe review-marker --reviewer <id> --verdict pass|minor|major --pr <n>`, which has this shape:

    <!-- city-agent-review v1 reviewer=<id> head=<40-char sha> verdict=pass|minor|major -->

- Never mention the marker name anywhere else in the review.
- Never edit a posted review; post a new one. An edited or malformed review blocks its head.
- The reviewer id is your session name, with `/<suffix>` for subagents.
- Verdicts:
  - `major`: a bug, a security or data-loss problem, unmet acceptance criteria, or failing tests;
  - `minor`: nits only;
  - `pass`: nothing found.

**CodeRabbit:**
- `request_changes_workflow` is on, so it APPROVES once its threads are resolved.
- Only the first push is auto-reviewed. After pushing fixes, comment `@coderabbitai review` once per round.
- Reply on each thread with `Fixed in <sha>` or a reasoned won't-fix. "Noted" is not a resolution.
- It reads `.coderabbit.yaml` from `main` only.

**Reviewing someone else's PR:** comment only; never push to their branch. Use `/review` for a deep review and `/fixup` to make your own PR mergeable.

---

## Worktrees & Multi-Agent Work

- Worktrees live in `../city-doodle-worktrees/CITY-<n>`.
- `bin/vibe cleanup` removes a worktree only when **all** of these hold: its ticket is terminal (Done, Canceled or Deployed), it has no uncommitted changes, and it's more than 30 minutes old. **Never** judge a worktree stale with `git branch --merged`, because a fresh zero-commit branch looks merged.
- Worktrees have no `.env.local`. Tools fall back to the main checkout's copy.
- Several sessions run in parallel. Announce which files you're touching, stay in your lane, and check `git branch -r` / `gh pr list` before starting overlapping work.

---

## Environment & Secrets

- Secrets live in `.env.local` (gitignored, never committed) at the main checkout root. `.envrc` (committed) loads it with direnv and puts `bin/` on `PATH`: run `direnv allow` once.
- Every new env var goes in `.env.example` (with where it's set: Fly app, Vercel, GitHub secret) **in the same PR**, and gets set wherever it's deployed, or has a HUMAN ticket.
- Deployed: `fly secrets list -a city-doodle-api` / `-a city-doodle-worker`; Vercel project env for `apps/web`.

---

## Git Hooks & CI

- Install once per clone: `git config --local core.hooksPath .githooks`. This also applies to worktrees.
  - **pre-commit** refuses `.env` / `.env.*` files (except `.env.example`).
  - **pre-push** lints the files you changed (ruff for Python; eslint for `apps/web`), runs `tsc`, and warns on multiple Alembic heads.
  - Bypass with `--no-verify` only after running those checks another way.
- **Alembic:** `bin/migrations check` must report one head. Revision ids must be unique. Run `bin/migrations fix-heads` after concurrent migration merges.
- **Read the failing log before fixing anything:** `gh pr checks <n> --repo kevin-earl-denny/city-doodle`, then `gh run view <id> --log-failed`.
- Actions are pinned to commit SHAs with a `# vX.Y.Z` comment, and runners to a fixed Ubuntu version (`ubuntu-latest` moved to 26.04 and broke Playwright: CITY-649).

---

## CLI Conventions (`bin/*`)

1. **Fail loudly.** Exit codes: 0 ok, 1 expected error, 2 drift or incident. A CLI that prints "nothing found" when its credential is missing is a bug. File it as an Urgent ticket.
2. **Smoke-test every subcommand you change** and put a ✅/❌/⏸️ matrix in the PR body.

```bash
bin/vibe do CITY-123          # worktree + claim; --force, --dry-run
bin/vibe pr                   # open a PR for the current branch (fills template + author marker)
bin/vibe cleanup              # remove worktrees whose ticket is terminal
bin/vibe doctor               # health check
bin/vibe review-gate <pr>     # evaluate the merge bar locally (dry run)
bin/vibe review-marker ...    # print an agent-review marker line
bin/ticket list|get|create|update|comment|relate|close|labels|projects|users
bin/migrations check|heads|fix-heads
bin/logs                      # query API/worker logs in Axiom (see bin/logs help)
```

Slash commands (`.claude/commands/`):
- `/do`, `/pr`, `/ticket`, `/cleanup`, `/doctor`;
- `/review`: the default for any review request;
- `/fixup`: get your PR green and approved;
- `/fly`, `/neon`, `/vercel`.

---

## Code Conventions

- **Python:** ruff-clean. Migrations never import app packages at module load.
- **TypeScript:** strict, no `any`. TanStack Query owns server state; optimistic updates roll back on failure. Keep heavy geometry off the main thread.
- **Numeric falsy:** a real `0` is not missing. Use `!= null`, not `!value` or `value || fallback`.
- **PixiJS:** destroy what you create (textures, graphics) or GPU memory leaks.

---

## Anti-Patterns

1. Working on `main` or in the main checkout.
2. Guessing at CI failures without reading the logs.
3. Committing secrets or `.env.local`.
4. Tickets without a description, labels or acceptance criteria.
5. Moving a ticket to Done on merge or commit.
6. Assuming CodeRabbit re-reviewed a follow-up push.
7. Shipping a CLI change without a smoke-test matrix.
8. Deleting another agent's worktree or branch.
9. Two migrations with the same `down_revision` or revision id.
