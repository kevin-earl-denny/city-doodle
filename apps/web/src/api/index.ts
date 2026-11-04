/**
 * City Doodle API client and React Query hooks.
 *
 * Usage:
 *   import { api, useWorlds, useCreateWorld } from '@/api';
 *
 *   // Direct API calls
 *   const worlds = await api.worlds.list();
 *
 *   // React Query hooks
 *   const { data: worlds } = useWorlds();
 *   const createWorld = useCreateWorld();
 */

// Types
export * from "./types";

// API client
export { api, auth, worlds, tiles, jobs, seeds } from "./client";
export { setTokenGetter, getAuthToken, getLastAuthToken } from "./client";
export type { TokenGetter } from "./client";

// React Query hooks
export * from "./hooks";
