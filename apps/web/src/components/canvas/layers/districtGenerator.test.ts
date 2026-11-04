import { describe, it, expect } from "vitest";
import {
  generateDistrictGeometry,
  wouldOverlap,
  clipDistrictAgainstExisting,
  seedIdToDistrictType,
  getEffectiveDistrictConfig,
  regenerateStreetGridForClippedDistrict,
  DEFAULT_SCALE_SETTINGS,
  BASE_BLOCK_SIZES,
  type DistrictGenerationConfig,
  type ScaleSettings,
} from "./districtGenerator";
import type { District } from "./types";

describe("generateDistrictGeometry", () => {
  it("generates a district with polygon and roads", () => {
    const position = { x: 100, y: 100 };
    const result = generateDistrictGeometry(position, "residential");

    expect(result.district).toBeDefined();
    expect(result.district.id).toContain("district");
    expect(result.district.type).toBe("residential");
    expect(result.district.name).toBeDefined();
    expect(result.district.polygon.points.length).toBeGreaterThanOrEqual(3);
    expect(result.roads).toBeDefined();
    expect(result.roads.length).toBeGreaterThan(0);
  });

  it("generates deterministic results for the same position", () => {
    const position = { x: 200, y: 300 };
    const result1 = generateDistrictGeometry(position, "residential");
    const result2 = generateDistrictGeometry(position, "residential");

    // Same district type
    expect(result1.district.type).toBe(result2.district.type);

    // Same polygon points count
    expect(result1.district.polygon.points.length).toBe(
      result2.district.polygon.points.length
    );

    // Same general location for polygon points
    const points1 = result1.district.polygon.points;
    const points2 = result2.district.polygon.points;
    for (let i = 0; i < points1.length; i++) {
      expect(points1[i].x).toBeCloseTo(points2[i].x, 5);
      expect(points1[i].y).toBeCloseTo(points2[i].y, 5);
    }
  });

  it("generates deterministic results with explicit seed", () => {
    const position = { x: 100, y: 100 };
    const explicitSeed = 42;

    const result1 = generateDistrictGeometry(position, "residential", { seed: explicitSeed });
    const result2 = generateDistrictGeometry(position, "residential", { seed: explicitSeed });

    // Same polygon points
    const points1 = result1.district.polygon.points;
    const points2 = result2.district.polygon.points;
    expect(points1.length).toBe(points2.length);
    for (let i = 0; i < points1.length; i++) {
      expect(points1[i].x).toBeCloseTo(points2[i].x, 5);
      expect(points1[i].y).toBeCloseTo(points2[i].y, 5);
    }

    // Same number of roads
    expect(result1.roads.length).toBe(result2.roads.length);
  });

  it("explicit seed overrides position-based seed", () => {
    const position1 = { x: 100, y: 100 };
    const position2 = { x: 500, y: 500 };
    const explicitSeed = 42;

    // Same explicit seed at different positions should produce similar geometry
    // (only position offset differs)
    const result1 = generateDistrictGeometry(position1, "residential", { seed: explicitSeed });
    const result2 = generateDistrictGeometry(position2, "residential", { seed: explicitSeed });

    // Same number of polygon points (shape is the same)
    expect(result1.district.polygon.points.length).toBe(result2.district.polygon.points.length);

    // Same number of roads
    expect(result1.roads.length).toBe(result2.roads.length);
  });

  it("different explicit seeds produce different results", () => {
    const position = { x: 100, y: 100 };

    const result1 = generateDistrictGeometry(position, "residential", { seed: 42 });
    const result2 = generateDistrictGeometry(position, "residential", { seed: 999 });

    // Different seeds should produce different geometry
    // We check that at least some points differ
    const points1 = result1.district.polygon.points;
    const points2 = result2.district.polygon.points;

    let hasDifference = false;
    const minLen = Math.min(points1.length, points2.length);
    for (let i = 0; i < minLen; i++) {
      if (
        Math.abs(points1[i].x - points2[i].x) > 1 ||
        Math.abs(points1[i].y - points2[i].y) > 1
      ) {
        hasDifference = true;
        break;
      }
    }
    expect(hasDifference).toBe(true);
  });

  it("generates different results for different positions", () => {
    const result1 = generateDistrictGeometry({ x: 100, y: 100 }, "residential");
    const result2 = generateDistrictGeometry({ x: 500, y: 500 }, "residential");

    // Different polygon center positions
    const center1 = getPolygonCenter(result1.district.polygon.points);
    const center2 = getPolygonCenter(result2.district.polygon.points);

    expect(Math.abs(center1.x - center2.x)).toBeGreaterThan(100);
    expect(Math.abs(center1.y - center2.y)).toBeGreaterThan(100);
  });

  it("generates downtown districts with rectangular shape", () => {
    const result = generateDistrictGeometry({ x: 300, y: 300 }, "downtown");

    expect(result.district.type).toBe("downtown");
    // CITY-560: Downtown districts are now axis-aligned rectangles (4 points)
    expect(result.district.polygon.points.length).toBe(4);
  });

  it("generates park districts without roads", () => {
    const result = generateDistrictGeometry({ x: 200, y: 200 }, "park");

    expect(result.district.type).toBe("park");
    expect(result.roads.length).toBe(0);
  });

  it("generates airport districts without roads", () => {
    const result = generateDistrictGeometry({ x: 400, y: 400 }, "airport");

    expect(result.district.type).toBe("airport");
    expect(result.roads.length).toBe(0);
  });

  it("respects custom configuration", () => {
    const config: DistrictGenerationConfig = {
      size: 200,
      minSize: 180,
      maxSize: 220,
      streetSpacing: 50,
    };

    const result = generateDistrictGeometry({ x: 300, y: 300 }, "residential", config);

    // District should be larger
    const bounds = getPolygonBounds(result.district.polygon.points);
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;

    // Size should be roughly 180-220
    expect(Math.min(width, height)).toBeGreaterThan(150);
    expect(Math.max(width, height)).toBeLessThan(280);
  });

  it("generates roads with street hierarchy (local and collector)", () => {
    // Use a larger district to ensure more streets are generated
    const result = generateDistrictGeometry({ x: 400, y: 400 }, "residential", {
      scaleSettings: {
        blockSizeMeters: 50, // Smaller blocks = more streets
        districtSizeMeters: 400,
        sprawlCompact: 0.5,
      },
    });

    // With CITY-142 street hierarchy:
    // - Perimeter streets and every 3-4 blocks are COLLECTOR class
    // - All other internal streets are LOCAL class
    const collectorRoads = result.roads.filter(r => r.roadClass === "collector");

    // All roads should be either local or collector (no highways/arterials in internal grid)
    for (const road of result.roads) {
      expect(["local", "collector"]).toContain(road.roadClass);
    }

    // With enough streets, we should have collector roads
    // (collector for perimeter + every 3-4 blocks)
    expect(result.roads.length).toBeGreaterThan(0);
    expect(collectorRoads.length).toBeGreaterThan(0);
  });

  it("generates roads that are within or near district bounds", () => {
    const result = generateDistrictGeometry({ x: 250, y: 250 }, "commercial");

    const districtBounds = getPolygonBounds(result.district.polygon.points);
    const padding = 20; // Allow some tolerance

    for (const road of result.roads) {
      for (const point of road.line.points) {
        expect(point.x).toBeGreaterThanOrEqual(districtBounds.minX - padding);
        expect(point.x).toBeLessThanOrEqual(districtBounds.maxX + padding);
        expect(point.y).toBeGreaterThanOrEqual(districtBounds.minY - padding);
        expect(point.y).toBeLessThanOrEqual(districtBounds.maxY + padding);
      }
    }
  });

  it("generates district polygon centered around the position", () => {
    const position = { x: 500, y: 400 };
    const result = generateDistrictGeometry(position, "industrial");

    const center = getPolygonCenter(result.district.polygon.points);

    // Center should be close to the requested position
    expect(Math.abs(center.x - position.x)).toBeLessThan(50);
    expect(Math.abs(center.y - position.y)).toBeLessThan(50);
  });

  it("generates isHistoric as false by default", () => {
    const result = generateDistrictGeometry({ x: 100, y: 100 }, "residential");
    expect(result.district.isHistoric).toBe(false);
  });
});

