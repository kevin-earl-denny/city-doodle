/**
 * API client for City Doodle backend.
 * Handles authentication, request formatting, and error handling.
 */

import {
  ApiClientError,
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
// Configuration
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ============================================================================
// Token Management
// ============================================================================

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
  if (token) {
    localStorage.setItem("auth_token", token);
  } else {
    localStorage.removeItem("auth_token");
  }
}

export function getAuthToken(): string | null {
  if (!authToken) {
    authToken = localStorage.getItem("auth_token");
  }
  return authToken;
}

export function clearAuthToken(): void {
  authToken = null;
  localStorage.removeItem("auth_token");
}

// ============================================================================
// Base Request Function
// ============================================================================

async function request<T>(
  method: string,
  path: string,
  options: {
    body?: unknown;
    params?: Record<string, string | number | boolean | undefined>;
    requireAuth?: boolean;
  } = {}
): Promise<T> {
  const { body, params, requireAuth = true } = options;

  // Build URL with query params
  const url = new URL(path, API_BASE_URL);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  // Build headers
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const token = getAuthToken();
  if (requireAuth && token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Make request
  const response = await fetch(url.toString(), {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // Handle errors
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    // Extract error message from API response
    let errorMessage = `API request failed: ${response.status} ${response.statusText}`;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const apiDetail = (detail as { detail: unknown }).detail;
      if (typeof apiDetail === "string") {
        errorMessage = apiDetail;
      } else if (apiDetail && typeof apiDetail === "object" && "message" in apiDetail) {
        errorMessage = String((apiDetail as { message: unknown }).message);
      }
    }
    throw new ApiClientError(errorMessage, response.status, detail);
  }

  // Handle empty responses (204 No Content)
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============================================================================
// Auth Endpoints
// ============================================================================

export const auth = {
  /** Register a new user */
  async register(data: UserCreate): Promise<AuthResponse> {
    const result = await request<AuthResponse>("POST", "/auth/register", {
      body: data,
      requireAuth: false,
    });
    setAuthToken(result.session.token);
    return result;
  },

  /** Login with email and password */
  async login(data: UserLogin): Promise<AuthResponse> {
    const result = await request<AuthResponse>("POST", "/auth/login", {
      body: data,
      requireAuth: false,
    });
    setAuthToken(result.session.token);
    return result;
  },

  /** Logout and clear session */
  async logout(): Promise<void> {
    await request<void>("POST", "/auth/logout");
    clearAuthToken();
  },

  /** Get current user info */
  async me(): Promise<UserResponse> {
    return request<UserResponse>("GET", "/auth/me");
  },
};

// ============================================================================
// World Endpoints
// ============================================================================

export const worlds = {
  /** Create a new world */
  async create(data: WorldCreate): Promise<World> {
    return request<World>("POST", "/worlds", { body: data });
  },

  /** List user's worlds */
  async list(): Promise<World[]> {
    return request<World[]>("GET", "/worlds");
  },

  /** Get a world by ID */
  async get(worldId: string): Promise<World> {
    return request<World>("GET", `/worlds/${worldId}`);
  },

  /** Update a world's name or settings */
  async update(worldId: string, data: WorldUpdate): Promise<World> {
    return request<World>("PATCH", `/worlds/${worldId}`, { body: data });
  },

  /** Delete a world */
  async delete(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}`);
  },

  /** Turn a terrain description (or a refinement of a previous brief) into a world brief and settings */
  async brief(data: WorldBriefRequest): Promise<WorldBriefResponse> {
    return request<WorldBriefResponse>("POST", "/worlds/brief", { body: data });
  },
};

// ============================================================================
// Tile Endpoints
// ============================================================================

export const tiles = {
  /** Create or get a tile at the specified coordinates */
  async create(data: TileCreate): Promise<Tile> {
    return request<Tile>("POST", `/worlds/${data.world_id}/tiles`, {
      params: { tx: data.tx, ty: data.ty },
    });
  },

  /** List tiles in a world */
  async list(worldId: string): Promise<Tile[]> {
    return request<Tile[]>("GET", `/worlds/${worldId}/tiles`);
  },

  /** Get a tile by ID */
  async get(tileId: string): Promise<Tile> {
    return request<Tile>("GET", `/tiles/${tileId}`);
  },

  /** Update a tile */
  async update(tileId: string, data: TileUpdate): Promise<Tile> {
    return request<Tile>("PATCH", `/tiles/${tileId}`, { body: data });
  },

  /** Acquire a lock on a tile */
  async acquireLock(tileId: string, data?: TileLockCreate): Promise<TileLock> {
    return request<TileLock>("POST", `/tiles/${tileId}/lock`, { body: data });
  },

  /** Release a lock on a tile */
  async releaseLock(tileId: string): Promise<void> {
    return request<void>("DELETE", `/tiles/${tileId}/lock`);
  },

  /** Get lock status for a tile */
  async getLock(tileId: string): Promise<TileLock | null> {
    return request<TileLock | null>("GET", `/tiles/${tileId}/lock`);
  },

  /** Extend a lock (heartbeat) */
  async heartbeatLock(
    tileId: string,
    durationSeconds?: number
  ): Promise<TileLock> {
    return request<TileLock>("POST", `/tiles/${tileId}/lock/heartbeat`, {
      params: { duration_seconds: durationSeconds },
    });
  },

  /** CITY-590: Re-queue terrain generation for a failed tile */
  async regenerateTerrain(tileId: string): Promise<Tile> {
    return request<Tile>("POST", `/tiles/${tileId}/regenerate-terrain`);
  },
};

// ============================================================================
// Job Endpoints
// ============================================================================

export const jobs = {
  /** Create a new job */
  async create(data: JobCreate): Promise<Job> {
    return request<Job>("POST", "/jobs", { body: data });
  },

  /** List user's jobs */
  async list(options?: { tileId?: string; limit?: number }): Promise<Job[]> {
    return request<Job[]>("GET", "/jobs", {
      params: {
        tile_id: options?.tileId,
        limit: options?.limit,
      },
    });
  },

  /** Get a job by ID */
  async get(jobId: string): Promise<Job> {
    return request<Job>("GET", `/jobs/${jobId}`);
  },

  /** Cancel a pending job */
  async cancel(jobId: string): Promise<Job> {
    return request<Job>("POST", `/jobs/${jobId}/cancel`);
  },
};

// ============================================================================
// Seed Endpoints
// ============================================================================

export const seeds = {
  /** List all placed seeds in a world */
  async list(worldId: string): Promise<PlacedSeed[]> {
    return request<PlacedSeed[]>("GET", `/worlds/${worldId}/seeds`);
  },

  /** Create a new placed seed */
  async create(worldId: string, data: PlacedSeedCreate): Promise<PlacedSeed> {
    return request<PlacedSeed>("POST", `/worlds/${worldId}/seeds`, { body: data });
  },

  /** Create multiple placed seeds in a single request */
  async createBulk(worldId: string, data: PlacedSeedBulkCreate): Promise<PlacedSeed[]> {
    return request<PlacedSeed[]>("POST", `/worlds/${worldId}/seeds/bulk`, { body: data });
  },

  /** Delete a placed seed */
  async delete(seedId: string): Promise<void> {
    return request<void>("DELETE", `/seeds/${seedId}`);
  },

  /** Delete all placed seeds in a world */
  async deleteAll(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}/seeds`);
  },
};

