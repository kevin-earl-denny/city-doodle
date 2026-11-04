/**
 * React Query hooks for the City Doodle API.
 */

import { useEffect, useRef } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  UseMutationOptions,
  UseQueryOptions,
} from "@tanstack/react-query";
import { api } from "./client";
import {
  AuthResponse,
  City,
  CityCreate,
  CityLimitsCreate,
  CityLimitsResponse,
  CityLimitsUpdate,
  CityUpdate,
  District,
  DistrictBulkCreate,
  DistrictCreate,
  DistrictUpdate,
  Job,
  JobCreate,
  JobProgress,
  Neighborhood,
  NeighborhoodBulkCreate,
  NeighborhoodCreate,
  NeighborhoodUpdate,
  PlacedSeed,
  PlacedSeedBulkCreate,
  PlacedSeedCreate,
  POI,
  POIBulkCreate,
  POICreate,
  POIUpdate,
  RoadEdge,
  RoadEdgeBulkCreate,
  RoadEdgeCreate,
  RoadEdgeUpdate,
  RoadNetwork,
  RoadNetworkStats,
  RoadNode,
  RoadNodeBulkCreate,
  RoadNodeCreate,
  RoadNodeUpdate,
  Tile,
  TileCreate,
  TileLock,
  TileLockCreate,
  TileUpdate,
  TransitLine,
  TransitLineBulkCreate,
  TransitLineCreate,
  TransitLineSegment,
  TransitLineSegmentBulkCreate,
  TransitLineSegmentCreate,
  TransitLineSegmentUpdate,
  TransitLineUpdate,
  TransitLineWithSegments,
  TransitNetwork,
  TransitNetworkStats,
  TransitStation,
  TransitStationBulkCreate,
  TransitStationCreate,
  TransitStationUpdate,
  UserCreate,
  UserLogin,
  UserResponse,
  World,
  WorldBriefRequest,
  WorldBriefResponse,
  WorldCreate,
  WorldUpdate,
} from "./types";

// ============================================================================
// Query Keys
// ============================================================================

export const queryKeys = {
  // Auth
  me: ["auth", "me"] as const,

  // Worlds
  worlds: ["worlds"] as const,
  world: (id: string) => ["worlds", id] as const,

  // Tiles
  worldTiles: (worldId: string) => ["worlds", worldId, "tiles"] as const,
  tile: (id: string) => ["tiles", id] as const,
  tileLock: (id: string) => ["tiles", id, "lock"] as const,

  // Jobs
  jobs: (filters?: { tileId?: string }) =>
    filters?.tileId ? (["jobs", { tileId: filters.tileId }] as const) : (["jobs"] as const),
  job: (id: string) => ["jobs", id] as const,

  // Seeds
  worldSeeds: (worldId: string) => ["worlds", worldId, "seeds"] as const,

  // Districts
  worldDistricts: (worldId: string) => ["worlds", worldId, "districts"] as const,
  district: (id: string) => ["districts", id] as const,

  // Neighborhoods
  worldNeighborhoods: (worldId: string) => ["worlds", worldId, "neighborhoods"] as const,
  neighborhood: (id: string) => ["neighborhoods", id] as const,

  // City Limits (CITY-407)
  worldCityLimits: (worldId: string) => ["worlds", worldId, "city-limits"] as const,

  // Cities (CITY-563)
  worldCities: (worldId: string) => ["worlds", worldId, "cities"] as const,
  city: (id: string) => ["cities", id] as const,

  // POIs
  worldPOIs: (worldId: string, poiType?: string) =>
    poiType
      ? (["worlds", worldId, "pois", { poiType }] as const)
      : (["worlds", worldId, "pois"] as const),
  poi: (id: string) => ["pois", id] as const,

  // Road Network
  worldRoadNetwork: (worldId: string) => ["worlds", worldId, "road-network"] as const,
  worldRoadNetworkStats: (worldId: string) => ["worlds", worldId, "road-network", "stats"] as const,
  worldRoadNodes: (worldId: string) => ["worlds", worldId, "road-nodes"] as const,
  roadNode: (id: string) => ["road-nodes", id] as const,
  worldRoadEdges: (worldId: string) => ["worlds", worldId, "road-edges"] as const,
  roadEdge: (id: string) => ["road-edges", id] as const,

  // Transit
  worldTransitNetwork: (worldId: string) => ["worlds", worldId, "transit"] as const,
  worldTransitStats: (worldId: string) => ["worlds", worldId, "transit", "stats"] as const,
  worldTransitStations: (worldId: string, stationType?: string) =>
    stationType
      ? (["worlds", worldId, "transit", "stations", { stationType }] as const)
      : (["worlds", worldId, "transit", "stations"] as const),
  transitStation: (id: string) => ["transit", "stations", id] as const,
  worldTransitLines: (worldId: string, lineType?: string) =>
    lineType
      ? (["worlds", worldId, "transit", "lines", { lineType }] as const)
      : (["worlds", worldId, "transit", "lines"] as const),
  transitLine: (id: string) => ["transit", "lines", id] as const,
  transitLineSegments: (lineId: string) => ["transit", "lines", lineId, "segments"] as const,
  transitSegment: (id: string) => ["transit", "segments", id] as const,
};

