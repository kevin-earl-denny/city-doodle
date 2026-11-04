/**
 * Transforms backend GeoJSON terrain features into the frontend TerrainData format.
 *
 * The backend worker generates terrain as a GeoJSON FeatureCollection stored in the
 * tile's `features` column. Each Feature has a `properties.feature_type` discriminator.
 * This module converts that into the typed TerrainData structure used by rendering layers.
 *
 * CITY-438
 */

import type {
  TerrainData,
  WaterFeature,
  CoastlineFeature,
  RiverFeature,
  ContourLine,
  BeachFeature,
  BarrierIslandFeature,
  TidalFlatFeature,
  DuneRidgeFeature,
  InletFeature,
  Point,
  Polygon,
  Line,
  LakeType,
  BeachType,
} from "./types";

// ---------------------------------------------------------------------------
// GeoJSON input types (matching backend output from features_to_geojson())
// ---------------------------------------------------------------------------

interface GeoJSONFeature {
  type: "Feature";
  geometry: {
    type: string;
    coordinates: unknown;
  };
  properties: Record<string, unknown>;
}

interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

// ---------------------------------------------------------------------------
// Coordinate conversion helpers
// ---------------------------------------------------------------------------

/** Convert GeoJSON [x, y] coordinate pair to frontend Point. */
function toPoint(coord: [number, number]): Point {
  return { x: coord[0], y: coord[1] };
}

/** Convert GeoJSON Polygon coordinates to frontend Polygon (exterior ring only). */
function toPolygon(coordinates: [number, number][][]): Polygon {
  const exterior = coordinates[0];
  if (!exterior) return { points: [] };
  return { points: exterior.map(toPoint) };
}

/** Convert GeoJSON LineString coordinates to frontend Line. */
function toLine(coordinates: [number, number][], width?: number): Line {
  const line: Line = { points: coordinates.map(toPoint) };
  if (width !== undefined) line.width = width;
  return line;
}

// ---------------------------------------------------------------------------
// Validation sets
// ---------------------------------------------------------------------------

const VALID_LAKE_TYPES = new Set<string>([
  "glacial", "crater", "oxbow", "reservoir", "rift", "pond", "kettle",
]);

const VALID_BEACH_TYPES = new Set<string>(["ocean", "bay", "lake", "river"]);

// ---------------------------------------------------------------------------
// Main transformer
// ---------------------------------------------------------------------------

/**
 * Transform a GeoJSON FeatureCollection (from the tile API `features` field)
 * into the frontend TerrainData structure.
 *
 * Feature type mapping:
 * - "coastline"      (Polygon)   → water[type="ocean"] + coastlines (exterior ring as line)
 * - "lake"           (Polygon)   → water[type="lake"] with lakeType & metrics
 * - "river"          (LineString) → rivers with width
 * - "contour"        (LineString) → contours with elevation
 * - "beach"          (Polygon)   → beaches with beachType
 * - "bay"            (Polygon)   → not rendered (already inside coastline water; CITY-690)
 * - "lagoon"         (Polygon)   → water[type="ocean"]
 * - "barrier_island" (Polygon)   → barrierIslands
 * - "tidal_flat"     (Polygon)   → tidalFlats
 * - "dune_ridge"     (LineString) → duneRidges
 * - "inlet"          (Polygon)   → inlets
 */