// ============================================================================
// District Endpoints
// ============================================================================

export const districts = {
  /** List all districts in a world */
  async list(worldId: string, options?: { historicOnly?: boolean }): Promise<District[]> {
    return request<District[]>("GET", `/worlds/${worldId}/districts`, {
      params: { historic_only: options?.historicOnly },
    });
  },

  /** Create a new district */
  async create(worldId: string, data: Omit<DistrictCreate, "world_id">): Promise<District> {
    return request<District>("POST", `/worlds/${worldId}/districts`, {
      body: { ...data, world_id: worldId },
    });
  },

  /** Create multiple districts in a single request */
  async createBulk(worldId: string, data: DistrictBulkCreate): Promise<District[]> {
    return request<District[]>("POST", `/worlds/${worldId}/districts/bulk`, { body: data });
  },

  /** Get a district by ID */
  async get(districtId: string): Promise<District> {
    return request<District>("GET", `/districts/${districtId}`);
  },

  /** Update a district */
  async update(districtId: string, data: DistrictUpdate): Promise<District> {
    return request<District>("PATCH", `/districts/${districtId}`, { body: data });
  },

  /** Delete a district */
  async delete(districtId: string): Promise<void> {
    return request<void>("DELETE", `/districts/${districtId}`);
  },

  /** Delete all districts in a world */
  async deleteAll(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}/districts`);
  },
};

// ============================================================================
// Neighborhood Endpoints
// ============================================================================

export const neighborhoods = {
  /** List all neighborhoods in a world */
  async list(worldId: string): Promise<Neighborhood[]> {
    return request<Neighborhood[]>("GET", `/worlds/${worldId}/neighborhoods`);
  },

  /** Create a new neighborhood */
  async create(worldId: string, data: Omit<NeighborhoodCreate, "world_id">): Promise<Neighborhood> {
    return request<Neighborhood>("POST", `/worlds/${worldId}/neighborhoods`, {
      body: { ...data, world_id: worldId },
    });
  },

  /** Create multiple neighborhoods in a single request */
  async createBulk(worldId: string, data: NeighborhoodBulkCreate): Promise<Neighborhood[]> {
    return request<Neighborhood[]>("POST", `/worlds/${worldId}/neighborhoods/bulk`, { body: data });
  },

  /** Get a neighborhood by ID */
  async get(neighborhoodId: string): Promise<Neighborhood> {
    return request<Neighborhood>("GET", `/neighborhoods/${neighborhoodId}`);
  },

  /** Update a neighborhood */
  async update(neighborhoodId: string, data: NeighborhoodUpdate): Promise<Neighborhood> {
    return request<Neighborhood>("PATCH", `/neighborhoods/${neighborhoodId}`, { body: data });
  },

  /** Delete a neighborhood */
  async delete(neighborhoodId: string): Promise<void> {
    return request<void>("DELETE", `/neighborhoods/${neighborhoodId}`);
  },

  /** Delete all neighborhoods in a world */
  async deleteAll(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}/neighborhoods`);
  },
};

