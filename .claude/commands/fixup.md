---
description: Resolve all PR feedback (CodeRabbit, agent reviews, any other comments), CI failures, merge conflicts, and lint — make the PR merge-ready without a deep code review
---

# /fixup - Make a PR merge-ready

Resolve every external blocker on a PR: feedback from **all** reviewers (CodeRabbit and the agent reviews posted as PR reviews — including nitpicks, suggestions, and outside-diff-range comments), CI failures (lint, tests, migrations), and merge conflicts. No deep code review — just make it green and approved.

## Usage

```bash
/fixup CITY-123       # fixup a specific ticket's PR
/fixup 2198           # fixup PR by number
/fixup                # auto-detect from current branch
```

## What it does

1. Finds the PR and checks out the branch
2. Rebases on main (resolves merge conflicts)
3. **Post-rebase stabilization** — immediately re-check migrations, lint, and tests (rebase can break all of these)
4. Fetches and fixes ALL CodeRabbit feedback (current + old, including nitpicks and outside-diff-range)
5. Fetches and fixes agent-review findings and any other PR comments. This repo has no human reviewers.
6. **Second-pass validation** — re-run migrations, lint, and tests again (feedback fixes can introduce new breakage)
7. Replies on every addressed review thread; resolves agent-review threads, but never CodeRabbit's (CodeRabbit resolves its own on re-review)
8. **Notes CHANGES_REQUESTED review state** — the push will trigger each bot's re-review automatically
9. Pushes and posts a PR comment summarizing changes

## Instructions

When the user invokes `/fixup`:

### Step 0: Resolve the PR

- If a ticket ID is given (e.g., `CITY-123`), find the PR:
  ```bash
  gh pr list --repo kevin-earl-denny/city-doodle --search "CITY-123" --json number,headRefName,url --jq '.[0]'
  ```
- If a PR number is given (e.g., `2198`), use it directly
- If no argument, detect from current branch:
  ```bash
  gh pr list --repo kevin-earl-denny/city-doodle --head "$(git branch --show-current)" --json number,headRefName,url --jq '.[0]'
  ```

Save the PR number, branch name, and URL for later steps.

### Step 1: Check out the branch and rebase (only if behind main)

> **Stacked PRs:** if the PR's base is another ticket branch (e.g. CITY-2 → `CITY-1`), substitute that base for `main` everywhere in this step: `gh pr view <PR_NUMBER> --json baseRefName -q .baseRefName`.

```bash
# Fetch latest
git fetch origin main
git fetch origin <branch>

# Check out the branch (find worktree or check out directly)
git worktree list | grep -i "<ticket-or-branch>"
# If in a worktree, cd there. Otherwise, FIRST make sure the current checkout is
# clean — `git checkout` carries non-conflicting local changes onto the PR branch,
# and Step 6 could then commit someone else's work as "fixes":
git status --porcelain   # must print nothing (tracked AND untracked)
# If it prints anything: stop and ask, or move that work aside explicitly
# (commit it on its own branch / `git stash push -u -m "<why>"`). Then:
git checkout <branch>

# Only rebase if the branch is actually behind main (a no-op rebase still needs
# a force-push). BEFORE rebasing, make sure the local branch already contains
# every remote commit — after a rebase they are no longer ancestors of HEAD, so
# this can't be checked afterwards. Record the remote SHA for the push lease.
if [ "$(git merge-base origin/main HEAD)" != "$(git rev-parse origin/main)" ]; then
  if [ -n "$(git log --oneline HEAD..origin/<branch>)" ]; then
    echo "origin/<branch> has commits this checkout lacks — integrate them first"; exit 1
  fi
  REMOTE_SHA=$(git rev-parse origin/<branch>)   # the lease for Step 6
  git rebase origin/main
else
  echo "Branch is already up-to-date with main — skipping rebase"
fi
```

If merge conflicts arise, resolve them intelligently:
- Read both sides of each conflict
- Prefer the semantically correct resolution (not just "ours" or "theirs")
- If a conflict is in a migration file, check `alembic heads` after resolution — you may need to update `down_revision`
- If `package-lock.json` conflicts, resolve `package.json` first, then regenerate with `npm install` and stage the lockfile. Never hand-edit lock markers

### Step 1b: Post-rebase stabilization

Rebasing on main frequently breaks things that were green before. **Immediately after a successful rebase**, run these checks and fix anything broken before moving on to feedback:

```bash
# 1. Migrations — check for parallel heads (most common rebase breakage)
(cd apps/api && alembic heads)
# If multiple heads: update down_revision in the branch's migration to point at main's latest head

# 2. Python lint (merge resolution can introduce lint violations)
(cd apps/api && ruff check --fix . && ruff format .)
ruff check --fix lib bin && ruff format lib bin   # tooling, if lib/ or bin/ changed

# 3. Frontend (if apps/web files are in the diff)
(cd apps/web && npx eslint . --fix && npm run typecheck)
```

Fix everything before proceeding. The goal is: **the branch is green on main before any feedback fixes are applied**, so feedback fixes are the only variable in the next steps.

### Step 2: Gather ALL external feedback

Run these in parallel.

#### 2a. ALL review threads, every reviewer (resolved AND unresolved)

Review here is **agents only**: **CodeRabbit** (`coderabbitai`) plus agent reviews, which are PR reviews posted from the `kdenny` user account. There are no human reviewers. **Fetch every thread regardless of author — never filter to a single bot** (agent reviews post under a user account, so a bot-only filter drops them). Capture `databaseId` (for replies) and `id` (the thread ID, for resolving).

> **`[bot]` suffix gotcha:** GraphQL `author.login` strips the suffix (`coderabbitai`); the REST reviews endpoint keeps it (`coderabbitai[bot]`). Don't compare logins across the two APIs assuming they match.

```bash
gh api graphql -f query='
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 100) {
            nodes { id databaseId path line body author { login } createdAt }
          }
        }
      }
    }
  }
}' -F owner='kevin-earl-denny' -F repo='city-doodle' -F number=<PR_NUMBER>
```

Group the threads by author so none is overlooked, and separate by state:
- **Unresolved (any author)** — must address, then reply on the thread (Step 5).
- **Resolved (bot-authored)** — scan for threads resolved without actually being fixed; bots (CodeRabbit especially) sometimes append new feedback to an old resolved thread.

Fetch **every** PR-level review body and plain PR comment too, from all authors. CodeRabbit's summary (batch nitpicks, outside-diff findings) is an issue comment, and agent reviews are review bodies from a user account, so a bot-only filter misses them:

```bash
# ALL authors: agent reviews are posted under a user account, not a bot.
# --paginate so long threads aren't truncated at 30 items.
gh api --paginate repos/kevin-earl-denny/city-doodle/pulls/<PR_NUMBER>/reviews \
  --jq '.[] | {user: .user.login, state, commit_id, body}'
gh api --paginate repos/kevin-earl-denny/city-doodle/issues/<PR_NUMBER>/comments \
  --jq '.[] | {user: .user.login, created_at: .created_at, body: .body}'
```

#### 2c. CI check status

```bash
gh pr checks <PR_NUMBER> --repo kevin-earl-denny/city-doodle
```

For any failing checks, get the logs:
```bash
gh run view <run-id> --repo kevin-earl-denny/city-doodle --log-failed
```

#### 2d. PR review status

```bash
# Check if any reviews are blocking (CHANGES_REQUESTED)
gh api repos/kevin-earl-denny/city-doodle/pulls/<PR_NUMBER>/reviews \
  --jq '.[] | {user: .user.login, state: .state}'
```

### Step 3: Fix all feedback

At this point the branch is rebased and locally green (Step 1b handled post-rebase breakage). Now work through all external feedback. For each item, read the actual code at the referenced location before making changes.

#### Priority order:
1. **CI failures** (from Step 2c) — read the actual failure logs, fix root causes. Common failures:
   - Test failures — run the failing test locally, fix
   - Type errors — `tsc --noEmit` or mypy
2. **CodeRabbit feedback** — address ALL threads (unresolved + resolved-but-updated):
   - **Bugs / logic issues** — fix the code
   - **Suggestions / improvements** — apply them (even nitpicks — address them all)
   - **Outside-diff-range comments** — fix these too (bots sometimes flag pre-existing issues adjacent to the diff)
   - **Old feedback on resolved threads** — check if a bot appended new comments to a resolved thread; if the underlying issue still exists, fix it
3. **Agent review comments and any other PR comments**: address every finding. Review here is agents only, so never request a human reviewer.

#### For each comment (any reviewer), decide:
- **Fix it** (default) — apply the suggestion or fix the flagged issue
- **Skip it** — ONLY if the suggestion is factually wrong or not applicable to this codebase. When skipping, you **MUST** post a reply directly on that comment's thread explaining why — for **every** reviewer (CodeRabbit, agent reviews, …), not just CodeRabbit:

```bash
# Reply to the specific comment thread explaining the skip
gh api repos/kevin-earl-denny/city-doodle/pulls/<PR_NUMBER>/comments/<COMMENT_DATABASE_ID>/replies \
  -f body="<concise explanation citing codebase evidence for why the suggestion was skipped>"
```