export function transformTileFeatures(
  featureCollection: unknown
): TerrainData {
  if (!isFeatureCollection(featureCollection)) {
    return emptyTerrainData();
  }

  const water: WaterFeature[] = [];
  const coastlines: CoastlineFeature[] = [];
  const rivers: RiverFeature[] = [];
  const contours: ContourLine[] = [];
  const beaches: BeachFeature[] = [];
  const barrierIslands: BarrierIslandFeature[] = [];
  const tidalFlats: TidalFlatFeature[] = [];
  const duneRidges: DuneRidgeFeature[] = [];
  const inlets: InletFeature[] = [];

  let oceanIdx = 0;
  let lakeIdx = 0;
  let coastIdx = 0;
  let riverIdx = 0;
  let contourIdx = 0;
  let beachIdx = 0;
  let lagoonIdx = 0;
  let barrierIdx = 0;
  let tidalIdx = 0;
  let duneIdx = 0;
  let inletIdx = 0;

  for (const feature of featureCollection.features) {
    const featureType = feature.properties?.feature_type as string | undefined;
    if (!featureType) continue;

    const geom = feature.geometry;
    const props = feature.properties;

    switch (featureType) {
      case "coastline": {
        if (geom.type !== "Polygon") break;
        const coords = geom.coordinates as [number, number][][];
        oceanIdx++;
        water.push({
          id: `ocean-${oceanIdx}`,
          type: "ocean",
          polygon: toPolygon(coords),
        });

        // Extract exterior ring as a coastline line
        const exterior = coords[0];
        if (exterior && exterior.length > 1) {
          coastIdx++;
          coastlines.push({
            id: `coast-${coastIdx}`,
            line: toLine(exterior, 2),
          });
        }
        break;
      }

      case "lake": {
        if (geom.type !== "Polygon") break;
        const coords = geom.coordinates as [number, number][][];
        lakeIdx++;

        const lakeTypeRaw = props.lake_type as string | undefined;
        const lakeType: LakeType | undefined =
          lakeTypeRaw && VALID_LAKE_TYPES.has(lakeTypeRaw)
            ? (lakeTypeRaw as LakeType)
            : undefined;

        water.push({
          id: `lake-${lakeIdx}`,
          type: "lake",
          polygon: toPolygon(coords),
          lakeType,
          metrics: {
            circularity: asOptionalNumber(props.circularity),
            elongation: asOptionalNumber(props.elongation),
            avgDepth: asOptionalNumber(props.avg_depth),
            maxDepth: asOptionalNumber(props.max_depth),
          },
        });
        break;
      }

      case "river": {
        if (geom.type !== "LineString") break;
        const coords = geom.coordinates as [number, number][];
        riverIdx++;

        rivers.push({
          id: `river-${riverIdx}`,
          line: toLine(coords),
          width: (props.width as number) ?? 3,
          widths: Array.isArray(props.widths) ? (props.widths as number[]) : undefined,
          name: props.name as string | undefined,
        });
        break;
      }

      case "contour": {
        if (geom.type !== "LineString") break;
        const coords = geom.coordinates as [number, number][];
        contourIdx++;

        contours.push({
          id: `contour-${contourIdx}`,
          elevation: (props.elevation as number) ?? 0,
          line: toLine(coords),
        });
        break;
      }

      case "beach": {
        if (geom.type !== "Polygon") break;
        const coords = geom.coordinates as [number, number][][];
        beachIdx++;

        const beachTypeRaw = props.beach_type as string | undefined;
        const beachType: BeachType =
          beachTypeRaw && VALID_BEACH_TYPES.has(beachTypeRaw)
            ? (beachTypeRaw as BeachType)
            : "ocean";

        beaches.push({
          id: `beach-${beachIdx}`,
          beachType,
          polygon: toPolygon(coords),
          width: asOptionalNumber(props.width),
        });
        break;
      }

      case "bay": {
        // CITY-690: bays are exact subsets of the sea already filled by
        // coastline water.  Filling them again stacked translucent ocean
        // and showed darker patches cut off at tile borders.
        break;
      }

      case "lagoon": {
        if (geom.type !== "Polygon") break;
        const coords = geom.coordinates as [number, number][][];
        lagoonIdx++;
        water.push({
          id: `lagoon-${lagoonIdx}`,
          type: "ocean",
          polygon: toPolygon(coords),
        });
        break;
      }

      case "barrier_island": {
        if (geom.type !== "Polygon") break;
        const coords = geom.coordinates as [number, number][][];
        barrierIdx++;
        barrierIslands.push({
          id: `barrier-${barrierIdx}`,
          polygon: toPolygon(coords),
          islandIndex: asOptionalNumber(props.island_index),
          width: asOptionalNumber(props.width),
        });
        break;
      }

      case "tidal_flat": {
        if (geom.type !== "Polygon") break;
        const coords = geom.coordinates as [number, number][][];
        tidalIdx++;
        tidalFlats.push({
          id: `tidal-${tidalIdx}`,
          polygon: toPolygon(coords),
        });
        break;
      }

      case "dune_ridge": {
        if (geom.type !== "LineString") break;
        const coords = geom.coordinates as [number, number][];
        duneIdx++;
        duneRidges.push({
          id: `dune-${duneIdx}`,
          line: toLine(coords),
          height: asOptionalNumber(props.height),
        });
        break;
      }

      case "inlet": {
        if (geom.type !== "Polygon") break;
        const coords = geom.coordinates as [number, number][][];
        inletIdx++;
        inlets.push({
          id: `inlet-${inletIdx}`,
          polygon: toPolygon(coords),
          width: asOptionalNumber(props.width),
        });
        break;
      }

      default:
        break;
    }
  }

  return { water, coastlines, rivers, contours, beaches, barrierIslands, tidalFlats, duneRidges, inlets };
}