// ============================================================================
// Auth Hooks
// ============================================================================

export function useCurrentUser(
  options?: Omit<UseQueryOptions<UserResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => api.auth.me(),
    ...options,
  });
}

export function useRegister(
  options?: UseMutationOptions<AuthResponse, Error, UserCreate>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UserCreate) => api.auth.register(data),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.me, data.user);
    },
    ...options,
  });
}

export function useLogin(
  options?: UseMutationOptions<AuthResponse, Error, UserLogin>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UserLogin) => api.auth.login(data),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.me, data.user);
    },
    ...options,
  });
}

export function useLogout(options?: UseMutationOptions<void, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.auth.logout(),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: queryKeys.me });
      queryClient.removeQueries({ queryKey: queryKeys.worlds });
    },
    ...options,
  });
}

// ============================================================================
// World Hooks
// ============================================================================

export function useWorlds(
  options?: Omit<UseQueryOptions<World[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worlds,
    queryFn: () => api.worlds.list(),
    ...options,
  });
}

export function useWorld(
  worldId: string,
  options?: Omit<UseQueryOptions<World>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.world(worldId),
    queryFn: () => api.worlds.get(worldId),
    enabled: !!worldId,
    ...options,
  });
}

/**
 * Read a terrain description into a world brief (CITY-660 "Describe it").
 * Not cached: every call is a fresh model request.
 */
export function useWorldBrief(
  options?: UseMutationOptions<WorldBriefResponse, Error, WorldBriefRequest>
) {
  return useMutation({
    mutationFn: (data: WorldBriefRequest) => api.worlds.brief(data),
    ...options,
  });
}

export function useCreateWorld(
  options?: UseMutationOptions<World, Error, WorldCreate>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorldCreate) => api.worlds.create(data),
    onSuccess: (world) => {
      // Seed the individual world cache so navigating to /worlds/:id
      // doesn't need to wait for a GET that may race against the commit.
      queryClient.setQueryData(queryKeys.world(world.id), world);
      queryClient.invalidateQueries({ queryKey: queryKeys.worlds });
    },
    ...options,
  });
}

export function useUpdateWorld(
  options?: UseMutationOptions<World, Error, { worldId: string; data: WorldUpdate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.worlds.update(worldId, data),
    onSuccess: (world) => {
      queryClient.setQueryData(queryKeys.world(world.id), world);
      queryClient.invalidateQueries({ queryKey: queryKeys.worlds });
    },
    ...options,
  });
}

export function useDeleteWorld(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.worlds.delete(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.worlds });
      queryClient.removeQueries({ queryKey: queryKeys.world(worldId) });
    },
    ...options,
  });
}

// ============================================================================
// Tile Hooks
// ============================================================================

/**
 * CITY-583/585: Helper to check if a tile has real terrain features.
 * Uses terrain_status as the primary signal, falls back to inspecting features content.
 */
function tileHasTerrainFeatures(tile: Tile): boolean {
  if (tile.terrain_status === "ready") return true;
  // Fallback for tiles created before CITY-585 migration
  return (
    !!tile.features &&
    typeof tile.features === "object" &&
    "type" in tile.features &&
    tile.features.type === "FeatureCollection"
  );
}

/** CITY-585/590/614: Max number of fast poll cycles (200 * 3s = 10 minutes).
 * Coastal/bay terrain generation can take 5-7 minutes on shared-CPU workers. */
const MAX_FAST_POLL_COUNT = 200;

/** CITY-620: Slow poll interval (30s) after fast polling exhausts.
 * Ensures terrain is eventually picked up even if the worker is slow or was restarted. */
const SLOW_POLL_INTERVAL_MS = 30_000;