// ============================================================================
// POI Endpoints
// ============================================================================

export const pois = {
  /** List all POIs in a world */
  async list(worldId: string, poiType?: string): Promise<POI[]> {
    return request<POI[]>("GET", `/worlds/${worldId}/pois`, {
      params: poiType ? { poi_type: poiType } : undefined,
    });
  },

  /** Create a new POI */
  async create(worldId: string, data: Omit<POICreate, "world_id">): Promise<POI> {
    return request<POI>("POST", `/worlds/${worldId}/pois`, {
      body: { ...data, world_id: worldId },
    });
  },

  /** Create multiple POIs in a single request */
  async createBulk(worldId: string, data: POIBulkCreate): Promise<POI[]> {
    return request<POI[]>("POST", `/worlds/${worldId}/pois/bulk`, { body: data });
  },

  /** Get a POI by ID */
  async get(poiId: string): Promise<POI> {
    return request<POI>("GET", `/pois/${poiId}`);
  },

  /** Update a POI */
  async update(poiId: string, data: POIUpdate): Promise<POI> {
    return request<POI>("PATCH", `/pois/${poiId}`, { body: data });
  },

  /** Delete a POI */
  async delete(poiId: string): Promise<void> {
    return request<void>("DELETE", `/pois/${poiId}`);
  },

  /** Delete all POIs in a world */
  async deleteAll(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}/pois`);
  },
};

// ============================================================================
// Road Network Endpoints
// ============================================================================

export const roads = {
  /** Get the complete road network for a world */
  async getNetwork(worldId: string): Promise<RoadNetwork> {
    return request<RoadNetwork>("GET", `/worlds/${worldId}/road-network`);
  },

  /** Get statistics about the road network */
  async getStats(worldId: string): Promise<RoadNetworkStats> {
    return request<RoadNetworkStats>("GET", `/worlds/${worldId}/road-network/stats`);
  },

  /** Clear all road nodes and edges in a world */
  async clearNetwork(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}/road-network`);
  },

  // Node endpoints
  nodes: {
    /** List all road nodes in a world */
    async list(worldId: string): Promise<RoadNode[]> {
      return request<RoadNode[]>("GET", `/worlds/${worldId}/road-nodes`);
    },

    /** Create a new road node */
    async create(worldId: string, data: Omit<RoadNodeCreate, "world_id">): Promise<RoadNode> {
      return request<RoadNode>("POST", `/worlds/${worldId}/road-nodes`, {
        body: { ...data, world_id: worldId },
      });
    },

    /** Create multiple road nodes in a single request */
    async createBulk(worldId: string, data: RoadNodeBulkCreate): Promise<RoadNode[]> {
      return request<RoadNode[]>("POST", `/worlds/${worldId}/road-nodes/bulk`, { body: data });
    },

    /** Get a road node by ID */
    async get(nodeId: string): Promise<RoadNode> {
      return request<RoadNode>("GET", `/road-nodes/${nodeId}`);
    },

    /** Update a road node */
    async update(nodeId: string, data: RoadNodeUpdate): Promise<RoadNode> {
      return request<RoadNode>("PATCH", `/road-nodes/${nodeId}`, { body: data });
    },

    /** Delete a road node */
    async delete(nodeId: string): Promise<void> {
      return request<void>("DELETE", `/road-nodes/${nodeId}`);
    },

    /** List all edges connected to a node */
    async listEdges(nodeId: string): Promise<RoadEdge[]> {
      return request<RoadEdge[]>("GET", `/road-nodes/${nodeId}/edges`);
    },
  },

  // Edge endpoints
  edges: {
    /** List all road edges in a world */
    async list(worldId: string): Promise<RoadEdge[]> {
      return request<RoadEdge[]>("GET", `/worlds/${worldId}/road-edges`);
    },

    /** Create a new road edge */
    async create(worldId: string, data: Omit<RoadEdgeCreate, "world_id">): Promise<RoadEdge> {
      return request<RoadEdge>("POST", `/worlds/${worldId}/road-edges`, {
        body: { ...data, world_id: worldId },
      });
    },

    /** Create multiple road edges in a single request */
    async createBulk(worldId: string, data: RoadEdgeBulkCreate): Promise<RoadEdge[]> {
      return request<RoadEdge[]>("POST", `/worlds/${worldId}/road-edges/bulk`, { body: data });
    },

    /** Get a road edge by ID */
    async get(edgeId: string): Promise<RoadEdge> {
      return request<RoadEdge>("GET", `/road-edges/${edgeId}`);
    },

    /** Update a road edge */
    async update(edgeId: string, data: RoadEdgeUpdate): Promise<RoadEdge> {
      return request<RoadEdge>("PATCH", `/road-edges/${edgeId}`, { body: data });
    },

    /** Delete a road edge */
    async delete(edgeId: string): Promise<void> {
      return request<void>("DELETE", `/road-edges/${edgeId}`);
    },
  },
};

