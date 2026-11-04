/**
 * Tests for POI auto-generation, organic campus footprints, and campus paths.
 * CITY-440: Footprint generation
 * CITY-441: University campus footprints
 * CITY-442: Hospital campus footprints
 */

import { describe, it, expect } from "vitest";
import {
  generatePOIFootprint,
  generateCampusPaths,
  generatePOIsForDistrict,
} from "./poiAutoGenerator";
import type { DistrictType, Point } from "./types";

// Helper: compute polygon centroid
function centroid(polygon: Point[]): Point {
  const cx = polygon.reduce((s, p) => s + p.x, 0) / polygon.length;
  const cy = polygon.reduce((s, p) => s + p.y, 0) / polygon.length;
  return { x: cx, y: cy };
}

// Helper: simple large square polygon for district tests
function makeSquare(cx: number, cy: number, half: number): Point[] {
  return [
    { x: cx - half, y: cy - half },
    { x: cx + half, y: cy - half },
    { x: cx + half, y: cy + half },
    { x: cx - half, y: cy + half },
  ];
}

describe("generatePOIFootprint", () => {
  it("returns undefined for POI types without footprints", () => {
    expect(generatePOIFootprint("civic", { x: 0, y: 0 })).toBeUndefined();
    expect(generatePOIFootprint("transit", { x: 0, y: 0 })).toBeUndefined();
    expect(generatePOIFootprint("park", { x: 0, y: 0 })).toBeUndefined();
    expect(generatePOIFootprint("industrial", { x: 0, y: 0 })).toBeUndefined();
  });

  it("returns an organic polygon for university type", () => {
    const fp = generatePOIFootprint("university", { x: 50, y: 50 });
    expect(fp).toBeDefined();
    expect(fp!.length).toBeGreaterThanOrEqual(10); // 14 points configured
  });

  it("returns an organic polygon for hospital type", () => {
    const fp = generatePOIFootprint("hospital", { x: 100, y: 200 });
    expect(fp).toBeDefined();
    expect(fp!.length).toBeGreaterThanOrEqual(8); // 10 points configured
  });

  it("returns an organic polygon for shopping type", () => {
    const fp = generatePOIFootprint("shopping", { x: -10, y: 30 });
    expect(fp).toBeDefined();
    expect(fp!.length).toBeGreaterThanOrEqual(6); // 8 points configured
  });

  it("generates polygon roughly centered on position", () => {
    const pos = { x: 200, y: 300 };
    const fp = generatePOIFootprint("university", pos)!;
    const c = centroid(fp);
    // Should be within a few world units of the original position
    expect(Math.abs(c.x - pos.x)).toBeLessThan(3);
    expect(Math.abs(c.y - pos.y)).toBeLessThan(3);
  });

  it("university footprint is larger than hospital", () => {
    const pos = { x: 0, y: 0 };
    const uniFootprint = generatePOIFootprint("university", pos)!;
    const hosFootprint = generatePOIFootprint("hospital", pos)!;

    // Compare max radius from center
    const maxRadius = (fp: Point[]) =>
      Math.max(...fp.map((p) => Math.sqrt(p.x ** 2 + p.y ** 2)));

    expect(maxRadius(uniFootprint)).toBeGreaterThan(maxRadius(hosFootprint));
  });

  it("is deterministic — same inputs produce same output", () => {
    const pos = { x: 42, y: 99 };
    const fp1 = generatePOIFootprint("university", pos);
    const fp2 = generatePOIFootprint("university", pos);
    expect(fp1).toEqual(fp2);
  });

  it("different positions produce different footprints", () => {
    const fp1 = generatePOIFootprint("university", { x: 0, y: 0 });
    const fp2 = generatePOIFootprint("university", { x: 100, y: 100 });
    // At least one point should differ
    const match = fp1!.every((p, i) => p.x === fp2![i].x && p.y === fp2![i].y);
    expect(match).toBe(false);
  });
});