Use the `databaseId` from the GraphQL query in Step 2a as `<COMMENT_DATABASE_ID>`. Each reply should cite specific codebase evidence (e.g., "Existing pattern at `file.py:67` already uses this approach"). Do NOT just say "skipped" — explain the reasoning so reviewers can evaluate the decision.

### Step 4: Second-pass validation

Feedback fixes can introduce new breakage (a CodeRabbit suggestion might break a test, fixing a lint issue might shift a migration import, etc.). **Re-run the full check suite after all fixes are applied:**

```bash
# 1. Migrations — parallel heads can appear if feedback fixes touched migration files
(cd apps/api && alembic heads)   # exactly one "(head)"; else fix down_revision again

# 2. API lint + format + tests (if apps/api changed)
(cd apps/api && ruff check . && ruff format --check . && pytest -q)

# 3. Tooling (if lib/, bin/, scripts/ or tests/ changed)
ruff check lib bin && ruff format --check lib bin && python3 -m pytest tests -q

# 4. Frontend lint + types + unit tests (if apps/web changed)
(cd apps/web && npm run lint && npm run typecheck && npm test)
```

Only run checks relevant to the files changed across the entire diff (original + rebase + feedback fixes). **Fix anything that fails.** If a fix here introduces yet another failure, keep iterating until clean — do not push a branch that fails local checks.

### Step 5: Reply on addressed review threads (never resolve CodeRabbit's)

> **The author must never cause CodeRabbit's approval.** A CodeRabbit APPROVED on the head passes the merge bar by itself, and CodeRabbit approves once its threads are resolved. So:
> - **Never resolve a CodeRabbit thread yourself.** Reply on it instead and let CodeRabbit resolve it when it re-reviews (Step 5b).
> - **Never type `@coderabbitai approve` or `@coderabbitai resolve`** in any comment or reply. You post as the PR author, and those commands would approve your own PR. (`.coderabbit.yaml` also sets `allow_author_approval: false`.)

**CodeRabbit threads:** for every thread you addressed, reply on it with what changed (file:line and the commit) or, if you skipped it, why (Step 3). Leave it unresolved.

**Agent-review threads (the `kdenny` account):** reply the same way, then resolve the thread. That includes old threads that were addressed earlier but never resolved.

```bash
# Reply on a thread (any reviewer): the first comment's databaseId from Step 2a
gh api repos/kevin-earl-denny/city-doodle/pulls/<PR_NUMBER>/comments/<COMMENT_DATABASE_ID>/replies \
  -f body="Fixed in <sha>: <what changed, file:line>"

# Agent-review threads ONLY (never CodeRabbit's): resolve by GraphQL thread ID
gh api graphql -f query='
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { isResolved }
  }
}' -F threadId='<THREAD_ID>'
```

Do this for EVERY addressed thread, from every reviewer.

### Step 5b: Note CHANGES_REQUESTED review state (any reviewer)

**Important:** Resolving review threads is NOT the same as clearing the review-level CHANGES_REQUESTED state. A PR with all threads resolved but a stale CHANGES_REQUESTED review will still show "Changes requested" in the UI. This applies to CodeRabbit's reviews.

After replying on all threads, check which reviewers have CHANGES_REQUESTED (REST logins keep the `[bot]` suffix):

```bash
gh api repos/kevin-earl-denny/city-doodle/pulls/<PR_NUMBER>/reviews \
  --jq '.[] | select(.state == "CHANGES_REQUESTED") | {user: .user.login, id, state}'
```

**Merge bar reminder (required `review-gate` status, `lib/vibe/review_gate.py`):** a PR is mergeable when CodeRabbit's latest state-changing review is **APPROVED on the current head**, **or** at least **2 distinct agent reviewers** (not the PR author) posted `pass`/`minor` reviews on the current head. Any `major` on the head blocks it. Every fixup push moves the head and resets the count, so the PR needs a fresh CodeRabbit approval or fresh agent reviews on the new head. After a **pure rebase** with no other change, carry the agent reviews instead: post a PR comment with `git range-diff` output and, on its own line, `<!-- city-rebase-carry v1 from=<old full sha> to=<new full sha> -->` (the gate verifies it with `git patch-id`; CodeRabbit approval never carries). Check with `bin/vibe review-gate <PR_NUMBER>`.