export function useWorldTiles(
  worldId: string,
  options?: Omit<UseQueryOptions<Tile[]>, "queryKey" | "queryFn">
) {
  // CITY-585/590: Track poll count to enforce max fast-poll safety net
  const pollCountRef = useRef(0);
  // CITY-613: Ensure the "switched to slow polling" warning is only logged once
  const hasWarnedRef = useRef(false);

  const query = useQuery({
    queryKey: queryKeys.worldTiles(worldId),
    queryFn: () => api.tiles.list(worldId),
    enabled: !!worldId,
    // CITY-620: Refetch on window focus so returning to the tab picks up ready terrain
    refetchOnWindowFocus: true,
    // CITY-583/585/590/620: Poll every 3s while tiles are pending/generating.
    // After MAX_FAST_POLL_COUNT attempts, switch to slow polling (30s) instead of stopping.
    // Stops polling only when all tiles are ready or any tile failed.
    refetchInterval: (query) => {
      const tiles = query.state.data;
      if (!tiles || tiles.length === 0) return 3000;

      // Stop polling if any tile has failed
      const anyFailed = tiles.some((t) => t.terrain_status === "failed");
      if (anyFailed) return false;

      const allReady = tiles.every(tileHasTerrainFeatures);
      if (allReady) {
        pollCountRef.current = 0;
        return false;
      }

      // CITY-620: After fast polling phase, switch to slow polling instead of stopping.
      // This ensures terrain is eventually picked up even if worker was slow/restarted.
      pollCountRef.current += 1;
      if (pollCountRef.current >= MAX_FAST_POLL_COUNT) {
        if (!hasWarnedRef.current) {
          console.warn(
            `[Terrain] Fast polling exhausted (${MAX_FAST_POLL_COUNT} attempts), switching to slow polling (${SLOW_POLL_INTERVAL_MS / 1000}s) for world ${worldId}`
          );
          hasWarnedRef.current = true;
        }
        return SLOW_POLL_INTERVAL_MS;
      }

      return 3000;
    },
    ...options,
  });

  // Reset poll count and warning flag when worldId changes
  useEffect(() => {
    pollCountRef.current = 0;
    hasWarnedRef.current = false;
  }, [worldId]);

  return query;
}

export function useTile(
  tileId: string,
  options?: Omit<UseQueryOptions<Tile>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.tile(tileId),
    queryFn: () => api.tiles.get(tileId),
    enabled: !!tileId,
    ...options,
  });
}

export function useCreateTile(
  options?: UseMutationOptions<Tile, Error, TileCreate>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TileCreate) => api.tiles.create(data),
    onSuccess: (tile) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTiles(tile.world_id),
      });
    },
    ...options,
  });
}

export function useUpdateTile(
  options?: UseMutationOptions<Tile, Error, { tileId: string; data: TileUpdate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tileId, data }) => api.tiles.update(tileId, data),
    onSuccess: (tile) => {
      queryClient.setQueryData(queryKeys.tile(tile.id), tile);
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTiles(tile.world_id),
      });
    },
    ...options,
  });
}

// ============================================================================
// Tile Lock Hooks
// ============================================================================

export function useTileLock(
  tileId: string,
  options?: Omit<UseQueryOptions<TileLock | null>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.tileLock(tileId),
    queryFn: () => api.tiles.getLock(tileId),
    enabled: !!tileId,
    ...options,
  });
}

export function useAcquireLock(
  options?: UseMutationOptions<
    TileLock,
    Error,
    { tileId: string; data?: TileLockCreate }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tileId, data }) => api.tiles.acquireLock(tileId, data),
    onSuccess: (lock) => {
      queryClient.setQueryData(queryKeys.tileLock(lock.tile_id), lock);
    },
    ...options,
  });
}

export function useReleaseLock(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tileId: string) => api.tiles.releaseLock(tileId),
    onSuccess: (_, tileId) => {
      queryClient.setQueryData(queryKeys.tileLock(tileId), null);
    },
    ...options,
  });
}

export function useHeartbeatLock(
  options?: UseMutationOptions<
    TileLock,
    Error,
    { tileId: string; durationSeconds?: number }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tileId, durationSeconds }) =>
      api.tiles.heartbeatLock(tileId, durationSeconds),
    onSuccess: (lock) => {
      queryClient.setQueryData(queryKeys.tileLock(lock.tile_id), lock);
    },
    ...options,
  });
}

// ============================================================================
// Terrain Regeneration Hook (CITY-590)
// ============================================================================

