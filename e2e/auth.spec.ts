/**
 * E2E tests for authentication (Clerk, CITY-644)
 *
 * Password registration/login moved to Clerk. These tests cover what can be
 * checked without signing in: the API rejects unauthenticated requests and
 * the old endpoints are gone; with a Clerk publishable key, the UI sends
 * signed-out visitors to Clerk. Signed-in flows need Clerk testing tokens
 * (CITY-654).
 */

import { test, expect } from "@playwright/test";

const API_URL = "http://localhost:8001";

test.describe("Auth API", () => {
  for (const path of ["/auth/register", "/auth/login", "/auth/logout"]) {
    test(`password endpoint ${path} is removed`, async ({ request }) => {
      const response = await request.post(`${API_URL}${path}`, {
        data: { email: "someone@example.com", password: "irrelevant" },
        failOnStatusCode: false,
      });
      expect([404, 405]).toContain(response.status());
    });
  }

  test("/auth/me without a token returns 401", async ({ request }) => {
    const response = await request.get(`${API_URL}/auth/me`, { failOnStatusCode: false });
    expect(response.status()).toBe(401);
  });

  test("X-User-Id header is not trusted", async ({ request }) => {
    const response = await request.get(`${API_URL}/worlds`, {
      headers: { "X-User-Id": "00000000-0000-0000-0000-000000000001" },
      failOnStatusCode: false,
    });
    expect(response.status()).toBe(401);
  });

  test("a forged bearer token is rejected", async ({ request }) => {
    const response = await request.get(`${API_URL}/worlds`, {
      headers: { Authorization: "Bearer not.a.real.jwt" },
      failOnStatusCode: false,
    });
    // 401 with CLERK_DOMAIN set; 503 (fail closed) when the e2e API has no Clerk config.
    expect([401, 503]).toContain(response.status());
  });
});

test.describe("Auth UI", () => {
  test.skip(
    !process.env.VITE_CLERK_PUBLISHABLE_KEY,
    "Needs VITE_CLERK_PUBLISHABLE_KEY (Clerk keys: CITY-645)"
  );

  test("signed-out visitor is sent to Clerk sign-in", async ({ page }) => {
    await page.goto("/worlds/some-world");
    await expect(page).toHaveURL(/\/sign-in/);
  });

  test("old /login URL redirects to sign-in", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/\/sign-in/);
  });

  test("old /register URL redirects to sign-up", async ({ page }) => {
    await page.goto("/register");
    await expect(page).toHaveURL(/\/sign-up/);
  });
});