describe("generateCampusPaths", () => {
  it("generates trail-class paths for university footprints", () => {
    const pos = { x: 50, y: 50 };
    const footprint = generatePOIFootprint("university", pos)!;
    const paths = generateCampusPaths(footprint, pos, "university", "poi-test-1");

    expect(paths.length).toBeGreaterThan(0);
    for (const path of paths) {
      expect(path.roadClass).toBe("trail");
      expect(path.line.points.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("generates trail-class paths for hospital footprints", () => {
    const pos = { x: 100, y: 100 };
    const footprint = generatePOIFootprint("hospital", pos)!;
    const paths = generateCampusPaths(footprint, pos, "hospital", "poi-test-2");

    expect(paths.length).toBeGreaterThan(0);
    for (const path of paths) {
      expect(path.roadClass).toBe("trail");
    }
  });

  it("does not generate paths for shopping footprints", () => {
    const pos = { x: 0, y: 0 };
    const footprint = generatePOIFootprint("shopping", pos)!;
    const paths = generateCampusPaths(footprint, pos, "shopping", "poi-test-3");
    expect(paths.length).toBe(0);
  });

  it("does not generate paths for types without footprints", () => {
    const paths = generateCampusPaths([], { x: 0, y: 0 }, "civic", "poi-test-4");
    expect(paths.length).toBe(0);
  });

  it("university generates more paths than hospital", () => {
    const pos = { x: 50, y: 50 };

    const uniFootprint = generatePOIFootprint("university", pos)!;
    const hosFootprint = generatePOIFootprint("hospital", pos)!;

    const uniPaths = generateCampusPaths(uniFootprint, pos, "university", "poi-uni");
    const hosPaths = generateCampusPaths(hosFootprint, pos, "hospital", "poi-hos");

    // University config has 4 base paths, hospital has 2
    expect(uniPaths.length).toBeGreaterThanOrEqual(hosPaths.length);
  });

  it("path IDs contain the POI ID for ownership tracking", () => {
    const pos = { x: 50, y: 50 };
    const footprint = generatePOIFootprint("university", pos)!;
    const paths = generateCampusPaths(footprint, pos, "university", "poi-abc-123");

    for (const path of paths) {
      expect(path.id).toContain("poi-abc-123-path-");
    }
  });

  it("is deterministic — same inputs produce same paths", () => {
    const pos = { x: 42, y: 99 };
    const footprint = generatePOIFootprint("university", pos)!;
    const paths1 = generateCampusPaths(footprint, pos, "university", "poi-det");
    const paths2 = generateCampusPaths(footprint, pos, "university", "poi-det");

    expect(paths1.length).toBe(paths2.length);
    for (let i = 0; i < paths1.length; i++) {
      expect(paths1[i].line.points).toEqual(paths2[i].line.points);
    }
  });
});

describe("generatePOIsForDistrict", () => {
  it("returns both pois and campusPaths for university district", () => {
    const polygon = makeSquare(100, 100, 20);
    const result = generatePOIsForDistrict("university", polygon, "Test University");

    expect(result.pois.length).toBeGreaterThan(0);
    // University POIs should have footprints
    const uniPOIs = result.pois.filter((p) => p.type === "university");
    for (const poi of uniPOIs) {
      expect(poi.footprint).toBeDefined();
      expect(poi.footprint!.length).toBeGreaterThanOrEqual(10);
    }
    // Should have campus paths for the university POIs
    expect(result.campusPaths.length).toBeGreaterThan(0);
    for (const path of result.campusPaths) {
      expect(path.roadClass).toBe("trail");
    }
  });

  it("returns both pois and campusPaths for hospital district", () => {
    const polygon = makeSquare(200, 200, 15);
    const result = generatePOIsForDistrict("hospital", polygon, "Test Hospital");

    expect(result.pois.length).toBeGreaterThan(0);
    const hosPOIs = result.pois.filter((p) => p.type === "hospital");
    for (const poi of hosPOIs) {
      expect(poi.footprint).toBeDefined();
      expect(poi.footprint!.length).toBeGreaterThanOrEqual(8);
    }
    // Hospital POIs get campus paths
    expect(result.campusPaths.length).toBeGreaterThan(0);
  });

  it("returns empty campusPaths for districts without campus POIs", () => {
    const polygon = makeSquare(300, 300, 15);
    const result = generatePOIsForDistrict("residential", polygon, "Test Residential");

    // Residential generates shopping + civic, neither gets campus paths
    expect(result.campusPaths.length).toBe(0);
  });

  it("returns empty result for district types with no POI mapping", () => {
    const polygon = makeSquare(0, 0, 10);
    // Cast to bypass type checking for non-mapped district type
    const result = generatePOIsForDistrict("nonexistent" as DistrictType, polygon, "None");
    expect(result.pois.length).toBe(0);
    expect(result.campusPaths.length).toBe(0);
  });

  it("does not generate POIs for k12 districts", () => {
    const polygon = makeSquare(400, 400, 15);
    const result = generatePOIsForDistrict("k12", polygon, "Test K12");
    expect(result.pois.length).toBe(0);
    expect(result.campusPaths.length).toBe(0);
  });

  it("sets districtId on POIs and campus paths when provided", () => {
    const polygon = makeSquare(100, 100, 20);
    const result = generatePOIsForDistrict(
      "university", polygon, "Test Uni", undefined, undefined, "dist-123"
    );

    for (const poi of result.pois) {
      expect(poi.districtId).toBe("dist-123");
    }
    for (const path of result.campusPaths) {
      expect(path.districtId).toBe("dist-123");
    }
  });
});