export function useRegenerateTerrain(
  options?: UseMutationOptions<Tile, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tileId: string) => api.tiles.regenerateTerrain(tileId),
    onSuccess: (tile) => {
      // Invalidate tile queries to trigger re-fetch/polling
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTiles(tile.world_id),
      });
      queryClient.setQueryData(queryKeys.tile(tile.id), tile);
    },
    ...options,
  });
}

// ============================================================================
// Job Hooks
// ============================================================================

export function useJobs(
  filters?: { tileId?: string; limit?: number },
  options?: Omit<UseQueryOptions<Job[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.jobs(filters),
    queryFn: () => api.jobs.list(filters),
    ...options,
  });
}

export function useJob(
  jobId: string,
  options?: Omit<UseQueryOptions<Job>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => api.jobs.get(jobId),
    enabled: !!jobId,
    ...options,
  });
}

export function useCreateJob(
  options?: UseMutationOptions<Job, Error, JobCreate>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: JobCreate) => api.jobs.create(data),
    onSuccess: () => {
      // CITY-497: jobs() key ["jobs"] prefix-matches ["jobs", { tileId }],
      // so a single invalidation covers both filtered and unfiltered queries.
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    },
    ...options,
  });
}

export function useCancelJob(options?: UseMutationOptions<Job, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api.jobs.cancel(jobId),
    onSuccess: (job) => {
      queryClient.setQueryData(queryKeys.job(job.id), job);
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    },
    ...options,
  });
}

export function useJobPolling(jobId: string | null) {
  const { data: job } = useQuery({
    queryKey: queryKeys.job(jobId ?? ""),
    queryFn: () => api.jobs.get(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 2000;
    },
  });

  return {
    job: job ?? null,
    status: job?.status ?? null,
    result: job?.result ?? null,
    error: job?.error ?? null,
    isPolling: !!jobId && !!job && job.status !== "completed" && job.status !== "failed",
  };
}

/**
 * CITY-626: Poll the terrain generation job for a world's center tile
 * to get incremental progress data ({completed, total}).
 *
 * Finds the most recent terrain_generation job for the center tile (tx=1, ty=1)
 * and polls it every 2s while it's running. CITY-630 moved the grid center to
 * (1,1); EditLockContext creates that tile, so it owns the terrain job.
 */
export function useTerrainJobProgress(
  tiles: Tile[] | undefined,
  isTerrainLoading: boolean,
) {
  // Find the center tile (tx=1, ty=1) to look up its terrain job
  const centerTile = tiles?.find((t) => t.tx === 1 && t.ty === 1);
  const centerTileId = centerTile?.id;

  // Fetch jobs for the center tile while terrain is loading
  const { data: tileJobs } = useQuery({
    queryKey: queryKeys.jobs(centerTileId ? { tileId: centerTileId } : undefined),
    queryFn: () => api.jobs.list({ tileId: centerTileId!, limit: 5 }),
    enabled: !!centerTileId && isTerrainLoading,
    refetchInterval: isTerrainLoading ? 2000 : false,
  });

  // Find the most recent terrain_generation job
  const terrainJob = tileJobs?.find((j) => j.type === "terrain_generation") ?? null;

  const progress: JobProgress | null = terrainJob?.progress ?? null;

  return {
    terrainJob,
    progress,
    isActive:
      !!terrainJob &&
      terrainJob.status !== "completed" &&
      terrainJob.status !== "failed" &&
      terrainJob.status !== "cancelled",
  };
}

// ============================================================================
// Seed Hooks
// ============================================================================

export function useWorldSeeds(
  worldId: string,
  options?: Omit<UseQueryOptions<PlacedSeed[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldSeeds(worldId),
    queryFn: () => api.seeds.list(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useCreateSeed(
  options?: UseMutationOptions<PlacedSeed, Error, { worldId: string; data: PlacedSeedCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.seeds.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldSeeds(worldId),
      });
    },
    ...options,
  });
}

export function useCreateSeedsBulk(
  options?: UseMutationOptions<PlacedSeed[], Error, { worldId: string; data: PlacedSeedBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.seeds.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldSeeds(worldId),
      });
    },
    ...options,
  });
}

export function useDeleteSeed(
  options?: UseMutationOptions<void, Error, { seedId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ seedId }) => api.seeds.delete(seedId),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldSeeds(worldId),
      });
    },
    ...options,
  });
}

export function useDeleteAllSeeds(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.seeds.deleteAll(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldSeeds(worldId),
      });
    },
    ...options,
  });
}

// ============================================================================
// District Hooks
// ============================================================================

