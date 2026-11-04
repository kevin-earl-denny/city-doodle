---
description: Deep review of a PR or ticket branch: production pitfalls, performance, security, acceptance criteria. Fixes your own branch; on someone else's PR, posts a review the review-gate counts.
---

# /review - Comprehensive Review

Deep review of ticket code for production readiness, performance, security, and correctness.

- **Your own branch** (you're its author): fix what you find and push.
- **Someone else's PR**: don't push to it. Post one PR review that ends in the `city-agent-review` marker (see "Posting an agent review" below). That review is what the required `review-gate` status counts.

## Usage

```bash
/review CITY-123       # review code for a specific ticket
/review 465            # review a PR by number
/review                # auto-detect from current branch
```

## Instructions

### Step 1: Resolve the PR, base, and head

- **Pick the branch and worktree first.** Every command below runs *inside* that worktree, so `HEAD` is the branch under review.
  - Ticket ID given (e.g. `CITY-123`): find its worktree (`git worktree list | grep -i CITY-123`). With no worktree, find the PR and review its head in a clean checkout (`git status --porcelain` must print nothing before you `git checkout`).
    ```bash
    gh pr list --repo kevin-earl-denny/city-doodle --search "CITY-123" --json number,headRefName --jq '.[0]'
    ```
  - PR number given: `gh pr view <n> --repo kevin-earl-denny/city-doodle --json headRefName,headRefOid,baseRefName,body,files`.
  - No argument: the current branch (`git branch --show-current`).

- **Resolve the base from the PR.** Stacked PRs target another ticket branch; use `main` only when there's no PR. Any other lookup failure (auth, network) is an error: stop and report it, don't guess.
  ```bash
  BRANCH=$(git branch --show-current)
  PR_JSON=$(gh pr list --repo kevin-earl-denny/city-doodle --head "$BRANCH" --state open \
    --json number,baseRefName,headRefOid --jq '.[0] // empty') || { echo "PR lookup failed"; exit 1; }
  if [ -n "$PR_JSON" ]; then
    PR_NUMBER=$(echo "$PR_JSON" | jq -r .number); BASE=$(echo "$PR_JSON" | jq -r .baseRefName)
    HEAD_SHA=$(echo "$PR_JSON" | jq -r .headRefOid)
  else
    PR_NUMBER=""; BASE=main; HEAD_SHA=$(git rev-parse HEAD)
  fi
  git fetch origin "$BASE"
  ```
- Review the three-dot diff (never `origin/main` for a stacked PR):
  ```bash
  git diff "origin/$BASE...$HEAD_SHA" --name-only
  git diff "origin/$BASE...$HEAD_SHA"
  ```
- Read the ticket and its acceptance criteria: `bin/ticket get CITY-123`. A broken or missing acceptance criterion is a **major** finding.

### Step 1b: Gather all existing PR feedback (if a PR exists)

Fetch every review thread and PR-level review from **all** reviewers. Review here is agents only: CodeRabbit plus agent reviews, which post under the `kdenny` user account, so never filter to bots.

> **`[bot]` suffix gotcha:** GraphQL `author.login` strips the suffix (`coderabbitai`); the REST reviews endpoint keeps it (`coderabbitai[bot]`).

```bash
# Unresolved review threads, any author
gh api graphql -f query='
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first: 100) {
        nodes { isResolved comments(first: 100) { nodes { path line body author { login } } } }
      }
    }
  }
}' -F owner='kevin-earl-denny' -F repo='city-doodle' -F number=<PR_NUMBER> \
  --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)'

# PR-level reviews (CodeRabbit + agent reviews)
gh api --paginate repos/kevin-earl-denny/city-doodle/pulls/<PR_NUMBER>/reviews \
  --jq '.[] | {user: .user.login, state, commit_id, body}'

# PR conversation comments, all authors
gh api --paginate repos/kevin-earl-denny/city-doodle/issues/<PR_NUMBER>/comments \
  --jq '.[] | {user: .user.login, created_at, body}'
```

Triage every item; don't blindly trust any reviewer. Read the code at the flagged location, decide whether it's real, and fold real ones into your findings.

### Step 2: Build the review scope

Changed files **plus** their immediate context: files that import them, files they import, related tests and types. Read all of it before judging.

### Step 3: Run the review

Check every file in scope against all of these. Use subagents to parallelize where useful.

- **Correctness**: logic errors, off-by-one, wrong units/coordinates, broken invariants, unhandled edge cases (empty arrays, null API responses, first-time user with no data).
- **Production reliability**: unhandled errors, silent failures (swallowed exceptions, empty catches), race conditions, stale closures, missing loading/error states, resource leaks (intervals, listeners, PixiJS objects not destroyed), data integrity on write paths.
- **Performance**: unnecessary re-renders, unstable props, heavy work per frame in the PixiJS render loop, N+1 queries or sequential awaits in `apps/api`, unbounded caches, large imports.
- **Security**: SQL injection (raw string SQL), XSS (`dangerouslySetInnerHTML`), command injection, auth gaps on FastAPI routes, secrets in code or client bundles, permissive CORS, missing input validation at API boundaries.
- **Type safety**: `any`, unnecessary `as` casts, untyped exports (TypeScript strict); missing or wrong Pydantic models / type hints in `apps/api`.
- **Database**: Alembic migrations in `apps/api/alembic/versions/` must keep a single head and a linear chain, have a working `downgrade`, and be safe on populated tables.
- **Cloud resources**: anything the change (or its docs/scripts) creates on Neon, Fly, Vercel, or docker must be torn down in the same job, including on failure. A create without guaranteed teardown is a **major**.
- **Conventions**: match existing patterns in `apps/web/src` (TanStack Query for server state, components/pages/utils layout) and `apps/api/src/city_api` (routers, schemas, repositories).
- **Tests**: new behaviour has tests; the tests actually exercise it.

### Step 4: Verify locally

Run what applies to the files changed:

```bash
# API
(cd apps/api && ruff check . && ruff format --check . && pytest -q)
(cd apps/api && alembic heads)   # exactly one "(head)"
# Web
(cd apps/web && npm run lint && npm run typecheck && npm test)
# Tooling (lib/, scripts/, bin/)
python3 -m pytest tests -q && ruff check lib bin
```

A failing test, lint, type check or a second Alembic head that the PR introduces is a **major**.

### Step 5: Classify findings

- **major**: a bug, security hole, data loss, broken acceptance criterion, failing tests/lint/types, or a resource without teardown. Blocks the head.
- **minor**: nits, small improvements, missing-but-non-critical tests. Still mergeable.
- **pass**: nothing found.

Give each finding a `file:line`, the concrete failure scenario, and the fix.

### Step 6a: Your own branch: fix and push

Fix the auto-fixable findings (90%+ confidence), flag trade-offs for the user, re-run Step 4, commit with explicit paths (`git add -- <paths>`, never `git add -A`), rebase on the PR base, and push with `git push --force-with-lease origin HEAD`. Then reply on each CodeRabbit thread you fixed, naming the pushed commit (don't resolve it, and never post `@coderabbitai approve`/`resolve`: see below). A push resets the review count: the new head needs fresh reviews.

### Step 6b: Someone else's PR: post an agent review

Don't push to their branch. Post one review as described below and report your verdict to the coordinator.

## Posting an agent review (review-gate)

The required `review-gate` status (`lib/vibe/review_gate.py`) passes a PR when CodeRabbit's latest state-changing review is APPROVED on the current head, **or** at least 2 distinct agent reviewers who aren't the PR's author posted `pass`/`minor` reviews on the current head. Any `major` on the head blocks it.

- Post **one PR review** (event `COMMENT`) pinned to the SHA you reviewed. PR comments don't count.
  ```bash
  gh api repos/kevin-earl-denny/city-doodle/pulls/<n>/reviews \
    -f commit_id=<full head sha> -f event=COMMENT -F body=@review.md
  ```
- The body's **exact last non-empty line** is the marker, generated by:
  ```bash
  bin/vibe review-marker --reviewer <your id> --verdict pass|minor|major --pr <n>
  ```
  It must be the **only** place the marker keyword appears in the review: don't quote marker examples. A second mention, a last line that doesn't parse, or **editing the review after posting** makes it invalid, and an invalid review blocks the head like a major. To change a verdict, post a new review (on a new head if it was a major).
- `pass` = no findings, `minor` = minors or nits only, `major` = at least one major. A `major` blocks until the head moves; a later `pass` from the same reviewer on the same head doesn't clear it.
- Reviewers are counted by **root id**: `<id>` and its subagents `<id>/...` are one reviewer, compared case-insensitively (`reviewer-b`, `Reviewer-B` and `reviewer-b/deep` are all `reviewer-b`). Only the latest review under a root counts, and a `major` from any of them blocks the head. Use your own session id as the root; subagents you spawn sign `<your id>/<role>`. The author's root (the `city-author` line in the PR body) never counts.
- After a **pure rebase**, the author can carry agent reviews to the new head with a PR comment whose own line is `<!-- city-rebase-carry v1 from=<old full sha> to=<new full sha> -->`; the gate verifies it with `git patch-id --verbatim`. CodeRabbit approval never carries.
- Check the result with `bin/vibe review-gate <n>`: it lists what counted and why the rest didn't.
- **Never steer CodeRabbit's approval.** Every agent posts as the PR author's account, and a CodeRabbit APPROVED on the head passes the gate alone. Never type `@coderabbitai approve` or `@coderabbitai resolve`, and never resolve a CodeRabbit thread: reply on it (agree, disagree, or "fixed in <sha>") and let CodeRabbit resolve its own threads when it re-reviews. Put your own findings in your agent review.

## Related

- `/fixup` — make a PR green and merge-ready (CI, review threads, conflicts)
- `/pr` — create a pull request