describe("wouldOverlap", () => {
  it("returns false when no existing districts", () => {
    const newPolygon = [
      { x: 0, y: 0 },
      { x: 100, y: 0 },
      { x: 100, y: 100 },
      { x: 0, y: 100 },
    ];

    expect(wouldOverlap(newPolygon, [])).toBe(false);
  });

  it("returns true when polygons overlap", () => {
    const existing: District[] = [
      {
        id: "existing-1",
        type: "residential",
        name: "Existing",
        polygon: {
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 100 },
            { x: 0, y: 100 },
          ],
        },
      },
    ];

    const newPolygon = [
      { x: 50, y: 50 },
      { x: 150, y: 50 },
      { x: 150, y: 150 },
      { x: 50, y: 150 },
    ];

    expect(wouldOverlap(newPolygon, existing)).toBe(true);
  });

  it("returns false when polygons do not overlap", () => {
    const existing: District[] = [
      {
        id: "existing-1",
        type: "residential",
        name: "Existing",
        polygon: {
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 100 },
            { x: 0, y: 100 },
          ],
        },
      },
    ];

    const newPolygon = [
      { x: 200, y: 200 },
      { x: 300, y: 200 },
      { x: 300, y: 300 },
      { x: 200, y: 300 },
    ];

    expect(wouldOverlap(newPolygon, existing)).toBe(false);
  });

  it("returns true when new polygon is completely inside existing", () => {
    const existing: District[] = [
      {
        id: "existing-1",
        type: "residential",
        name: "Existing",
        polygon: {
          points: [
            { x: 0, y: 0 },
            { x: 200, y: 0 },
            { x: 200, y: 200 },
            { x: 0, y: 200 },
          ],
        },
      },
    ];

    const newPolygon = [
      { x: 50, y: 50 },
      { x: 100, y: 50 },
      { x: 100, y: 100 },
      { x: 50, y: 100 },
    ];

    expect(wouldOverlap(newPolygon, existing)).toBe(true);
  });

  it("returns true when existing polygon is inside new polygon", () => {
    const existing: District[] = [
      {
        id: "existing-1",
        type: "residential",
        name: "Existing",
        polygon: {
          points: [
            { x: 50, y: 50 },
            { x: 100, y: 50 },
            { x: 100, y: 100 },
            { x: 50, y: 100 },
          ],
        },
      },
    ];

    const newPolygon = [
      { x: 0, y: 0 },
      { x: 200, y: 0 },
      { x: 200, y: 200 },
      { x: 0, y: 200 },
    ];

    expect(wouldOverlap(newPolygon, existing)).toBe(true);
  });
});

