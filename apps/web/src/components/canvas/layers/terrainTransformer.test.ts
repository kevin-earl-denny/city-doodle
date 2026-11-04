import { describe, it, expect } from "vitest";
import { transformTileFeatures, emptyTerrainData, composeTileFeatures } from "./terrainTransformer";

// ---------------------------------------------------------------------------
// Helper to build a minimal GeoJSON FeatureCollection
// ---------------------------------------------------------------------------

function fc(...features: Record<string, unknown>[]) {
  return { type: "FeatureCollection", features };
}

function feature(
  featureType: string,
  geometry: Record<string, unknown>,
  extraProps: Record<string, unknown> = {}
) {
  return {
    type: "Feature",
    geometry,
    properties: { feature_type: featureType, ...extraProps },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("transformTileFeatures", () => {
  it("returns empty terrain for null/undefined input", () => {
    expect(transformTileFeatures(null)).toEqual(emptyTerrainData());
    expect(transformTileFeatures(undefined)).toEqual(emptyTerrainData());
  });

  it("returns empty terrain for invalid input", () => {
    expect(transformTileFeatures({})).toEqual(emptyTerrainData());
    expect(transformTileFeatures({ type: "Point" })).toEqual(emptyTerrainData());
    expect(transformTileFeatures("string")).toEqual(emptyTerrainData());
  });

  it("returns empty terrain for empty FeatureCollection", () => {
    expect(transformTileFeatures(fc())).toEqual(emptyTerrainData());
  });

  it("transforms coastline polygon into ocean water + coastline line", () => {
    const coords = [[[0, 0], [100, 0], [100, 50], [0, 50], [0, 0]]];
    const result = transformTileFeatures(
      fc(feature("coastline", { type: "Polygon", coordinates: coords }, { area: 5000 }))
    );

    expect(result.water).toHaveLength(1);
    expect(result.water[0].type).toBe("ocean");
    expect(result.water[0].id).toBe("ocean-1");
    expect(result.water[0].polygon.points).toHaveLength(5);
    expect(result.water[0].polygon.points[0]).toEqual({ x: 0, y: 0 });

    expect(result.coastlines).toHaveLength(1);
    expect(result.coastlines[0].id).toBe("coast-1");
    expect(result.coastlines[0].line.points).toHaveLength(5);
    expect(result.coastlines[0].line.width).toBe(2);
  });

  it("transforms lake polygon with metrics and lakeType", () => {
    const coords = [[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]];
    const result = transformTileFeatures(
      fc(
        feature("lake", { type: "Polygon", coordinates: coords }, {
          area: 100,
          lake_type: "crater",
          circularity: 0.95,
          elongation: 1.1,
          avg_depth: 0.05,
          max_depth: 0.12,
          rim_elevation: 0.4,
        })
      )
    );

    expect(result.water).toHaveLength(1);
    const lake = result.water[0];
    expect(lake.type).toBe("lake");
    expect(lake.id).toBe("lake-1");
    expect(lake.lakeType).toBe("crater");
    expect(lake.metrics).toEqual({
      circularity: 0.95,
      elongation: 1.1,
      avgDepth: 0.05,
      maxDepth: 0.12,
    });
  });

  it("handles unknown lake_type gracefully", () => {
    const coords = [[[0, 0], [1, 0], [1, 1], [0, 0]]];
    const result = transformTileFeatures(
      fc(feature("lake", { type: "Polygon", coordinates: coords }, { lake_type: "unknown_type" }))
    );
    expect(result.water[0].lakeType).toBeUndefined();
  });

  it("transforms river linestring with width", () => {
    const coords = [[0, 0], [50, 25], [100, 50]];
    const result = transformTileFeatures(
      fc(
        feature("river", { type: "LineString", coordinates: coords }, {
          width: 5.5,
          length: 111.8,
          max_flow: 42.0,
          avg_flow: 28.3,
        })
      )
    );

    expect(result.rivers).toHaveLength(1);
    const river = result.rivers[0];
    expect(river.id).toBe("river-1");
    expect(river.width).toBe(5.5);
    expect(river.line.points).toEqual([
      { x: 0, y: 0 },
      { x: 50, y: 25 },
      { x: 100, y: 50 },
    ]);
  });

  it("defaults river width to 3 when not provided", () => {
    const coords = [[0, 0], [10, 10]];
    const result = transformTileFeatures(
      fc(feature("river", { type: "LineString", coordinates: coords }))
    );
    expect(result.rivers[0].width).toBe(3);
  });

  it("transforms contour linestring with elevation", () => {
    const coords = [[0, 50], [100, 55]];
    const result = transformTileFeatures(
      fc(feature("contour", { type: "LineString", coordinates: coords }, { elevation: 0.5 }))
    );

    expect(result.contours).toHaveLength(1);
    expect(result.contours[0].elevation).toBe(0.5);
    expect(result.contours[0].id).toBe("contour-1");
  });

  it("transforms beach polygon with beachType", () => {
    const coords = [[[0, 0], [10, 0], [10, 2], [0, 2], [0, 0]]];
    const result = transformTileFeatures(
      fc(
        feature("beach", { type: "Polygon", coordinates: coords }, {
          beach_type: "bay",
          width: 2.5,
          area: 20,
        })
      )
    );

    expect(result.beaches).toHaveLength(1);
    const beach = result.beaches[0];
    expect(beach.beachType).toBe("bay");
    expect(beach.width).toBe(2.5);
    expect(beach.id).toBe("beach-1");
  });

  it("defaults beachType to ocean for unknown values", () => {
    const coords = [[[0, 0], [1, 0], [1, 1], [0, 0]]];
    const result = transformTileFeatures(
      fc(feature("beach", { type: "Polygon", coordinates: coords }, { beach_type: "swamp" }))
    );
    expect(result.beaches[0].beachType).toBe("ocean");
  });

  it("does not render bay polygons as extra water (CITY-690)", () => {
    const coords = [[[0, 0], [30, 0], [30, 20], [0, 20], [0, 0]]];
    const result = transformTileFeatures(
      fc(feature("bay", { type: "Polygon", coordinates: coords }, { bay_size: "harbor" }))
    );

    expect(result.water).toHaveLength(0);
  });

  it("transforms lagoon polygon as ocean water feature", () => {
    const coords = [[[5, 5], [15, 5], [15, 8], [5, 8], [5, 5]]];
    const result = transformTileFeatures(
      fc(feature("lagoon", { type: "Polygon", coordinates: coords }, { depth: 0.02 }))
    );

    expect(result.water).toHaveLength(1);
    expect(result.water[0].type).toBe("ocean");
    expect(result.water[0].id).toBe("lagoon-1");
  });

  it("transforms barrier_island polygon into barrierIslands array", () => {
    const coords = [[[0, 0], [20, 0], [20, 5], [0, 5], [0, 0]]];
    const result = transformTileFeatures(
      fc(
        feature("barrier_island", { type: "Polygon", coordinates: coords }, {
          island_index: 2,
          width: 5.0,
        })
      )
    );

    expect(result.barrierIslands).toHaveLength(1);
    const island = result.barrierIslands[0];
    expect(island.id).toBe("barrier-1");
    expect(island.polygon.points).toHaveLength(5);
    expect(island.polygon.points[0]).toEqual({ x: 0, y: 0 });
    expect(island.islandIndex).toBe(2);
    expect(island.width).toBe(5.0);
  });

  it("transforms tidal_flat polygon into tidalFlats array", () => {
    const coords = [[[10, 10], [30, 10], [30, 15], [10, 15], [10, 10]]];
    const result = transformTileFeatures(
      fc(feature("tidal_flat", { type: "Polygon", coordinates: coords }))
    );

    expect(result.tidalFlats).toHaveLength(1);
    const flat = result.tidalFlats[0];
    expect(flat.id).toBe("tidal-1");
    expect(flat.polygon.points).toHaveLength(5);
    expect(flat.polygon.points[0]).toEqual({ x: 10, y: 10 });
  });

  it("transforms dune_ridge linestring into duneRidges array", () => {
    const coords = [[0, 0], [10, 5], [20, 3]];
    const result = transformTileFeatures(
      fc(feature("dune_ridge", { type: "LineString", coordinates: coords }, { height: 3.5 }))
    );

    expect(result.duneRidges).toHaveLength(1);
    const dune = result.duneRidges[0];
    expect(dune.id).toBe("dune-1");
    expect(dune.line.points).toEqual([
      { x: 0, y: 0 },
      { x: 10, y: 5 },
      { x: 20, y: 3 },
    ]);
    expect(dune.height).toBe(3.5);
  });

  it("transforms inlet polygon into inlets array", () => {
    const coords = [[[5, 0], [10, 0], [10, 8], [5, 8], [5, 0]]];
    const result = transformTileFeatures(
      fc(feature("inlet", { type: "Polygon", coordinates: coords }, { width: 4.2 }))
    );

    expect(result.inlets).toHaveLength(1);
    const inlet = result.inlets[0];
    expect(inlet.id).toBe("inlet-1");
    expect(inlet.polygon.points).toHaveLength(5);
    expect(inlet.width).toBe(4.2);
  });

  it("skips barrier_island with wrong geometry type", () => {
    const result = transformTileFeatures(
      fc(feature("barrier_island", { type: "LineString", coordinates: [[0, 0], [1, 1]] }))
    );
    expect(result.barrierIslands).toHaveLength(0);
  });

  it("skips dune_ridge with wrong geometry type", () => {
    const result = transformTileFeatures(
      fc(feature("dune_ridge", { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }))
    );
    expect(result.duneRidges).toHaveLength(0);
  });

  it("skips inlet with wrong geometry type", () => {
    const result = transformTileFeatures(
      fc(feature("inlet", { type: "Point", coordinates: [5, 5] }))
    );
    expect(result.inlets).toHaveLength(0);
  });

  it("skips features with mismatched geometry type", () => {
    const result = transformTileFeatures(
      fc(feature("coastline", { type: "LineString", coordinates: [[0, 0], [1, 1]] }))
    );
    expect(result.water).toHaveLength(0);
    expect(result.coastlines).toHaveLength(0);
  });

  it("handles mixed feature types in a single collection", () => {
    const result = transformTileFeatures(
      fc(
        feature("coastline", {
          type: "Polygon",
          coordinates: [[[0, 0], [100, 0], [100, 30], [0, 30], [0, 0]]],
        }),
        feature("lake", {
          type: "Polygon",
          coordinates: [[[50, 50], [60, 50], [60, 60], [50, 50]]],
        }, { lake_type: "pond" }),
        feature("river", {
          type: "LineString",
          coordinates: [[60, 55], [80, 40], [100, 30]],
        }, { width: 4 }),
        feature("contour", {
          type: "LineString",
          coordinates: [[0, 40], [100, 45]],
        }, { elevation: 0.3 }),
        feature("beach", {
          type: "Polygon",
          coordinates: [[[0, 28], [100, 28], [100, 32], [0, 32], [0, 28]]],
        }, { beach_type: "ocean", width: 3 }),
        feature("bay", {
          type: "Polygon",
          coordinates: [[[40, 0], [60, 0], [55, 15], [45, 15], [40, 0]]],
        }),
      )
    );

    expect(result.water).toHaveLength(2); // ocean + lake (bays aren't drawn)
    expect(result.coastlines).toHaveLength(1);
    expect(result.rivers).toHaveLength(1);
    expect(result.contours).toHaveLength(1);
    expect(result.beaches).toHaveLength(1);

    expect(result.water[0].id).toBe("ocean-1");
    expect(result.water[1].id).toBe("lake-1");
  });

  it("skips features without feature_type property", () => {
    const result = transformTileFeatures({
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry: { type: "Point", coordinates: [0, 0] },
          properties: { name: "mystery" },
        },
      ],
    });
    expect(result).toEqual(emptyTerrainData());
  });
});