export function useWorldDistricts(
  worldId: string,
  options?: Omit<UseQueryOptions<District[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldDistricts(worldId),
    queryFn: () => api.districts.list(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useDistrict(
  districtId: string,
  options?: Omit<UseQueryOptions<District>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.district(districtId),
    queryFn: () => api.districts.get(districtId),
    enabled: !!districtId,
    ...options,
  });
}

export function useCreateDistrict(
  options?: UseMutationOptions<District, Error, { worldId: string; data: Omit<DistrictCreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.districts.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldDistricts(worldId),
      });
    },
    ...options,
  });
}

export function useCreateDistrictsBulk(
  options?: UseMutationOptions<District[], Error, { worldId: string; data: DistrictBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.districts.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldDistricts(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateDistrict(
  options?: UseMutationOptions<District, Error, { districtId: string; data: DistrictUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ districtId, data }) => api.districts.update(districtId, data),
    onSuccess: (district, { worldId }) => {
      queryClient.setQueryData(queryKeys.district(district.id), district);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldDistricts(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteDistrict(
  options?: UseMutationOptions<void, Error, { districtId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ districtId }) => api.districts.delete(districtId),
    onSuccess: (_, { districtId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.district(districtId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldDistricts(worldId),
      });
    },
    ...options,
  });
}

export function useDeleteAllDistricts(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.districts.deleteAll(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldDistricts(worldId),
      });
    },
    ...options,
  });
}

// ============================================================================
// Neighborhood Hooks
// ============================================================================

export function useWorldNeighborhoods(
  worldId: string,
  options?: Omit<UseQueryOptions<Neighborhood[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldNeighborhoods(worldId),
    queryFn: () => api.neighborhoods.list(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useNeighborhood(
  neighborhoodId: string,
  options?: Omit<UseQueryOptions<Neighborhood>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.neighborhood(neighborhoodId),
    queryFn: () => api.neighborhoods.get(neighborhoodId),
    enabled: !!neighborhoodId,
    ...options,
  });
}

export function useCreateNeighborhood(
  options?: UseMutationOptions<Neighborhood, Error, { worldId: string; data: Omit<NeighborhoodCreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.neighborhoods.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldNeighborhoods(worldId),
      });
    },
    ...options,
  });
}

export function useCreateNeighborhoodsBulk(
  options?: UseMutationOptions<Neighborhood[], Error, { worldId: string; data: NeighborhoodBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.neighborhoods.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldNeighborhoods(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateNeighborhood(
  options?: UseMutationOptions<Neighborhood, Error, { neighborhoodId: string; data: NeighborhoodUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ neighborhoodId, data }) => api.neighborhoods.update(neighborhoodId, data),
    onSuccess: (neighborhood, { worldId }) => {
      queryClient.setQueryData(queryKeys.neighborhood(neighborhood.id), neighborhood);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldNeighborhoods(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteNeighborhood(
  options?: UseMutationOptions<void, Error, { neighborhoodId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ neighborhoodId }) => api.neighborhoods.delete(neighborhoodId),
    onSuccess: (_, { neighborhoodId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.neighborhood(neighborhoodId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldNeighborhoods(worldId),
      });
    },
    ...options,
  });
}

export function useDeleteAllNeighborhoods(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.neighborhoods.deleteAll(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldNeighborhoods(worldId),
      });
    },
    ...options,
  });
}

// ============================================================================
// City Limits Hooks (CITY-407)
// ============================================================================

export function useWorldCityLimits(
  worldId: string,
  options?: Omit<UseQueryOptions<CityLimitsResponse | null>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldCityLimits(worldId),
    queryFn: () => api.cityLimits.get(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useUpsertCityLimits(
  options?: UseMutationOptions<CityLimitsResponse, Error, { worldId: string; data: Omit<CityLimitsCreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.cityLimits.upsert(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldCityLimits(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateCityLimits(
  options?: UseMutationOptions<CityLimitsResponse, Error, { worldId: string; data: CityLimitsUpdate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.cityLimits.update(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldCityLimits(worldId),
      });
    },
    ...options,
  });
}

export function useDeleteCityLimits(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.cityLimits.delete(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldCityLimits(worldId),
      });
    },
    ...options,
  });
}

// ============================================================================
// City Hooks (CITY-563)
// ============================================================================

export function useWorldCities(
  worldId: string | undefined,
  options?: Omit<UseQueryOptions<City[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldCities(worldId ?? ""),
    queryFn: () => api.cities.list(worldId!),
    enabled: !!worldId,
    ...options,
  });
}

