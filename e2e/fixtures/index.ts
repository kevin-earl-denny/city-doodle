/**
 * Combined E2E test fixtures
 *
 * Import from this file to get all fixtures at once:
 *
 * ```ts
 * import { test, expect } from './fixtures';
 *
 * test('authenticated test', async ({ page, auth, api }) => {
 *   // NOTE: `auth` currently skips the test (Clerk e2e sign-in is CITY-654).
 * });
 * ```
 */

import { test as base, expect } from "@playwright/test";
import { skippedAuthFixture, type AuthFixture } from "./auth";
import type { ApiFixture } from "./api";

const API_URL = "http://localhost:8001";

// Re-export types
export type { TestUser, AuthFixture } from "./auth";
export type { World, Tile, ApiFixture } from "./api";

/**
 * Combined test fixture with auth and api helpers
 */
export const test = base.extend<{
  auth: AuthFixture;
  api: ApiFixture;
}>({
  // Skips the test until Clerk e2e sign-in exists (CITY-654); see ./auth.ts.
  auth: skippedAuthFixture,

  api: async ({ request }, use) => {
    const authHeaders = (token: string) => ({
      Authorization: `Bearer ${token}`,
    });

    const api: ApiFixture = {
      async createWorld(token, name?) {
        const worldName = name ?? `Test World ${Date.now()}`;
        const response = await request.post(`${API_URL}/worlds`, {
          headers: authHeaders(token),
          data: { name: worldName },
        });

        if (!response.ok()) {
          const body = await response.text();
          throw new Error(`Failed to create world: ${response.status()} - ${body}`);
        }

        return response.json();
      },

      async listWorlds(token) {
        const response = await request.get(`${API_URL}/worlds`, {
          headers: authHeaders(token),
        });

        if (!response.ok()) {
          const body = await response.text();
          throw new Error(`Failed to list worlds: ${response.status()} - ${body}`);
        }

        return response.json();
      },

      async getWorld(token, worldId) {
        const response = await request.get(`${API_URL}/worlds/${worldId}`, {
          headers: authHeaders(token),
        });

        if (!response.ok()) {
          const body = await response.text();
          throw new Error(`Failed to get world: ${response.status()} - ${body}`);
        }

        return response.json();
      },

      async generateTerrain(token, worldId, x, y) {
        const response = await request.post(
          `${API_URL}/worlds/${worldId}/tiles/${x}/${y}/generate`,
          { headers: authHeaders(token) }
        );

        if (!response.ok()) {
          const body = await response.text();
          throw new Error(`Failed to generate terrain: ${response.status()} - ${body}`);
        }

        return response.json();
      },

      async getTile(token, worldId, x, y) {
        const response = await request.get(
          `${API_URL}/worlds/${worldId}/tiles/${x}/${y}`,
          { headers: authHeaders(token) }
        );

        if (response.status() === 404) return null;

        if (!response.ok()) {
          const body = await response.text();
          throw new Error(`Failed to get tile: ${response.status()} - ${body}`);
        }

        return response.json();
      },

      async fetch(token, path, options?) {
        const url = path.startsWith("http") ? path : `${API_URL}${path}`;
        return request.fetch(url, {
          method: options?.method ?? "GET",
          headers: authHeaders(token),
          data: options?.data,
        });
      },
    };

    await use(api);
  },
});

export { expect };