describe("emptyTerrainData", () => {
  it("returns all empty arrays", () => {
    const empty = emptyTerrainData();
    expect(empty.water).toEqual([]);
    expect(empty.coastlines).toEqual([]);
    expect(empty.rivers).toEqual([]);
    expect(empty.contours).toEqual([]);
    expect(empty.beaches).toEqual([]);
    expect(empty.barrierIslands).toEqual([]);
    expect(empty.tidalFlats).toEqual([]);
    expect(empty.duneRidges).toEqual([]);
    expect(empty.inlets).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// composeTileFeatures (CITY-588)
// ---------------------------------------------------------------------------

describe("composeTileFeatures", () => {
  it("returns emptyTerrainData for empty array", () => {
    expect(composeTileFeatures([])).toEqual(emptyTerrainData());
  });

  it("single tile produces same features as transformTileFeatures (with prefix)", () => {
    const collection = fc(
      feature("river", { type: "LineString", coordinates: [[0, 0], [10, 10]] }, { width: 4 }),
      feature("lake", { type: "Polygon", coordinates: [[[5, 5], [10, 5], [10, 10], [5, 5]]] }, { lake_type: "pond" }),
    );

    const single = transformTileFeatures(collection);
    const composed = composeTileFeatures([{ features: collection, tx: 0, ty: 0 }]);

    // Same number of features
    expect(composed.rivers).toHaveLength(single.rivers.length);
    expect(composed.water).toHaveLength(single.water.length);

    // IDs are prefixed with tile coordinates
    expect(composed.rivers[0].id).toBe("t0_0-river-1");
    expect(composed.water[0].id).toBe("t0_0-lake-1");

    // Data is the same apart from ID
    expect(composed.rivers[0].width).toBe(single.rivers[0].width);
    expect(composed.rivers[0].line).toEqual(single.rivers[0].line);
  });

  it("merges features from multiple tiles correctly", () => {
    const tile1 = fc(
      feature("coastline", {
        type: "Polygon",
        coordinates: [[[0, 0], [100, 0], [100, 50], [0, 50], [0, 0]]],
      }),
      feature("river", { type: "LineString", coordinates: [[0, 0], [50, 25]] }, { width: 3 }),
    );

    const tile2 = fc(
      feature("lake", {
        type: "Polygon",
        coordinates: [[[10, 10], [20, 10], [20, 20], [10, 10]]],
      }, { lake_type: "crater" }),
      feature("beach", {
        type: "Polygon",
        coordinates: [[[0, 0], [10, 0], [10, 2], [0, 0]]],
      }, { beach_type: "ocean" }),
      feature("contour", { type: "LineString", coordinates: [[0, 30], [50, 35]] }, { elevation: 0.5 }),
    );

    const result = composeTileFeatures([
      { features: tile1, tx: 0, ty: 0 },
      { features: tile2, tx: 1, ty: 0 },
    ]);

    // Tile 1: 1 ocean water + 1 coastline + 1 river
    // Tile 2: 1 lake water + 1 beach + 1 contour
    expect(result.water).toHaveLength(2); // ocean + lake
    expect(result.coastlines).toHaveLength(1);
    expect(result.rivers).toHaveLength(1);
    expect(result.contours).toHaveLength(1);
    expect(result.beaches).toHaveLength(1);
  });

  it("filters out tiles without valid FeatureCollections", () => {
    const validTile = fc(
      feature("river", { type: "LineString", coordinates: [[0, 0], [10, 10]] }, { width: 2 }),
    );

    const result = composeTileFeatures([
      { features: validTile, tx: 0, ty: 0 },
      { features: {} as unknown, tx: 1, ty: 0 },           // empty object
      { features: null as unknown, tx: 0, ty: 1 },          // null
      { features: "invalid" as unknown, tx: 1, ty: 1 },     // string
    ]);

    expect(result.rivers).toHaveLength(1);
    expect(result.rivers[0].id).toBe("t0_0-river-1");
  });

  it("returns emptyTerrainData when all tiles have invalid features", () => {
    const result = composeTileFeatures([
      { features: {} as unknown, tx: 0, ty: 0 },
      { features: null as unknown, tx: 1, ty: 0 },
    ]);

    expect(result).toEqual(emptyTerrainData());
  });

  it("prefixes feature IDs with tile coordinates to avoid collisions", () => {
    const tileA = fc(
      feature("river", { type: "LineString", coordinates: [[0, 0], [10, 10]] }, { width: 3 }),
    );
    const tileB = fc(
      feature("river", { type: "LineString", coordinates: [[20, 20], [30, 30]] }, { width: 5 }),
    );

    const result = composeTileFeatures([
      { features: tileA, tx: 0, ty: 0 },
      { features: tileB, tx: 2, ty: 1 },
    ]);

    expect(result.rivers).toHaveLength(2);
    expect(result.rivers[0].id).toBe("t0_0-river-1");
    expect(result.rivers[1].id).toBe("t2_1-river-1");

    // Verify IDs are unique
    const allIds = result.rivers.map((r) => r.id);
    expect(new Set(allIds).size).toBe(allIds.length);
  });

  it("prefixes all feature category IDs consistently", () => {
    const tile = fc(
      feature("coastline", {
        type: "Polygon",
        coordinates: [[[0, 0], [10, 0], [10, 5], [0, 5], [0, 0]]],
      }),
      feature("lake", {
        type: "Polygon",
        coordinates: [[[1, 1], [2, 1], [2, 2], [1, 1]]],
      }, { lake_type: "pond" }),
      feature("river", { type: "LineString", coordinates: [[0, 0], [5, 5]] }, { width: 2 }),
      feature("contour", { type: "LineString", coordinates: [[0, 3], [10, 3]] }, { elevation: 0.2 }),
      feature("beach", {
        type: "Polygon",
        coordinates: [[[0, 0], [10, 0], [10, 1], [0, 0]]],
      }, { beach_type: "ocean" }),
    );

    const result = composeTileFeatures([{ features: tile, tx: 3, ty: 7 }]);

    expect(result.water[0].id).toBe("t3_7-ocean-1");
    expect(result.water[1].id).toBe("t3_7-lake-1");
    expect(result.coastlines[0].id).toBe("t3_7-coast-1");
    expect(result.rivers[0].id).toBe("t3_7-river-1");
    expect(result.contours[0].id).toBe("t3_7-contour-1");
    expect(result.beaches[0].id).toBe("t3_7-beach-1");
  });
});

// ---------------------------------------------------------------------------
// CITY-586: End-to-end pipeline round-trip tests
//
// These tests use a realistic GeoJSON FeatureCollection (matching what the
// backend terrain generator actually produces) to verify the full pipeline
// from backend GeoJSON → frontend TerrainData.
// ---------------------------------------------------------------------------

/**
 * Realistic sample GeoJSON that mirrors actual backend output.
 * Contains one of each major feature type.
 */
const REALISTIC_GEOJSON = {
  type: "FeatureCollection",
  features: [
    // Coastline polygon (produces water + coastlines)
    {
      type: "Feature",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [10372.725, 2828.925],
            [10377.957, 2489.453],
            [10311.139, 2156.581],
            [10550.028, 1904.632],
            [10648.281, 1571.625],
            [10372.725, 2828.925],
          ],
        ],
      },
      properties: { feature_type: "coastline", area: 2500000 },
    },
    // Lake polygon with metrics
    {
      type: "Feature",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [5000.0, 5000.0],
            [5500.0, 5000.0],
            [5500.0, 5500.0],
            [5000.0, 5500.0],
            [5000.0, 5000.0],
          ],
        ],
      },
      properties: {
        feature_type: "lake",
        area: 250000,
        lake_type: "glacial",
        circularity: 0.78,
        elongation: 1.3,
        avg_depth: 0.04,
        max_depth: 0.09,
        rim_elevation: 0.42,
      },
    },
    // River linestring with flow data
    {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [1000.0, 500.0],
          [1200.0, 600.0],
          [1400.0, 550.0],
          [1600.0, 700.0],
          [1800.0, 900.0],
          [2000.0, 1100.0],
          [2200.0, 1300.0],
          [2400.0, 1200.0],
          [2600.0, 1400.0],
          [2800.0, 1500.0],
        ],
      },
      properties: {
        feature_type: "river",
        width: 4.5,
        length: 2100.0,
        max_flow: 35.0,
        avg_flow: 22.0,
      },
    },
    // Contour lines at different elevations
    {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [0.0, 3000.0],
          [500.0, 3100.0],
          [1000.0, 3050.0],
          [1500.0, 3200.0],
          [2000.0, 3150.0],
        ],
      },
      properties: { feature_type: "contour", elevation: 0.3 },
    },
    {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [0.0, 4000.0],
          [600.0, 4100.0],
          [1200.0, 4050.0],
        ],
      },
      properties: { feature_type: "contour", elevation: 0.5 },
    },
    // Beach polygon
    {
      type: "Feature",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [8000.0, 2800.0],
            [8500.0, 2810.0],
            [8500.0, 2850.0],
            [8000.0, 2840.0],
            [8000.0, 2800.0],
          ],
        ],
      },
      properties: {
        feature_type: "beach",
        beach_type: "ocean",
        width: 3.2,
        area: 18000,
      },
    },
    // Bay polygon
    {
      type: "Feature",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [6000.0, 1000.0],
            [7000.0, 1000.0],
            [6800.0, 1800.0],
            [6200.0, 1800.0],
            [6000.0, 1000.0],
          ],
        ],
      },
      properties: { feature_type: "bay", bay_size: "harbor" },
    },
  ],
} as const;