**CodeRabbit does not re-review on push in this repo.** `.coderabbit.yaml` sets `auto_pause_after_reviewed_commits: 1`, so only the first push is auto-reviewed. After the Step 6 push, request a re-review **once** with a PR comment: `gh pr comment <PR_NUMBER> --body "@coderabbitai review"`. That re-review reads your thread replies, resolves the threads it agrees are fixed, and, once all of its threads are resolved, produces the APPROVE that alone satisfies the merge bar (`auto_approvals.enabled: true`). CodeRabbit decides that, never the author: don't resolve its threads, and never post `@coderabbitai approve` or `@coderabbitai resolve`. Don't post it more than once per fixup round, because each request uses fair-use quota. If CodeRabbit is rate-limited, note "pending re-review (coderabbit)" in the fixup summary. 

### Step 6: Commit, push, and comment

```bash
# Stage and commit all fixes (review `git status` first — only this PR's changes)
git status --short
git add -- <paths you changed>   # explicit paths, never `git add -A`
git commit -m "$(cat <<'EOF'
CITY-XXX: Fixup — resolve PR feedback and CI issues

[summary of what was fixed]

<attribution lines from the session's system reminder>
EOF
)"

# Push. Regular push unless Step 1 actually rebased this run:
git push origin <branch>
# Only if Step 1 rebased: force-with-lease pinned to the remote SHA that Step 1
# verified was fully contained BEFORE the rebase. If someone pushed since, the
# lease fails — fetch, integrate, and redo Step 1 rather than overriding it.
#   git push --force-with-lease=<branch>:"$REMOTE_SHA" origin <branch>
# Pushing does NOT re-trigger CodeRabbit here — request it in Step 5b.
```

Then post a PR comment summarizing all changes:

```bash
gh pr comment <PR_NUMBER> --repo kevin-earl-denny/city-doodle --body "$(cat <<'EOF'
## Fixup Summary

**Rebased on main:** ✅ / ❌ (no conflicts)

**Automated-reviewer feedback addressed (N threads — break out per bot):**
- [CodeRabbit] [file:line] — [what was fixed]
- [file:line] — [skipped: reason] (only if any were skipped)

**Agent-review / other PR comments addressed (N):**
- [reviewer]: [file:line] — [what was fixed]

**CI fixes:**
- [what was fixed — lint, tests, migrations, etc.]

**Replied on every addressed thread:** ✅ (agent-review threads resolved; CodeRabbit threads left for CodeRabbit to resolve on re-review)

---
*Generated by `/fixup`*
EOF
)"
```

### Step 7: Verify

```bash
# Confirm PR is up to date with main
gh pr view <PR_NUMBER> --repo kevin-earl-denny/city-doodle --json mergeable,mergeStateStatus --jq '{mergeable, mergeStateStatus}'

# Count unresolved threads: agent-review threads should be 0; CodeRabbit's stay
# open until its re-review resolves them (don't resolve them yourself)
gh api graphql -f query='
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes { author { login } }
          }
        }
      }
    }
  }
}' -F owner='kevin-earl-denny' -F repo='city-doodle' -F number=<PR_NUMBER> \
  --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | .comments.nodes[0].author.login] | group_by(.) | map({(.[0]): length}) | add'

# Confirm no CHANGES_REQUESTED reviews remain (threads resolved ≠ review approved)
gh api repos/kevin-earl-denny/city-doodle/pulls/<PR_NUMBER>/reviews \
  --jq '[.[] | select(.state == "CHANGES_REQUESTED")] | length'
# If > 0 for coderabbitai[bot], confirm the `@coderabbitai review` comment from Step 5b was posted — note "pending re-review" in the report
```

Report the final state to the user:
- Merge conflicts: resolved / none
- Review threads: agent reviews N addressed, N resolved, N remaining (should be 0); CodeRabbit N addressed and replied to, N still open pending its re-review
- CodeRabbit review state: APPROVED / pending re-review (if CHANGES_REQUESTED persists, the `@coderabbitai review` request is pending and it clears once processed)
- Agent-review findings: N addressed, N remaining
- CI status: passing / pending re-run
- PR mergeable: yes / no (and why — distinguish "BLOCKED by pending bot re-review" from other blockers)

## What this skill does NOT do

- **No deep code review** — use `/review` for that
- **No ticket compliance check** — check the PR against the ticket's acceptance criteria with `/review`
- **No architecture analysis** — this is purely mechanical: fix what's flagged, make it green
- **No new feature work** — only resolves existing feedback and failures

## Related

- `/review` — deep review (production pitfalls, performance, security, acceptance criteria) + fix, or a gate-format agent review of someone else's PR
- `/pr` — Create a pull request