export function useCity(
  cityId: string,
  options?: Omit<UseQueryOptions<City>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.city(cityId),
    queryFn: () => api.cities.get(cityId),
    enabled: !!cityId,
    ...options,
  });
}

export function useCreateCity(
  options?: UseMutationOptions<City, Error, { worldId: string; data: CityCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.cities.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldCities(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateCity(
  options?: UseMutationOptions<City, Error, { cityId: string; data: CityUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cityId, data }) => api.cities.update(cityId, data),
    onSuccess: (city, { worldId }) => {
      queryClient.setQueryData(queryKeys.city(city.id), city);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldCities(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteCity(
  options?: UseMutationOptions<void, Error, { cityId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cityId }) => api.cities.delete(cityId),
    onSuccess: (_, { cityId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.city(cityId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldCities(worldId),
      });
      // Deleting a city cascades neighborhoods and unlinks districts
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldNeighborhoods(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldDistricts(worldId),
      });
    },
    ...options,
  });
}

// ============================================================================
// POI Hooks
// ============================================================================

export function useWorldPOIs(
  worldId: string,
  poiType?: string,
  options?: Omit<UseQueryOptions<POI[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldPOIs(worldId, poiType),
    queryFn: () => api.pois.list(worldId, poiType),
    enabled: !!worldId,
    ...options,
  });
}

export function usePOI(
  poiId: string,
  options?: Omit<UseQueryOptions<POI>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.poi(poiId),
    queryFn: () => api.pois.get(poiId),
    enabled: !!poiId,
    ...options,
  });
}

export function useCreatePOI(
  options?: UseMutationOptions<POI, Error, { worldId: string; data: Omit<POICreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.pois.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldPOIs(worldId),
      });
    },
    ...options,
  });
}

export function useCreatePOIsBulk(
  options?: UseMutationOptions<POI[], Error, { worldId: string; data: POIBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.pois.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldPOIs(worldId),
      });
    },
    ...options,
  });
}

export function useUpdatePOI(
  options?: UseMutationOptions<POI, Error, { poiId: string; data: POIUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ poiId, data }) => api.pois.update(poiId, data),
    onSuccess: (poi, { worldId }) => {
      queryClient.setQueryData(queryKeys.poi(poi.id), poi);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldPOIs(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeletePOI(
  options?: UseMutationOptions<void, Error, { poiId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ poiId }) => api.pois.delete(poiId),
    onSuccess: (_, { poiId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.poi(poiId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldPOIs(worldId),
      });
    },
    ...options,
  });
}

export function useDeleteAllPOIs(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.pois.deleteAll(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldPOIs(worldId),
      });
    },
    ...options,
  });
}

// ============================================================================
// Road Network Hooks
// ============================================================================

export function useRoadNetwork(
  worldId: string,
  options?: Omit<UseQueryOptions<RoadNetwork>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldRoadNetwork(worldId),
    queryFn: () => api.roads.getNetwork(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useRoadNetworkStats(
  worldId: string,
  options?: Omit<UseQueryOptions<RoadNetworkStats>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldRoadNetworkStats(worldId),
    queryFn: () => api.roads.getStats(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useClearRoadNetwork(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.roads.clearNetwork(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetworkStats(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNodes(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadEdges(worldId),
      });
    },
    ...options,
  });
}

// Road Node Hooks

export function useRoadNodes(
  worldId: string,
  options?: Omit<UseQueryOptions<RoadNode[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldRoadNodes(worldId),
    queryFn: () => api.roads.nodes.list(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useRoadNode(
  nodeId: string,
  options?: Omit<UseQueryOptions<RoadNode>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.roadNode(nodeId),
    queryFn: () => api.roads.nodes.get(nodeId),
    enabled: !!nodeId,
    ...options,
  });
}

export function useCreateRoadNode(
  options?: UseMutationOptions<RoadNode, Error, { worldId: string; data: Omit<RoadNodeCreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.roads.nodes.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNodes(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetworkStats(worldId),
      });
    },
    ...options,
  });
}