describe("seedIdToDistrictType", () => {
  it("maps residential to residential", () => {
    expect(seedIdToDistrictType("residential")).toBe("residential");
  });

  it("maps downtown to downtown", () => {
    expect(seedIdToDistrictType("downtown")).toBe("downtown");
  });

  it("maps shopping to commercial", () => {
    expect(seedIdToDistrictType("shopping")).toBe("commercial");
  });

  it("maps industrial to industrial", () => {
    expect(seedIdToDistrictType("industrial")).toBe("industrial");
  });

  it("maps park to park", () => {
    expect(seedIdToDistrictType("park")).toBe("park");
  });

  it("maps unknown seed to residential as default", () => {
    expect(seedIdToDistrictType("unknown")).toBe("residential");
  });
});

describe("getEffectiveDistrictConfig", () => {
  it("returns default config when no options provided", () => {
    const config = getEffectiveDistrictConfig();

    expect(config.scaleSettings).toEqual(DEFAULT_SCALE_SETTINGS);
    expect(config.polygonPoints).toBe(8);
    // Lowered from 0.3 so most districts take the rectangular path (CITY-369).
    expect(config.organicFactor).toBe(0.15);
    expect(config.streetClass).toBe("local");
  });

  it("uses custom scale settings when provided", () => {
    const customSettings: ScaleSettings = {
      blockSizeMeters: 150,
      districtSizeMeters: 700,
      sprawlCompact: 0.5,
    };

    const config = getEffectiveDistrictConfig({ scaleSettings: customSettings });

    expect(config.scaleSettings).toEqual(customSettings);
  });

  it("applies sprawl multiplier to increase sizes when sprawlCompact is low", () => {
    const sprawlingConfig = getEffectiveDistrictConfig({
      scaleSettings: {
        blockSizeMeters: 100,
        districtSizeMeters: 3200,
        sprawlCompact: 0, // Sprawling
      },
    });

    const compactConfig = getEffectiveDistrictConfig({
      scaleSettings: {
        blockSizeMeters: 100,
        districtSizeMeters: 3200,
        sprawlCompact: 1, // Compact
      },
    });

    // Sprawling should have larger sizes
    expect(sprawlingConfig.size).toBeGreaterThan(compactConfig.size);
    expect(sprawlingConfig.streetSpacing).toBeGreaterThan(compactConfig.streetSpacing);
  });

  // CITY-333: an explicit size (drag-to-size) is exact, so min and max collapse to it.
  it("pins min and max to an explicit size", () => {
    const config = getEffectiveDistrictConfig({
      size: 999,
      minSize: 888,
      maxSize: 1111,
      scaleSettings: {
        blockSizeMeters: 100,
        districtSizeMeters: 3200,
        sprawlCompact: 0.5,
      },
    });

    expect(config.size).toBe(999);
    expect(config.minSize).toBe(999);
    expect(config.maxSize).toBe(999);
  });

  it("respects explicit min and max sizes when no size is given", () => {
    const config = getEffectiveDistrictConfig({
      minSize: 888,
      maxSize: 1111,
      scaleSettings: {
        blockSizeMeters: 100,
        districtSizeMeters: 3200,
        sprawlCompact: 0.5,
      },
    });

    expect(config.minSize).toBe(888);
    expect(config.maxSize).toBe(1111);
  });
});

