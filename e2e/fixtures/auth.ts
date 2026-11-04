/**
 * Authentication fixtures for E2E tests
 *
 * CITY-644 replaced email/password auth (POST /auth/register|login and a
 * localStorage session token) with Clerk. Until e2e sign-in goes through Clerk
 * testing tokens (CITY-654), every test that requests the `auth` fixture is
 * skipped with CLERK_E2E_SKIP_REASON instead of failing against removed
 * endpoints. The interface is kept so the specs still type-check.
 */

import { test as base, type Page, type TestInfo } from "@playwright/test";

export const CLERK_E2E_SKIP_REASON =
  "Password auth was removed in CITY-644; e2e sign-in via Clerk testing tokens is CITY-654";

export interface TestUser {
  email: string;
  password: string;
  id?: string;
  token?: string;
}

export interface AuthFixture {
  /** Register a new user via API and return credentials */
  registerUser: (email?: string, password?: string) => Promise<TestUser>;

  /** Login an existing user via API and return token */
  loginUser: (email: string, password: string) => Promise<TestUser>;

  /** Login as a user in the browser (UI flow) */
  loginViaBrowser: (page: Page, email: string, password: string) => Promise<void>;

  /** Register a user in the browser (UI flow) */
  registerViaBrowser: (page: Page, email?: string, password?: string) => Promise<TestUser>;

  /** Set auth token in browser for authenticated tests */
  setAuthInBrowser: (page: Page, token: string) => Promise<void>;

  /** Clear auth from browser */
  clearAuth: (page: Page) => Promise<void>;

  /** Get a unique test email */
  uniqueEmail: () => string;
}

/** Fixture body: skips the requesting test until Clerk e2e auth exists (CITY-654). */
export async function skippedAuthFixture(
  // eslint-disable-next-line no-empty-pattern
  {}: object,
  use: (auth: AuthFixture) => Promise<void>,
  testInfo: TestInfo
): Promise<void> {
  testInfo.skip(true, CLERK_E2E_SKIP_REASON);
  await use(undefined as never);
}

export const test = base.extend<{ auth: AuthFixture }>({
  auth: skippedAuthFixture,
});

export { expect } from "@playwright/test";