export function useCreateRoadNodesBulk(
  options?: UseMutationOptions<RoadNode[], Error, { worldId: string; data: RoadNodeBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.roads.nodes.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNodes(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetworkStats(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateRoadNode(
  options?: UseMutationOptions<RoadNode, Error, { nodeId: string; data: RoadNodeUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, data }) => api.roads.nodes.update(nodeId, data),
    onSuccess: (node, { worldId }) => {
      queryClient.setQueryData(queryKeys.roadNode(node.id), node);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldRoadNodes(worldId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldRoadNetwork(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteRoadNode(
  options?: UseMutationOptions<void, Error, { nodeId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId }) => api.roads.nodes.delete(nodeId),
    onSuccess: (_, { nodeId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.roadNode(nodeId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNodes(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadEdges(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetworkStats(worldId),
      });
    },
    ...options,
  });
}

// Road Edge Hooks

export function useRoadEdges(
  worldId: string,
  options?: Omit<UseQueryOptions<RoadEdge[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldRoadEdges(worldId),
    queryFn: () => api.roads.edges.list(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useRoadEdge(
  edgeId: string,
  options?: Omit<UseQueryOptions<RoadEdge>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.roadEdge(edgeId),
    queryFn: () => api.roads.edges.get(edgeId),
    enabled: !!edgeId,
    ...options,
  });
}

export function useCreateRoadEdge(
  options?: UseMutationOptions<RoadEdge, Error, { worldId: string; data: Omit<RoadEdgeCreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.roads.edges.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadEdges(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetworkStats(worldId),
      });
    },
    ...options,
  });
}

export function useCreateRoadEdgesBulk(
  options?: UseMutationOptions<RoadEdge[], Error, { worldId: string; data: RoadEdgeBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.roads.edges.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadEdges(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetworkStats(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateRoadEdge(
  options?: UseMutationOptions<RoadEdge, Error, { edgeId: string; data: RoadEdgeUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ edgeId, data }) => api.roads.edges.update(edgeId, data),
    onSuccess: (edge, { worldId }) => {
      queryClient.setQueryData(queryKeys.roadEdge(edge.id), edge);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldRoadEdges(worldId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldRoadNetwork(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteRoadEdge(
  options?: UseMutationOptions<void, Error, { edgeId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ edgeId }) => api.roads.edges.delete(edgeId),
    onSuccess: (_, { edgeId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.roadEdge(edgeId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadEdges(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldRoadNetworkStats(worldId),
      });
    },
    ...options,
  });
}

// ============================================================================
// Transit Hooks
// ============================================================================

export function useTransitNetwork(
  worldId: string,
  options?: Omit<UseQueryOptions<TransitNetwork>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldTransitNetwork(worldId),
    queryFn: () => api.transit.getNetwork(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useTransitNetworkStats(
  worldId: string,
  options?: Omit<UseQueryOptions<TransitNetworkStats>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldTransitStats(worldId),
    queryFn: () => api.transit.getStats(worldId),
    enabled: !!worldId,
    ...options,
  });
}

export function useClearTransitNetwork(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (worldId: string) => api.transit.clearNetwork(worldId),
    onSuccess: (_, worldId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStats(worldId),
      });
    },
    ...options,
  });
}

// Transit Station Hooks

export function useTransitStations(
  worldId: string,
  stationType?: string,
  options?: Omit<UseQueryOptions<TransitStation[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldTransitStations(worldId, stationType),
    queryFn: () => api.transit.stations.list(worldId, stationType),
    enabled: !!worldId,
    ...options,
  });
}

export function useTransitStation(
  stationId: string,
  options?: Omit<UseQueryOptions<TransitStation>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.transitStation(stationId),
    queryFn: () => api.transit.stations.get(stationId),
    enabled: !!stationId,
    ...options,
  });
}

export function useCreateTransitStation(
  options?: UseMutationOptions<TransitStation, Error, { worldId: string; data: Omit<TransitStationCreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.transit.stations.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStations(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStats(worldId),
      });
    },
    ...options,
  });
}

export function useCreateTransitStationsBulk(
  options?: UseMutationOptions<TransitStation[], Error, { worldId: string; data: TransitStationBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.transit.stations.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStations(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStats(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateTransitStation(
  options?: UseMutationOptions<TransitStation, Error, { stationId: string; data: TransitStationUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ stationId, data }) => api.transit.stations.update(stationId, data),
    onSuccess: (station, { worldId }) => {
      queryClient.setQueryData(queryKeys.transitStation(station.id), station);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitStations(worldId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitNetwork(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteTransitStation(
  options?: UseMutationOptions<void, Error, { stationId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ stationId }) => api.transit.stations.delete(stationId),
    onSuccess: (_, { stationId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.transitStation(stationId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStations(worldId),
      });
      // Station deletion CASCADE deletes segments, so lines are stale too
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitLines(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStats(worldId),
      });
    },
    ...options,
  });
}

// Transit Line Hooks

export function useTransitLines(
  worldId: string,
  lineType?: string,
  options?: Omit<UseQueryOptions<TransitLine[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.worldTransitLines(worldId, lineType),
    queryFn: () => api.transit.lines.list(worldId, lineType),
    enabled: !!worldId,
    ...options,
  });
}

export function useTransitLine(
  lineId: string,
  options?: Omit<UseQueryOptions<TransitLineWithSegments>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.transitLine(lineId),
    queryFn: () => api.transit.lines.get(lineId),
    enabled: !!lineId,
    ...options,
  });
}