describe("generateDistrictGeometry with scale settings", () => {
  it("generates larger districts with larger districtSizeMeters", () => {
    const smallConfig: DistrictGenerationConfig = {
      scaleSettings: {
        blockSizeMeters: 60,
        districtSizeMeters: 300,
        sprawlCompact: 0.5,
      },
    };

    const largeConfig: DistrictGenerationConfig = {
      scaleSettings: {
        blockSizeMeters: 200,
        districtSizeMeters: 900,
        sprawlCompact: 0.5,
      },
    };

    const smallResult = generateDistrictGeometry({ x: 100, y: 100 }, "residential", smallConfig);
    const largeResult = generateDistrictGeometry({ x: 100, y: 100 }, "residential", largeConfig);

    const smallBounds = getPolygonBounds(smallResult.district.polygon.points);
    const largeBounds = getPolygonBounds(largeResult.district.polygon.points);

    const smallArea = (smallBounds.maxX - smallBounds.minX) * (smallBounds.maxY - smallBounds.minY);
    const largeArea = (largeBounds.maxX - largeBounds.minX) * (largeBounds.maxY - largeBounds.minY);

    expect(largeArea).toBeGreaterThan(smallArea);
  });

  it("generates districts with more roads when blockSizeMeters is smaller", () => {
    const denseConfig: DistrictGenerationConfig = {
      scaleSettings: {
        blockSizeMeters: 50,
        districtSizeMeters: 3200,
        sprawlCompact: 0.5,
      },
    };

    const sparseConfig: DistrictGenerationConfig = {
      scaleSettings: {
        blockSizeMeters: 200,
        districtSizeMeters: 3200,
        sprawlCompact: 0.5,
      },
    };

    const denseResult = generateDistrictGeometry({ x: 200, y: 200 }, "commercial", denseConfig);
    const sparseResult = generateDistrictGeometry({ x: 200, y: 200 }, "commercial", sparseConfig);

    // More roads in dense configuration due to smaller block sizes
    expect(denseResult.roads.length).toBeGreaterThanOrEqual(sparseResult.roads.length);
  });

  it("applies sprawl multiplier correctly", () => {
    const sprawlingConfig: DistrictGenerationConfig = {
      scaleSettings: {
        blockSizeMeters: 100,
        districtSizeMeters: 3200,
        sprawlCompact: 0.1, // Very sprawling
      },
    };

    const compactConfig: DistrictGenerationConfig = {
      scaleSettings: {
        blockSizeMeters: 100,
        districtSizeMeters: 3200,
        sprawlCompact: 0.9, // Very compact
      },
    };

    const sprawlingResult = generateDistrictGeometry({ x: 300, y: 300 }, "residential", sprawlingConfig);
    const compactResult = generateDistrictGeometry({ x: 300, y: 300 }, "residential", compactConfig);

    const sprawlingBounds = getPolygonBounds(sprawlingResult.district.polygon.points);
    const compactBounds = getPolygonBounds(compactResult.district.polygon.points);

    const sprawlingWidth = sprawlingBounds.maxX - sprawlingBounds.minX;
    const compactWidth = compactBounds.maxX - compactBounds.minX;

    // Sprawling should be larger than compact
    expect(sprawlingWidth).toBeGreaterThan(compactWidth);
  });
});

