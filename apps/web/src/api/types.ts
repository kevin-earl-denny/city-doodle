/**
 * TypeScript types matching the API Pydantic schemas.
 * These should be kept in sync with apps/api/src/city_api/schemas/
 */

// ============================================================================
// Common Types
// ============================================================================

/** UUID string type */
export type UUID = string;

/** ISO datetime string */
export type DateTime = string;

// ============================================================================
// User & Auth Types
// ============================================================================

export interface UserCreate {
  email: string;
  password: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface UserResponse {
  id: UUID;
  email: string;
  created_at: DateTime;
}

export interface SessionResponse {
  token: string;
  expires_at: DateTime;
}

export interface AuthResponse {
  user: UserResponse;
  session: SessionResponse;
}

// ============================================================================
// World Types
// ============================================================================

export type GeographicSetting =
  | "coastal"
  | "bay_harbor"
  | "river_valley"
  | "lakefront"
  | "inland"
  | "island"
  | "peninsula"
  | "delta";

export const GEOGRAPHIC_SETTINGS: {
  value: GeographicSetting;
  label: string;
  description: string;
}[] = [
  { value: "coastal", label: "Coastal", description: "City along an ocean coast with beaches" },
  { value: "bay_harbor", label: "Bay / Harbor", description: "City on a sheltered bay or natural harbor" },
  { value: "river_valley", label: "River Valley", description: "City built along a major river" },
  { value: "lakefront", label: "Lakefront", description: "City on the shore of a large lake" },
  { value: "inland", label: "Inland", description: "Landlocked city with no major water features" },
  { value: "island", label: "Island", description: "City on an island surrounded by water" },
  { value: "peninsula", label: "Peninsula", description: "City on a peninsula jutting into water" },
  { value: "delta", label: "River Delta", description: "City at a river mouth with wetlands and channels" },
];

export interface WorldSettings {
  /** Geographic setting determining water body layout */
  geographic_setting: GeographicSetting;
  /** 0 = strict grid, 1 = fully organic street layout */
  grid_organic: number;
  /** 0 = sprawling suburbs, 1 = dense urban core */
  sprawl_compact: number;
  /** 0 = historic preservation focus, 1 = modern redevelopment */
  historic_modern: number;
  /** 0 = transit-oriented, 1 = car-dependent */
  transit_car: number;
  /** Size of a city block in meters (50-300) */
  block_size_meters: number;
  /** Size of a district in meters (1000-6000) */
  district_size_meters: number;
  /** Whether to generate beaches along coastlines */
  beach_enabled: boolean;
  /** Multiplier for beach width (0.5 = narrow, 2.0 = wide) */
  beach_width_multiplier: number;
  /** Compass bearing of the main water body from the city centre, in degrees (CITY-659) */
  water_direction_deg?: number | null;
  /** Bearing of the main river's axis, in degrees (CITY-659) */
  river_axis_deg?: number | null;
  /** Terrain relief class (CITY-659) */
  relief?: Relief | null;
}

/** Default world settings */
export const DEFAULT_WORLD_SETTINGS: WorldSettings = {
  geographic_setting: "coastal",
  grid_organic: 0.5,
  sprawl_compact: 0.5,
  historic_modern: 0.5,
  transit_car: 0.5,
  block_size_meters: 150,
  district_size_meters: 3200,  // ~2 miles, yields ~4 sq mi districts
  beach_enabled: true,
  beach_width_multiplier: 1.0,
};

/** City scale presets for different city types */
export interface CityScalePreset {
  name: string;
  description: string;
  block_size_meters: number;
  district_size_meters: number;
}

export const CITY_SCALE_PRESETS: Record<string, CityScalePreset> = {
  manhattan: {
    name: "Manhattan",
    description: "Dense urban grid with small blocks (~1 sq mi districts)",
    block_size_meters: 80,
    district_size_meters: 1600,  // ~1 mile, ~1 sq mi
  },
  portland: {
    name: "Portland",
    description: "Small walkable blocks, medium districts (~2.5 sq mi)",
    block_size_meters: 100,
    district_size_meters: 2500,  // ~1.5 miles, ~2.5 sq mi
  },
  houston: {
    name: "Houston",
    description: "Large sprawling blocks and districts (~9 sq mi)",
    block_size_meters: 200,
    district_size_meters: 4800,  // ~3 miles, ~9 sq mi
  },
  european: {
    name: "European",
    description: "Irregular small blocks, compact districts (~1.5 sq mi)",
    block_size_meters: 70,
    district_size_meters: 2000,  // ~1.25 miles, ~1.5 sq mi
  },
  default: {
    name: "Default",
    description: "Standard American city layout (~4 sq mi districts)",
    block_size_meters: 150,
    district_size_meters: 3200,  // ~2 miles, ~4 sq mi
  },
};

export interface WorldCreate {
  name: string;
  seed?: number;
  settings?: Partial<WorldSettings>;
}

// ============================================================================
// World Brief ("Describe it", CITY-659 / CITY-660)
// ============================================================================

export type Relief = "flat" | "rolling" | "hilly" | "mountainous";

export type WaterSide =
  | "north"
  | "north_east"
  | "east"
  | "south_east"
  | "south"
  | "south_west"
  | "west"
  | "north_west"
  | "all_around"
  | "none";

export type RiverCourse = "none" | "straight" | "meandering" | "braided";

export type RiverAxis = "north_south" | "east_west" | "northeast_southwest" | "northwest_southeast";

export type CoastStyle = "smooth" | "varied" | "rugged" | "none";

export type GrowthStoryId =
  | "medieval_tangle"
  | "boomtown_grid"
  | "grand_boulevards"
  | "hill_town"
  | "streetcar_suburb"
  | "motor_sprawl";

/** Structured reading of a terrain description, returned by POST /worlds/brief. */
export interface WorldBrief {
  archetype: GeographicSetting;
  water_side: WaterSide;
  river: { count: number; course: RiverCourse; axis: RiverAxis | null };
  relief: Relief;
  coast: CoastStyle;
  growth_story: GrowthStoryId;
  sliders: {
    grid_organic: number;
    sprawl_compact: number;
    transit_car: number;
    historic_modern: number;
    block_size_meters: number;
    district_size_meters: number;
  };
  name: string;
  name_suggestions: string[];
  founding_year: number | null;
  founding_story: string;
  feels_like: string[];
  legend: { water: string; river: string; ground: string; streets: string };
  unsupported: string[];
}

export interface WorldBriefRequest {
  /** The player's description, 3–600 chars. Re-sent with every refinement. */
  prompt: string;
  /** The brief being refined; requires `refinement`. */
  previous?: WorldBrief;
  /** Follow-up change, up to 300 chars. */
  refinement?: string;
}

export interface WorldBriefResponse {
  brief: WorldBrief;
  /** Compiled settings, ready to pass to POST /worlds unchanged. */
  settings: WorldSettings;
  warnings: string[];
}

export interface WorldUpdate {
  name?: string;
  settings?: Partial<WorldSettings>;
}

export interface World {
  id: UUID;
  user_id: UUID;
  name: string;
  seed: number;
  settings: WorldSettings;
  created_at: DateTime;
  updated_at: DateTime;
}

// ============================================================================
// Tile Types
// ============================================================================

export interface TerrainData {
  elevation: number[][];
  water_bodies: Record<string, unknown>[];
  vegetation: Record<string, unknown>[];
}

/**
 * Legacy TileFeatures shape for non-terrain tile content.
 * No longer used by the Tile interface (CITY-582 changed features to raw dict).
 * Kept for potential future use with structured tile content.
 */
export interface TileFeatures {
  roads: Record<string, unknown>[];
  buildings: Record<string, unknown>[];
  pois: Record<string, unknown>[];
}

export interface TileCreate {
  world_id: UUID;
  tx: number;
  ty: number;
}

export interface TileUpdate {
  terrain_data?: TerrainData;
  features?: Record<string, unknown>;
}

/** Terrain generation lifecycle status */
export type TerrainStatus = "pending" | "generating" | "ready" | "failed";

export interface Tile {
  id: UUID;
  world_id: UUID;
  tx: number;
  ty: number;
  terrain_data: TerrainData;
  /**
   * CITY-582: The API now passes through the raw features dict from the DB.
   * When populated by the terrain worker this is a GeoJSON FeatureCollection
   * ({type: "FeatureCollection", features: [...]}). When empty it is {}.
   */
  features: Record<string, unknown>;
  /** CITY-585: Terrain generation lifecycle status */
  terrain_status: TerrainStatus;
  /** CITY-585: Error message if terrain generation failed */
  terrain_error: string | null;
  created_at: DateTime;
  updated_at: DateTime;
}

export interface TileLockCreate {
  duration_seconds?: number;
}

export interface TileLock {
  tile_id: UUID;
  user_id: UUID;
  locked_at: DateTime;
  expires_at: DateTime;
}

// ============================================================================
// Job Types
// ============================================================================

export type JobType =
  | "terrain_generation"
  | "seed_placement"
  | "growth_simulation"
  | "vmt_calculation"
  | "city_growth"
  | "export_png"
  | "export_gif";

export type JobStatus =
  | "pending"
  | "running"
  | "claimed"
  | "completed"
  | "failed"
  | "cancelled";

export interface JobCreate {
  type: JobType;
  tile_id?: UUID;
  params?: Record<string, unknown>;
}

/** CITY-626: Progress data for long-running jobs (e.g. terrain generation) */
export interface JobProgress {
  completed: number;
  total: number;
}

export interface Job {
  id: UUID;
  user_id: UUID;
  type: JobType;
  status: JobStatus;
  tile_id?: UUID;
  params: Record<string, unknown>;
  result?: Record<string, unknown>;
  /** CITY-626: Incremental progress for long-running jobs */
  progress?: JobProgress | null;
  error?: string;
  created_at: DateTime;
  started_at?: DateTime;
  completed_at?: DateTime;
}

// ============================================================================
// District Types
// ============================================================================

/** API district types - must match backend DistrictType enum */
export type DistrictType =
  | "residential"
  | "downtown"
  | "commercial"
  | "industrial"
  | "hospital"
  | "university"
  | "k12"
  | "park"
  | "airport";

export interface DistrictCreate {
  world_id: UUID;
  type: DistrictType;
  geometry: Record<string, unknown>;
  name?: string;
  density?: number;
  max_height?: number;
  transit_access?: boolean;
  historic?: boolean;
  street_grid?: Record<string, unknown>;
  fill_color?: string;
}

export interface DistrictUpdate {
  type?: DistrictType;
  name?: string;
  geometry?: Record<string, unknown>;
  density?: number;
  max_height?: number;
  transit_access?: boolean;
  historic?: boolean;
  street_grid?: Record<string, unknown>;
  fill_color?: string;
}

export interface DistrictBulkCreate {
  districts: DistrictCreate[];
}

export interface District {
  id: UUID;
  world_id: UUID;
  city_id?: UUID;
  type: DistrictType;
  name?: string;
  geometry: Record<string, unknown>;
  density: number;
  max_height: number;
  transit_access: boolean;
  historic: boolean;
  street_grid?: Record<string, unknown>;
  fill_color?: string;
  created_at: DateTime;
  updated_at: DateTime;
}

// ============================================================================
// Neighborhood Types
// ============================================================================

export interface NeighborhoodCreate {
  world_id: UUID;
  name: string;
  geometry: Record<string, unknown>;
  label_color?: string;
  accent_color?: string;
}

export interface NeighborhoodUpdate {
  name?: string;
  geometry?: Record<string, unknown>;
  label_color?: string;
  accent_color?: string;
}

export interface NeighborhoodBulkCreate {
  neighborhoods: NeighborhoodCreate[];
}

export interface Neighborhood {
  id: UUID;
  world_id: UUID;
  city_id?: UUID;
  name: string;
  geometry: Record<string, unknown>;
  label_color?: string;
  accent_color?: string;
  created_at: DateTime;
  updated_at: DateTime;
}

// ============================================================================
// POI Types
// ============================================================================

// Import from canonical definition to avoid duplication (CITY-404)
import type { POIType } from "../components/canvas/layers/types";
export type { POIType };

export interface POICreate {
  world_id: UUID;
  type: POIType;
  name: string;
  position_x: number;
  position_y: number;
  footprint?: Array<{ x: number; y: number }>;
}

export interface POIUpdate {
  type?: POIType;
  name?: string;
  position_x?: number;
  position_y?: number;
  footprint?: Array<{ x: number; y: number }>;
}

export interface POIBulkCreate {
  pois: POICreate[];
}

export interface POI {
  id: UUID;
  world_id: UUID;
  type: POIType;
  name: string;
  position_x: number;
  position_y: number;
  footprint?: Array<{ x: number; y: number }>;
  created_at: DateTime;
  updated_at: DateTime;
}

// ============================================================================
// City Types (CITY-563)
// ============================================================================

export type CityClassification = "core" | "suburb" | "town";

export interface CityCreate {
  name: string;
  classification: CityClassification;
  boundary: Record<string, unknown>;
  established?: number;
}

export interface CityUpdate {
  name?: string;
  classification?: CityClassification;
  boundary?: Record<string, unknown>;
  established?: number;
}

export interface City {
  id: UUID;
  world_id: UUID;
  name: string;
  classification: CityClassification;
  boundary: Record<string, unknown>;
  established?: number;
  created_at: DateTime;
  updated_at: DateTime;
}

// ============================================================================
// City Limits Types (CITY-407)
// ============================================================================

export interface CityLimitsCreate {
  world_id: UUID;
  name: string;
  boundary: Record<string, unknown>;
  established?: number;
}

export interface CityLimitsUpdate {
  name?: string;
  boundary?: Record<string, unknown>;
  established?: number;
}

export interface CityLimitsResponse {
  id: UUID;
  world_id: UUID;
  name: string;
  boundary: Record<string, unknown>;
  established?: number;
  created_at: DateTime;
  updated_at: DateTime;
}

// ============================================================================
// Placed Seed Types
// ============================================================================

export interface Position {
  x: number;
  y: number;
}

/**
 * Park size presets for configurable park placement.
 */
export type ParkSize = "pocket" | "neighborhood" | "community" | "regional" | "city";

/**
 * Metadata for park seeds.
 */
export interface ParkMetadata {
  size: ParkSize;
  name?: string;
  has_pond?: boolean;
  has_trails?: boolean;
  connected_road_id?: string;
}

export interface PlacedSeedCreate {
  seed_type_id: string;
  position: Position;
  /** Optional metadata for park-specific configuration */
  metadata?: Record<string, unknown>;
}

export interface PlacedSeedBulkCreate {
  seeds: PlacedSeedCreate[];
}

export interface PlacedSeed {
  id: UUID;
  world_id: UUID;
  seed_type_id: string;
  position: Position;
  placed_at: DateTime;
  /** Optional metadata (e.g., park size, features) */
  metadata?: Record<string, unknown>;
}

// ============================================================================
// Transit Types
// ============================================================================

export type StationType = "subway" | "rail";

export type LineType = "subway" | "rail";

export interface TransitPoint {
  x: number;
  y: number;
}

export interface TransitStationCreate {
  world_id: UUID;
  district_id: UUID;
  station_type: StationType;
  name: string;
  position_x: number;
  position_y: number;
  is_terminus?: boolean;
}

export interface TransitStationUpdate {
  district_id?: UUID;
  station_type?: StationType;
  name?: string;
  position_x?: number;
  position_y?: number;
  is_terminus?: boolean;
}

export interface TransitStation {
  id: UUID;
  world_id: UUID;
  district_id: UUID;
  station_type: StationType;
  name: string;
  position_x: number;
  position_y: number;
  is_terminus: boolean;
  created_at: DateTime;
  updated_at: DateTime;
}

export interface TransitStationBulkCreate {
  stations: TransitStationCreate[];
}

export interface TransitLineCreate {
  world_id: UUID;
  line_type: LineType;
  name: string;
  color?: string;
  is_auto_generated?: boolean;
}

export interface TransitLineUpdate {
  line_type?: LineType;
  name?: string;
  color?: string;
  is_auto_generated?: boolean;
}

export interface TransitLine {
  id: UUID;
  world_id: UUID;
  line_type: LineType;
  name: string;
  color: string;
  is_auto_generated: boolean;
  created_at: DateTime;
  updated_at: DateTime;
}

export interface TransitLineBulkCreate {
  lines: TransitLineCreate[];
}

export interface TransitLineSegmentCreate {
  line_id: UUID;
  from_station_id: UUID;
  to_station_id: UUID;
  geometry?: TransitPoint[];
  is_underground?: boolean;
  order_in_line: number;
}

export interface TransitLineSegmentUpdate {
  from_station_id?: UUID;
  to_station_id?: UUID;
  geometry?: TransitPoint[];
  is_underground?: boolean;
  order_in_line?: number;
}

export interface TransitLineSegment {
  id: UUID;
  line_id: UUID;
  from_station_id: UUID;
  to_station_id: UUID;
  geometry: TransitPoint[];
  is_underground: boolean;
  order_in_line: number;
  created_at: DateTime;
  updated_at: DateTime;
}

export interface TransitLineSegmentBulkCreate {
  segments: TransitLineSegmentCreate[];
}

export interface TransitLineWithSegments {
  id: UUID;
  world_id: UUID;
  line_type: LineType;
  name: string;
  color: string;
  is_auto_generated: boolean;
  segments: TransitLineSegment[];
  created_at: DateTime;
  updated_at: DateTime;
}

export interface TransitNetwork {
  world_id: UUID;
  stations: TransitStation[];
  lines: TransitLineWithSegments[];
}

export interface TransitNetworkStats {
  world_id: UUID;
  total_stations: number;
  total_lines: number;
  total_segments: number;
  stations_by_type: Record<string, number>;
  lines_by_type: Record<string, number>;
}

// ============================================================================
// Road Network Types
// ============================================================================

export type RoadClass = "highway" | "arterial" | "collector" | "local" | "alley" | "trail";

export type NodeType = "intersection" | "endpoint" | "roundabout" | "interchange";

export interface RoadPoint {
  x: number;
  y: number;
}

export interface RoadNodeCreate {
  world_id: UUID;
  position: RoadPoint;
  node_type?: NodeType;
  name?: string;
}

export interface RoadNodeUpdate {
  position?: RoadPoint;
  node_type?: NodeType;
  name?: string;
}

export interface RoadNode {
  id: UUID;
  world_id: UUID;
  position: RoadPoint;
  node_type: NodeType;
  name?: string;
  connected_edges: UUID[];
  created_at: DateTime;
  updated_at: DateTime;
}

export interface RoadNodeBulkCreate {
  nodes: RoadNodeCreate[];
}

export interface RoadEdgeCreate {
  world_id: UUID;
  from_node_id: UUID;
  to_node_id: UUID;
  road_class?: RoadClass;
  geometry?: RoadPoint[];
  speed_limit?: number;
  name?: string;
  is_one_way?: boolean;
  lanes?: number;
  district_id?: UUID;
}

export interface RoadEdgeUpdate {
  road_class?: RoadClass;
  geometry?: RoadPoint[];
  speed_limit?: number;
  name?: string;
  is_one_way?: boolean;
  lanes?: number;
}

export interface RoadEdge {
  id: UUID;
  world_id: UUID;
  from_node_id: UUID;
  to_node_id: UUID;
  road_class: RoadClass;
  geometry: RoadPoint[];
  length_meters: number;
  speed_limit?: number;
  name?: string;
  is_one_way: boolean;
  lanes: number;
  district_id?: UUID;
  created_at: DateTime;
  updated_at: DateTime;
}

export interface RoadEdgeBulkCreate {
  edges: RoadEdgeCreate[];
}

export interface RoadNetwork {
  world_id: UUID;
  nodes: RoadNode[];
  edges: RoadEdge[];
}

export interface RoadNetworkStats {
  world_id: UUID;
  total_nodes: number;
  total_edges: number;
  total_length_meters: number;
  edges_by_class: Record<string, number>;
  connectivity_score: number;
}

// ============================================================================
// API Error Types
// ============================================================================

export interface ApiError {
  detail: string | { message: string; [key: string]: unknown };
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}
