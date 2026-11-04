/**
 * CITY-698: the fast-poll budget in useWorldTiles counts fetches, not
 * evaluations of refetchInterval (which TanStack runs on every re-render).
 */
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Tile } from "./types";

const listTiles = vi.fn();

vi.mock("./client", () => ({
  api: { tiles: { list: (worldId: string) => listTiles(worldId) } },
}));

import { useWorldTiles } from "./hooks";

const generatingTiles: Tile[] = [
  {
    id: "tile-1",
    world_id: "world-1",
    tx: 1,
    ty: 1,
    terrain_data: { elevation: [], water_bodies: [], vegetation: [] },
    features: {},
    terrain_status: "generating",
    terrain_error: null,
    created_at: "2026-11-04T00:00:00Z",
    updated_at: "2026-11-04T00:00:00Z",
  } as unknown as Tile,
];

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

// console.warn is spied on in beforeEach
const exhausted = () =>
  vi.mocked(console.warn).mock.calls.some((args) => String(args[0]).includes("Fast polling exhausted"));

describe("useWorldTiles fast-poll budget", () => {
  beforeEach(() => {
    listTiles.mockReset();
    listTiles.mockResolvedValue(generatingTiles);
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is not spent by re-renders between fetches", async () => {
    const { result, rerender } = renderHook(() => useWorldTiles("world-1"), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    for (let i = 0; i < 300; i++) rerender();

    expect(listTiles).toHaveBeenCalledTimes(1);
    expect(exhausted()).toBe(false);
  });

  it("switches to slow polling after 200 fetches", async () => {
    const { result } = renderHook(() => useWorldTiles("world-1"), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    for (let i = 0; i < 199 && !exhausted(); i++) {
      await result.current.refetch();
    }

    await waitFor(() => expect(exhausted()).toBe(true));
    expect(listTiles.mock.calls.length).toBeGreaterThanOrEqual(200);
  });
});