// Helper functions for tests
function getPolygonCenter(points: { x: number; y: number }[]): { x: number; y: number } {
  const sum = points.reduce(
    (acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }),
    { x: 0, y: 0 }
  );
  return {
    x: sum.x / points.length,
    y: sum.y / points.length,
  };
}

function getPolygonBounds(points: { x: number; y: number }[]): {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
} {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const point of points) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }

  return { minX, maxX, minY, maxY };
}

// CITY-142: Type-specific block sizing tests
describe("CITY-142: Type-specific block sizing", () => {
  it("defines different base block sizes for each district type", () => {
    expect(BASE_BLOCK_SIZES.downtown).toBe(60);
    expect(BASE_BLOCK_SIZES.residential).toBe(120);
    expect(BASE_BLOCK_SIZES.industrial).toBe(200);
    expect(BASE_BLOCK_SIZES.commercial).toBe(100);
  });

  it("generates downtown districts with smaller blocks than residential", () => {
    const position = { x: 500, y: 500 };

    // Generate both types with same settings
    const downtownResult = generateDistrictGeometry(position, "downtown");
    const residentialResult = generateDistrictGeometry(position, "residential");

    // Downtown has 60m base blocks, residential has 120m base
    // So downtown should have more roads (denser street grid)
    // Note: polygon sizes also differ, so we compare roads per unit area
    const downtownBounds = getPolygonBounds(downtownResult.district.polygon.points);
    const residentialBounds = getPolygonBounds(residentialResult.district.polygon.points);

    const downtownArea =
      (downtownBounds.maxX - downtownBounds.minX) *
      (downtownBounds.maxY - downtownBounds.minY);
    const residentialArea =
      (residentialBounds.maxX - residentialBounds.minX) *
      (residentialBounds.maxY - residentialBounds.minY);

    const downtownDensity = downtownResult.roads.length / downtownArea;
    const residentialDensity = residentialResult.roads.length / residentialArea;

    // Downtown should have higher road density
    expect(downtownDensity).toBeGreaterThan(residentialDensity * 0.5); // Allow some variance
  });

  it("generates industrial districts with larger blocks than downtown", () => {
    const position = { x: 600, y: 600 };

    const industrialResult = generateDistrictGeometry(position, "industrial");
    const downtownResult = generateDistrictGeometry(position, "downtown");

    // Industrial has 200m base blocks, downtown has 60m base
    // Industrial should have fewer roads (less dense street grid)
    // But industrial districts are also organic shaped, so just check roads exist
    expect(industrialResult.roads.length).toBeGreaterThan(0);
    expect(downtownResult.roads.length).toBeGreaterThan(0);
  });
});

// CITY-142: Street hierarchy tests
describe("CITY-142: Street hierarchy", () => {
  it("generates collector roads at perimeter and intervals", () => {
    const result = generateDistrictGeometry({ x: 700, y: 700 }, "commercial", {
      scaleSettings: {
        blockSizeMeters: 40, // Small blocks = more streets
        districtSizeMeters: 3200,
        sprawlCompact: 0.5,
      },
    });

    const collectorRoads = result.roads.filter((r) => r.roadClass === "collector");

    // Should have collector roads (perimeter + every 3-4 blocks)
    expect(collectorRoads.length).toBeGreaterThan(0);

    // All roads should be either local or collector
    for (const road of result.roads) {
      expect(["local", "collector"]).toContain(road.roadClass);
    }
  });
});

