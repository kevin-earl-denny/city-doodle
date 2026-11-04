/**
 * Global setup for E2E tests
 *
 * Runs once before all tests to ensure the test environment is ready.
 * - Verifies API is running and healthy
 * - Verifies database is accessible
 */

import { test as setup, expect } from "@playwright/test";

const API_URL = "http://localhost:8001";

setup("verify API is healthy", async ({ request }) => {
  // Check API health endpoint
  const response = await request.get(`${API_URL}/health`);
  expect(response.ok()).toBeTruthy();

  const data = await response.json();
  expect(data.status).toBe("healthy");
});

setup("verify auth endpoint is available", async ({ request }) => {
  // Without a Clerk session token /auth/me must answer 401 (not 404 or 5xx).
  const response = await request.get(`${API_URL}/auth/me`, {
    failOnStatusCode: false,
  });
  expect(response.status()).toBe(401);
});

setup("verify worlds endpoint requires auth", async ({ request }) => {
  // Unauthenticated request should return 401
  const response = await request.get(`${API_URL}/worlds`, {
    failOnStatusCode: false,
  });

  // Should be unauthorized, not a server error
  expect([401, 403]).toContain(response.status());
});