describe("CITY-586: pipeline round-trip with realistic GeoJSON", () => {
  it("produces non-empty arrays for all terrain categories", () => {
    const result = transformTileFeatures(REALISTIC_GEOJSON);

    expect(result.water.length).toBeGreaterThan(0);
    expect(result.coastlines.length).toBeGreaterThan(0);
    expect(result.rivers.length).toBeGreaterThan(0);
    expect(result.contours.length).toBeGreaterThan(0);
    expect(result.beaches.length).toBeGreaterThan(0);
  });

  it("assigns correct feature IDs", () => {
    const result = transformTileFeatures(REALISTIC_GEOJSON);

    // Water: ocean (from coastline) + lake; bays aren't drawn (CITY-690)
    expect(result.water).toHaveLength(2);
    expect(result.water[0].id).toBe("ocean-1");
    expect(result.water[1].id).toBe("lake-1");

    expect(result.coastlines).toHaveLength(1);
    expect(result.coastlines[0].id).toBe("coast-1");

    expect(result.rivers).toHaveLength(1);
    expect(result.rivers[0].id).toBe("river-1");

    expect(result.contours).toHaveLength(2);
    expect(result.contours[0].id).toBe("contour-1");
    expect(result.contours[1].id).toBe("contour-2");

    expect(result.beaches).toHaveLength(1);
    expect(result.beaches[0].id).toBe("beach-1");
  });

  it("correctly transforms polygon coordinates to points", () => {
    const result = transformTileFeatures(REALISTIC_GEOJSON);

    // Coastline polygon -> water[0].polygon
    const oceanPoly = result.water[0].polygon;
    expect(oceanPoly.points.length).toBe(6);
    expect(oceanPoly.points[0]).toEqual({ x: 10372.725, y: 2828.925 });
    expect(oceanPoly.points[5]).toEqual({ x: 10372.725, y: 2828.925 }); // closed ring

    // Lake polygon
    const lakePoly = result.water[1].polygon;
    expect(lakePoly.points.length).toBe(5);
    expect(lakePoly.points[0]).toEqual({ x: 5000.0, y: 5000.0 });
  });

  it("correctly transforms linestring coordinates to points", () => {
    const result = transformTileFeatures(REALISTIC_GEOJSON);

    // River
    const riverLine = result.rivers[0].line;
    expect(riverLine.points.length).toBe(10);
    expect(riverLine.points[0]).toEqual({ x: 1000.0, y: 500.0 });
    expect(riverLine.points[9]).toEqual({ x: 2800.0, y: 1500.0 });

    // Contour
    const contourLine = result.contours[0].line;
    expect(contourLine.points.length).toBe(5);
    expect(contourLine.points[0]).toEqual({ x: 0.0, y: 3000.0 });
  });

  it("preserves numeric properties (width, elevation, metrics)", () => {
    const result = transformTileFeatures(REALISTIC_GEOJSON);

    // River width
    expect(result.rivers[0].width).toBe(4.5);

    // Contour elevations
    expect(result.contours[0].elevation).toBe(0.3);
    expect(result.contours[1].elevation).toBe(0.5);

    // Beach width
    expect(result.beaches[0].width).toBe(3.2);

    // Lake metrics
    const lake = result.water[1];
    expect(lake.lakeType).toBe("glacial");
    expect(lake.metrics).toEqual({
      circularity: 0.78,
      elongation: 1.3,
      avgDepth: 0.04,
      maxDepth: 0.09,
    });
  });

  it("preserves beach type classification", () => {
    const result = transformTileFeatures(REALISTIC_GEOJSON);
    expect(result.beaches[0].beachType).toBe("ocean");
  });

  it("coastline line has default width of 2", () => {
    const result = transformTileFeatures(REALISTIC_GEOJSON);
    expect(result.coastlines[0].line.width).toBe(2);
  });

  it("survives JSON stringify → parse round-trip", () => {
    // Simulate what happens when GeoJSON is fetched from API as JSON string
    const jsonString = JSON.stringify(REALISTIC_GEOJSON);
    const parsed = JSON.parse(jsonString);
    const result = transformTileFeatures(parsed);

    expect(result.water.length).toBeGreaterThan(0);
    expect(result.coastlines.length).toBeGreaterThan(0);
    expect(result.rivers.length).toBeGreaterThan(0);
    expect(result.contours.length).toBeGreaterThan(0);
    expect(result.beaches.length).toBeGreaterThan(0);

    // Verify it matches the non-round-tripped result
    const direct = transformTileFeatures(REALISTIC_GEOJSON);
    expect(result).toEqual(direct);
  });
});