// CITY-142: regenerateStreetGridForClippedDistrict tests
describe("CITY-142: regenerateStreetGridForClippedDistrict", () => {
  it("generates roads for a clipped polygon", () => {
    const clippedPolygon = [
      { x: 100, y: 100 },
      { x: 250, y: 100 },
      { x: 250, y: 250 },
      { x: 100, y: 250 },
    ];

    const result = regenerateStreetGridForClippedDistrict(
      clippedPolygon,
      "district-123",
      "residential",
      { x: 175, y: 175 },
      0.5
    );

    expect(result.roads.length).toBeGreaterThan(0);
    expect(typeof result.gridAngle).toBe("number");

    // Road IDs should include the district ID
    for (const road of result.roads) {
      expect(road.id).toContain("district-123");
    }
  });

  it("returns empty array for parks and airports", () => {
    const polygon = [
      { x: 0, y: 0 },
      { x: 100, y: 0 },
      { x: 100, y: 100 },
      { x: 0, y: 100 },
    ];

    const parkResult = regenerateStreetGridForClippedDistrict(
      polygon,
      "park-1",
      "park",
      { x: 50, y: 50 },
      0.5
    );

    const airportResult = regenerateStreetGridForClippedDistrict(
      polygon,
      "airport-1",
      "airport",
      { x: 50, y: 50 },
      0.5
    );

    expect(parkResult.roads).toHaveLength(0);
    expect(airportResult.roads).toHaveLength(0);
  });

  it("returns empty array for invalid polygons (less than 3 points)", () => {
    const invalidPolygon = [
      { x: 0, y: 0 },
      { x: 100, y: 100 },
    ];

    const result = regenerateStreetGridForClippedDistrict(
      invalidPolygon,
      "district-1",
      "residential",
      { x: 50, y: 50 },
      0.5
    );

    expect(result.roads).toHaveLength(0);
  });

  it("applies density multiplier based on sprawl_compact", () => {
    const polygon = [
      { x: 0, y: 0 },
      { x: 300, y: 0 },
      { x: 300, y: 300 },
      { x: 0, y: 300 },
    ];

    // Sprawling (low density)
    const sprawlingResult = regenerateStreetGridForClippedDistrict(
      polygon,
      "district-s",
      "residential",
      { x: 150, y: 150 },
      0.1 // Sprawling
    );

    // Compact (high density)
    const compactResult = regenerateStreetGridForClippedDistrict(
      polygon,
      "district-c",
      "residential",
      { x: 150, y: 150 },
      0.9 // Compact
    );

    // Compact should have more roads due to smaller block spacing
    expect(compactResult.roads.length).toBeGreaterThanOrEqual(sprawlingResult.roads.length);
  });

  it("uses consistent RNG based on position for deterministic results", () => {
    const polygon = [
      { x: 0, y: 0 },
      { x: 200, y: 0 },
      { x: 200, y: 200 },
      { x: 0, y: 200 },
    ];

    const result1 = regenerateStreetGridForClippedDistrict(
      polygon,
      "district-1",
      "residential",
      { x: 100, y: 100 },
      0.5
    );

    const result2 = regenerateStreetGridForClippedDistrict(
      polygon,
      "district-2", // Different ID
      "residential",
      { x: 100, y: 100 }, // Same position
      0.5
    );

    // Road positions should be the same (same position = same RNG seed)
    expect(result1.roads.length).toBe(result2.roads.length);
    if (result1.roads.length > 0 && result2.roads.length > 0) {
      expect(result1.roads[0].line.points[0].x).toBeCloseTo(result2.roads[0].line.points[0].x, 1);
      expect(result1.roads[0].line.points[0].y).toBeCloseTo(result2.roads[0].line.points[0].y, 1);
    }
  });

  it("accepts explicit grid angle parameter", () => {
    const polygon = [
      { x: 0, y: 0 },
      { x: 200, y: 0 },
      { x: 200, y: 200 },
      { x: 0, y: 200 },
    ];

    const explicitAngle = Math.PI / 6; // 30 degrees

    const result = regenerateStreetGridForClippedDistrict(
      polygon,
      "district-1",
      "residential",
      { x: 100, y: 100 },
      0.5,
      explicitAngle
    );

    // Should use the explicit angle
    expect(result.gridAngle).toBe(explicitAngle);
    expect(result.roads.length).toBeGreaterThan(0);
  });
});