// ============================================================================
// Transit Endpoints
// ============================================================================

export const transit = {
  /** Get the complete transit network for a world */
  async getNetwork(worldId: string): Promise<TransitNetwork> {
    return request<TransitNetwork>("GET", `/worlds/${worldId}/transit`);
  },

  /** Get statistics about the transit network */
  async getStats(worldId: string): Promise<TransitNetworkStats> {
    return request<TransitNetworkStats>("GET", `/worlds/${worldId}/transit/stats`);
  },

  /** Clear all transit stations and lines in a world */
  async clearNetwork(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}/transit`);
  },

  // Station endpoints
  stations: {
    /** List all transit stations in a world */
    async list(worldId: string, stationType?: string): Promise<TransitStation[]> {
      return request<TransitStation[]>("GET", `/worlds/${worldId}/transit/stations`, {
        params: { station_type: stationType },
      });
    },

    /** Create a new transit station */
    async create(worldId: string, data: Omit<TransitStationCreate, "world_id">): Promise<TransitStation> {
      return request<TransitStation>("POST", `/worlds/${worldId}/transit/stations`, {
        body: { ...data, world_id: worldId },
      });
    },

    /** Create multiple transit stations in a single request */
    async createBulk(worldId: string, data: TransitStationBulkCreate): Promise<TransitStation[]> {
      return request<TransitStation[]>("POST", `/worlds/${worldId}/transit/stations/bulk`, { body: data });
    },

    /** Get a transit station by ID */
    async get(stationId: string): Promise<TransitStation> {
      return request<TransitStation>("GET", `/transit/stations/${stationId}`);
    },

    /** Update a transit station */
    async update(stationId: string, data: TransitStationUpdate): Promise<TransitStation> {
      return request<TransitStation>("PATCH", `/transit/stations/${stationId}`, { body: data });
    },

    /** Delete a transit station */
    async delete(stationId: string): Promise<void> {
      return request<void>("DELETE", `/transit/stations/${stationId}`);
    },
  },

  // Line endpoints
  lines: {
    /** List all transit lines in a world */
    async list(worldId: string, lineType?: string): Promise<TransitLine[]> {
      return request<TransitLine[]>("GET", `/worlds/${worldId}/transit/lines`, {
        params: { line_type: lineType },
      });
    },

    /** Create a new transit line */
    async create(worldId: string, data: Omit<TransitLineCreate, "world_id">): Promise<TransitLine> {
      return request<TransitLine>("POST", `/worlds/${worldId}/transit/lines`, {
        body: { ...data, world_id: worldId },
      });
    },

    /** Create multiple transit lines in a single request */
    async createBulk(worldId: string, data: TransitLineBulkCreate): Promise<TransitLine[]> {
      return request<TransitLine[]>("POST", `/worlds/${worldId}/transit/lines/bulk`, { body: data });
    },

    /** Get a transit line by ID with all its segments */
    async get(lineId: string): Promise<TransitLineWithSegments> {
      return request<TransitLineWithSegments>("GET", `/transit/lines/${lineId}`);
    },

    /** Update a transit line */
    async update(lineId: string, data: TransitLineUpdate): Promise<TransitLine> {
      return request<TransitLine>("PATCH", `/transit/lines/${lineId}`, { body: data });
    },

    /** Delete a transit line */
    async delete(lineId: string): Promise<void> {
      return request<void>("DELETE", `/transit/lines/${lineId}`);
    },
  },

  // Segment endpoints
  segments: {
    /** List all segments of a transit line */
    async list(lineId: string): Promise<TransitLineSegment[]> {
      return request<TransitLineSegment[]>("GET", `/transit/lines/${lineId}/segments`);
    },

    /** Create a new line segment */
    async create(lineId: string, data: Omit<TransitLineSegmentCreate, "line_id">): Promise<TransitLineSegment> {
      return request<TransitLineSegment>("POST", `/transit/lines/${lineId}/segments`, {
        body: { ...data, line_id: lineId },
      });
    },

    /** Create multiple line segments in a single request */
    async createBulk(lineId: string, data: TransitLineSegmentBulkCreate): Promise<TransitLineSegment[]> {
      return request<TransitLineSegment[]>("POST", `/transit/lines/${lineId}/segments/bulk`, { body: data });
    },

    /** Get a line segment by ID */
    async get(segmentId: string): Promise<TransitLineSegment> {
      return request<TransitLineSegment>("GET", `/transit/segments/${segmentId}`);
    },

    /** Update a line segment */
    async update(segmentId: string, data: TransitLineSegmentUpdate): Promise<TransitLineSegment> {
      return request<TransitLineSegment>("PATCH", `/transit/segments/${segmentId}`, { body: data });
    },

    /** Delete a line segment */
    async delete(segmentId: string): Promise<void> {
      return request<void>("DELETE", `/transit/segments/${segmentId}`);
    },
  },
};

// ============================================================================
// City Limits Endpoints (CITY-407)
// ============================================================================

export const cityLimits = {
  /** Get city limits for a world (returns null if none set) */
  async get(worldId: string): Promise<CityLimitsResponse | null> {
    return request<CityLimitsResponse | null>("GET", `/worlds/${worldId}/city-limits`);
  },

  /** Create or replace city limits for a world */
  async upsert(worldId: string, data: Omit<CityLimitsCreate, "world_id">): Promise<CityLimitsResponse> {
    return request<CityLimitsResponse>("PUT", `/worlds/${worldId}/city-limits`, {
      body: { ...data, world_id: worldId },
    });
  },

  /** Update city limits for a world */
  async update(worldId: string, data: CityLimitsUpdate): Promise<CityLimitsResponse> {
    return request<CityLimitsResponse>("PATCH", `/worlds/${worldId}/city-limits`, { body: data });
  },

  /** Delete city limits for a world */
  async delete(worldId: string): Promise<void> {
    return request<void>("DELETE", `/worlds/${worldId}/city-limits`);
  },
};

// ============================================================================
// City Endpoints (CITY-563)
// ============================================================================

export const cities = {
  /** List all cities in a world */
  async list(worldId: string): Promise<City[]> {
    return request<City[]>("GET", `/worlds/${worldId}/cities`);
  },

  /** Create a new city */
  async create(worldId: string, data: CityCreate): Promise<City> {
    return request<City>("POST", `/worlds/${worldId}/cities`, { body: data });
  },

  /** Get a city by ID */
  async get(cityId: string): Promise<City> {
    return request<City>("GET", `/cities/${cityId}`);
  },

  /** Update a city */
  async update(cityId: string, data: CityUpdate): Promise<City> {
    return request<City>("PATCH", `/cities/${cityId}`, { body: data });
  },

  /** Delete a city (cascade: neighborhoods deleted, districts unlinked) */
  async delete(cityId: string): Promise<void> {
    return request<void>("DELETE", `/cities/${cityId}`);
  },
};

// ============================================================================
// Default Export
// ============================================================================

export const api = {
  auth,
  worlds,
  tiles,
  jobs,
  seeds,
  districts,
  neighborhoods,
  pois,
  roads,
  transit,
  cityLimits,
  cities,
};

export default api;