export function useCreateTransitLine(
  options?: UseMutationOptions<TransitLine, Error, { worldId: string; data: Omit<TransitLineCreate, "world_id"> }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.transit.lines.create(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitLines(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStats(worldId),
      });
    },
    ...options,
  });
}

export function useCreateTransitLinesBulk(
  options?: UseMutationOptions<TransitLine[], Error, { worldId: string; data: TransitLineBulkCreate }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ worldId, data }) => api.transit.lines.createBulk(worldId, data),
    onSuccess: (_, { worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitLines(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStats(worldId),
      });
    },
    ...options,
  });
}

export function useUpdateTransitLine(
  options?: UseMutationOptions<TransitLine, Error, { lineId: string; data: TransitLineUpdate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lineId, data }) => api.transit.lines.update(lineId, data),
    onSuccess: (line, { worldId }) => {
      queryClient.setQueryData(queryKeys.transitLine(line.id), line);
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitLines(worldId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitNetwork(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteTransitLine(
  options?: UseMutationOptions<void, Error, { lineId: string; worldId: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lineId }) => api.transit.lines.delete(lineId),
    onSuccess: (_, { lineId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.transitLine(lineId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitLines(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitNetwork(worldId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.worldTransitStats(worldId),
      });
    },
    ...options,
  });
}

// Transit Line Segment Hooks

export function useTransitLineSegments(
  lineId: string,
  options?: Omit<UseQueryOptions<TransitLineSegment[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.transitLineSegments(lineId),
    queryFn: () => api.transit.segments.list(lineId),
    enabled: !!lineId,
    ...options,
  });
}

export function useTransitSegment(
  segmentId: string,
  options?: Omit<UseQueryOptions<TransitLineSegment>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.transitSegment(segmentId),
    queryFn: () => api.transit.segments.get(segmentId),
    enabled: !!segmentId,
    ...options,
  });
}

export function useCreateTransitLineSegment(
  options?: UseMutationOptions<TransitLineSegment, Error, { lineId: string; data: Omit<TransitLineSegmentCreate, "line_id">; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lineId, data }) => api.transit.segments.create(lineId, data),
    onSuccess: (_, { lineId, worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.transitLineSegments(lineId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.transitLine(lineId),
      });
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitNetwork(worldId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitStats(worldId),
        });
      }
    },
    ...options,
  });
}

export function useCreateTransitLineSegmentsBulk(
  options?: UseMutationOptions<TransitLineSegment[], Error, { lineId: string; data: TransitLineSegmentBulkCreate; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lineId, data }) => api.transit.segments.createBulk(lineId, data),
    onSuccess: (_, { lineId, worldId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.transitLineSegments(lineId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.transitLine(lineId),
      });
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitNetwork(worldId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitStats(worldId),
        });
      }
    },
    ...options,
  });
}

export function useUpdateTransitLineSegment(
  options?: UseMutationOptions<TransitLineSegment, Error, { segmentId: string; data: TransitLineSegmentUpdate; lineId?: string; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ segmentId, data }) => api.transit.segments.update(segmentId, data),
    onSuccess: (segment, { lineId, worldId }) => {
      queryClient.setQueryData(queryKeys.transitSegment(segment.id), segment);
      if (lineId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.transitLineSegments(lineId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.transitLine(lineId),
        });
      }
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitNetwork(worldId),
        });
      }
    },
    ...options,
  });
}

export function useDeleteTransitLineSegment(
  options?: UseMutationOptions<void, Error, { segmentId: string; lineId: string; worldId?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ segmentId }) => api.transit.segments.delete(segmentId),
    onSuccess: (_, { segmentId, lineId, worldId }) => {
      queryClient.removeQueries({ queryKey: queryKeys.transitSegment(segmentId) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.transitLineSegments(lineId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.transitLine(lineId),
      });
      if (worldId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitNetwork(worldId),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.worldTransitStats(worldId),
        });
      }
    },
    ...options,
  });
}
