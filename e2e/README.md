# E2E Tests

End-to-end tests using Playwright for City Doodle.

## Running Tests

### Prerequisites

1. **Test database**: Create a local test database
   ```bash
   createdb city_doodle_test
   ```

2. **API dependencies**: Install Python dependencies in the API venv
   ```bash
   cd apps/api
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Run migrations** (first time only):
   ```bash
   cd apps/api
   DATABASE_URL=postgresql+asyncpg://localhost/city_doodle_test alembic upgrade head
   ```

### Running All Tests (Local)

```bash
npm run test:e2e
```

This runs:
- All test files in `/e2e`
- All browsers (Chromium, Firefox, WebKit)
- All tests including `@slow` tagged tests

### Running CI Subset

```bash
CI=true npm run test:e2e
```

This runs:
- Only Chromium
- Excludes `@slow` tagged tests
- Uses GitHub reporter

### Running Specific Tests

```bash
# Single file
npx playwright test e2e/auth.spec.ts

# Specific test by title
npx playwright test -g "can login"

# Debug mode (headed browser)
npx playwright test --debug

# UI mode (interactive)
npx playwright test --ui
```

## Test Structure

```
e2e/
├── fixtures/           # Shared test utilities
│   ├── index.ts       # Combined fixture exports
│   ├── auth.ts        # Auth fixture (skips tests until Clerk e2e sign-in, CITY-654)
│   └── api.ts         # Direct API helpers (create world, etc.)
├── global.setup.ts    # Runs once before all tests
├── auth.spec.ts       # Clerk auth checks (API 401s; UI redirects need a Clerk key)
├── worlds.spec.ts     # World creation/management tests
├── build-grow.spec.ts # Seed placement & growth tests
├── export.spec.ts     # Export functionality tests
└── home.spec.ts       # Basic navigation tests
```

## Test Tagging Strategy

### No tag (default)
Runs in both CI and local. Use for essential happy-path tests.

```typescript
test("can login with valid credentials", async ({ page }) => {
  // ...
});
```

### @slow
Runs only locally. Use for edge cases, error scenarios, or slow tests.

```typescript
test("@slow handles network timeout gracefully", async ({ page }) => {
  // ...
});
```

### Using Tags

The `@slow` tag is detected by test title. In CI, tests with `@slow` in the title are excluded via grep pattern.

## Fixtures

### auth fixture

> **Currently skipped.** CITY-644 replaced email/password auth with Clerk, so
> `/auth/register`, `/auth/login` and the localStorage token no longer exist.
> Any test that requests `auth` is skipped until e2e sign-in uses Clerk testing
> tokens (CITY-654). The UI checks in `auth.spec.ts` run only when
> `VITE_CLERK_PUBLISHABLE_KEY` is set. The example below is the pre-Clerk API.

```typescript
import { test, expect } from "./fixtures";

test("example", async ({ page, auth }) => {
  // Register user via API (fast)
  const user = await auth.registerUser();

  // Or with specific credentials
  const user2 = await auth.registerUser("test@example.com", "password123");

  // Set auth in browser without UI flow
  await auth.setAuthInBrowser(page, user.token!);

  // Or login via UI
  await auth.loginViaBrowser(page, user.email, user.password);
});
```

### api fixture

```typescript
import { test, expect } from "./fixtures";

test("example", async ({ page, auth, api }) => {
  const user = await auth.registerUser();

  // Create test data via API
  const world = await api.createWorld(user.token!, "My World");

  // Then test UI with pre-existing data
  await auth.setAuthInBrowser(page, user.token!);
  await page.goto(`/worlds/${world.id}`);
});
```

## CI Configuration

E2E tests run in GitHub Actions with:
- PostgreSQL service container
- Python API server
- Vite dev server
- Chromium only

See `.github/workflows/tests.yml` for the full configuration.

## Troubleshooting

### "Connection refused" errors

Make sure both servers are running:
1. Web: `npm run dev --workspace=apps/web`
2. API: `cd apps/api && source .venv/bin/activate && uvicorn city_api.main:app --port 8001`

### Database errors

Run migrations on the test database:
```bash
cd apps/api
DATABASE_URL=postgresql+asyncpg://localhost/city_doodle_test alembic upgrade head
```

### Viewing test reports

After running tests:
```bash
npx playwright show-report
```