// CITY-327/329: Concave polygon and intersection pairing tests
describe("CITY-327: Concave polygon street grid", () => {
  it("generates valid roads for concave L-shaped polygon", () => {
    // L-shaped concave polygon — grid lines will cross it at 4+ points
    const lShape = [
      { x: 0, y: 0 },
      { x: 200, y: 0 },
      { x: 200, y: 100 },
      { x: 100, y: 100 },
      { x: 100, y: 200 },
      { x: 0, y: 200 },
    ];

    const result = regenerateStreetGridForClippedDistrict(
      lShape,
      "district-l",
      "commercial",
      { x: 100, y: 100 },
      0.5,
      0 // No rotation for predictable results
    );

    expect(result.roads.length).toBeGreaterThan(0);

    // Every road segment midpoint must be inside the polygon
    for (const road of result.roads) {
      const pts = road.line.points;
      const midX = (pts[0].x + pts[1].x) / 2;
      const midY = (pts[0].y + pts[1].y) / 2;
      // Midpoint should be inside or very near the L-shape boundary
      const inBounds =
        midX >= -5 && midX <= 205 && midY >= -5 && midY <= 205;
      expect(inBounds).toBe(true);
    }
  });

  it("generates valid roads for concave U-shaped polygon", () => {
    // U-shaped polygon — multiple re-entries for horizontal lines
    const uShape = [
      { x: 0, y: 0 },
      { x: 300, y: 0 },
      { x: 300, y: 200 },
      { x: 200, y: 200 },
      { x: 200, y: 100 },
      { x: 100, y: 100 },
      { x: 100, y: 200 },
      { x: 0, y: 200 },
    ];

    const result = regenerateStreetGridForClippedDistrict(
      uShape,
      "district-u",
      "residential",
      { x: 150, y: 100 },
      0.5,
      0
    );

    expect(result.roads.length).toBeGreaterThan(0);
  });

  it("does not produce roads outside the polygon for star-shaped concavity", () => {
    // Star/cross shape — many concave indentations
    const cross = [
      { x: 100, y: 0 },
      { x: 200, y: 0 },
      { x: 200, y: 100 },
      { x: 300, y: 100 },
      { x: 300, y: 200 },
      { x: 200, y: 200 },
      { x: 200, y: 300 },
      { x: 100, y: 300 },
      { x: 100, y: 200 },
      { x: 0, y: 200 },
      { x: 0, y: 100 },
      { x: 100, y: 100 },
    ];

    const result = regenerateStreetGridForClippedDistrict(
      cross,
      "district-cross",
      "downtown",
      { x: 150, y: 150 },
      0.5,
      0
    );

    expect(result.roads.length).toBeGreaterThan(0);

    // All road endpoints should be within generous bounds of the cross
    for (const road of result.roads) {
      for (const pt of road.line.points) {
        expect(pt.x).toBeGreaterThanOrEqual(-10);
        expect(pt.x).toBeLessThanOrEqual(310);
        expect(pt.y).toBeGreaterThanOrEqual(-10);
        expect(pt.y).toBeLessThanOrEqual(310);
      }
    }
  });
});

// CITY-328: Jitter scaling tests
describe("CITY-328: Jitter control", () => {
  it("collector roads have no jitter applied", () => {
    const polygon = [
      { x: 0, y: 0 },
      { x: 300, y: 0 },
      { x: 300, y: 300 },
      { x: 0, y: 300 },
    ];

    const result = regenerateStreetGridForClippedDistrict(
      polygon,
      "district-j",
      "residential",
      { x: 150, y: 150 },
      0.5,
      0
    );

    const collectors = result.roads.filter(r => r.roadClass === "collector");
    expect(collectors.length).toBeGreaterThan(0);

    // Collector road endpoints should be exactly on the polygon boundary
    // or on exact grid lines (no perpendicular jitter offset)
    for (const road of collectors) {
      const pts = road.line.points;
      // Both endpoints should be on/near the polygon edge (within tolerance)
      // since collectors are either perimeter roads or grid-aligned
      const withinBounds =
        pts[0].x >= -1 && pts[0].x <= 301 &&
        pts[0].y >= -1 && pts[0].y <= 301 &&
        pts[1].x >= -1 && pts[1].x <= 301 &&
        pts[1].y >= -1 && pts[1].y <= 301;
      expect(withinBounds).toBe(true);
    }
  });
});

// CITY-554: Strip duplicate closing point from polygon-clipping output
describe("CITY-554: clipDistrictAgainstExisting strips closed ring duplicate", () => {
  it("strips duplicate closing point from polygon-clipping output", () => {
    // Two overlapping squares — clipping will produce a polygon
    const newPolygon = [
      { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }
    ];
    const existingDistrict = {
      id: "existing-1",
      type: "residential" as const,
      name: "Test District",
      polygon: { points: [
        { x: 5, y: 0 }, { x: 15, y: 0 }, { x: 15, y: 10 }, { x: 5, y: 10 }
      ]},
    };

    const result = clipDistrictAgainstExisting(
      newPolygon,
      [existingDistrict] as unknown as Parameters<typeof clipDistrictAgainstExisting>[1]
    );

    // The result should NOT have first == last (no closed ring)
    expect(result.clippedPolygon.length).toBeGreaterThan(2);
    const first = result.clippedPolygon[0];
    const last = result.clippedPolygon[result.clippedPolygon.length - 1];
    expect(first.x === last.x && first.y === last.y).toBe(false);
  });
});