/**
 * Create empty terrain data (fallback when no tile data is available).
 */
export function emptyTerrainData(): TerrainData {
  return {
    water: [],
    coastlines: [],
    rivers: [],
    contours: [],
    beaches: [],
    barrierIslands: [],
    tidalFlats: [],
    duneRidges: [],
    inlets: [],
  };
}

// ---------------------------------------------------------------------------
// Type guards & helpers
// ---------------------------------------------------------------------------

function isFeatureCollection(value: unknown): value is GeoJSONFeatureCollection {
  if (!value || typeof value !== "object") return false;
  const obj = value as Record<string, unknown>;
  return obj.type === "FeatureCollection" && Array.isArray(obj.features);
}

function asOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

// ---------------------------------------------------------------------------
// Multi-tile composition (CITY-588)
// ---------------------------------------------------------------------------

/**
 * Compose terrain features from multiple tiles into a single TerrainData.
 * Transforms each tile's GeoJSON FeatureCollection and merges all features.
 * Feature IDs are prefixed with tile coordinates to avoid collisions.
 */
export function composeTileFeatures(
  tiles: Array<{ features: unknown; tx: number; ty: number }>
): TerrainData {
  const validTiles = tiles.filter((t) => isFeatureCollection(t.features));

  if (validTiles.length === 0) {
    return emptyTerrainData();
  }

  const water: TerrainData["water"] = [];
  const coastlines: TerrainData["coastlines"] = [];
  const rivers: TerrainData["rivers"] = [];
  const contours: TerrainData["contours"] = [];
  const beaches: TerrainData["beaches"] = [];
  const barrierIslands: TerrainData["barrierIslands"] = [];
  const tidalFlats: TerrainData["tidalFlats"] = [];
  const duneRidges: TerrainData["duneRidges"] = [];
  const inlets: TerrainData["inlets"] = [];

  for (const tile of validTiles) {
    const tileData = transformTileFeatures(tile.features);
    const prefix = `t${tile.tx}_${tile.ty}-`;

    for (const w of tileData.water) {
      water.push({ ...w, id: `${prefix}${w.id}` });
    }
    for (const c of tileData.coastlines) {
      coastlines.push({ ...c, id: `${prefix}${c.id}` });
    }
    for (const r of tileData.rivers) {
      rivers.push({ ...r, id: `${prefix}${r.id}` });
    }
    for (const ct of tileData.contours) {
      contours.push({ ...ct, id: `${prefix}${ct.id}` });
    }
    for (const b of tileData.beaches) {
      beaches.push({ ...b, id: `${prefix}${b.id}` });
    }
    for (const bi of tileData.barrierIslands) {
      barrierIslands.push({ ...bi, id: `${prefix}${bi.id}` });
    }
    for (const tf of tileData.tidalFlats) {
      tidalFlats.push({ ...tf, id: `${prefix}${tf.id}` });
    }
    for (const dr of tileData.duneRidges) {
      duneRidges.push({ ...dr, id: `${prefix}${dr.id}` });
    }
    for (const il of tileData.inlets) {
      inlets.push({ ...il, id: `${prefix}${il.id}` });
    }
  }

  console.info(
    '[Terrain] Composed %d tiles into terrain data (water=%d, coastlines=%d, rivers=%d, contours=%d, beaches=%d)',
    validTiles.length,
    water.length,
    coastlines.length,
    rivers.length,
    contours.length,
    beaches.length,
  );

  return { water, coastlines, rivers, contours, beaches, barrierIslands, tidalFlats, duneRidges, inlets };
}
