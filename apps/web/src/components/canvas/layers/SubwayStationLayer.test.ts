/**
 * Tests for SubwayStationLayer
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { SubwayStationLayer, toSubwayStationData } from "./SubwayStationLayer";
import type { SubwayStationData, SubwayStationPreviewData } from "./SubwayStationLayer";
import type { TransitStation } from "../../../api/types";

describe("SubwayStationLayer", () => {
  let layer: SubwayStationLayer;

  beforeEach(() => {
    layer = new SubwayStationLayer();
  });

  afterEach(() => {
    layer.destroy();
  });

  describe("initialization", () => {
    it("should create container with correct label", () => {
      expect(layer.getContainer().label).toBe("subway-stations");
    });

    it("should be visible by default", () => {
      expect(layer.getContainer().visible).toBe(true);
    });
  });

  describe("setStations", () => {
    it("should add stations", () => {
      const stations: SubwayStationData[] = [
        { id: "1", name: "Central", position: { x: 100, y: 100 }, isTerminus: false },
        { id: "2", name: "North", position: { x: 200, y: 200 }, isTerminus: true },
      ];

      layer.setStations(stations);

      // Container should have 3 sub-containers: tunnels, stations, preview
      expect(layer.getContainer().children.length).toBe(3);
      // Stations container (index 1) should have both stations
      const stationsContainer = layer.getContainer().children[1];
      expect(stationsContainer.children.length).toBe(2);
    });

    it("should update existing stations", () => {
      const stations: SubwayStationData[] = [
        { id: "1", name: "Central", position: { x: 100, y: 100 }, isTerminus: false },
      ];

      layer.setStations(stations);

      // Update the station
      const updatedStations: SubwayStationData[] = [
        { id: "1", name: "Central Updated", position: { x: 150, y: 150 }, isTerminus: true },
      ];

      layer.setStations(updatedStations);

      // Should still have same number of containers (3: tunnels, stations, preview)
      expect(layer.getContainer().children.length).toBe(3);
    });

    it("should remove stations that are no longer present", () => {
      const stations: SubwayStationData[] = [
        { id: "1", name: "Central", position: { x: 100, y: 100 }, isTerminus: false },
        { id: "2", name: "North", position: { x: 200, y: 200 }, isTerminus: false },
      ];

      layer.setStations(stations);

      // Remove one station
      layer.setStations([stations[0]]);

      // Should still have 3 containers (tunnels, stations, preview)
      expect(layer.getContainer().children.length).toBe(3);
      // Stations container should have only 1 station now
      const stationsContainer = layer.getContainer().children[1];
      expect(stationsContainer.children.length).toBe(1);
    });

    it("should handle empty stations array", () => {
      layer.setStations([]);
      expect(layer.getContainer().children.length).toBe(3); // tunnels, stations, preview containers
    });
  });

  describe("setPreview", () => {
    it("should show preview when data is provided", () => {
      const preview: SubwayStationPreviewData = {
        position: { x: 100, y: 100 },
        isValid: true,
      };

      layer.setPreview(preview);

      // Preview container (index 2) should have children
      const previewContainer = layer.getContainer().children[2];
      expect(previewContainer.children.length).toBeGreaterThan(0);
    });

    it("should clear preview when null is provided", () => {
      const preview: SubwayStationPreviewData = {
        position: { x: 100, y: 100 },
        isValid: true,
      };

      layer.setPreview(preview);
      layer.setPreview(null);

      // CITY-506: Preview objects are now hidden instead of destroyed
      const previewContainer = layer.getContainer().children[2];
      for (const child of previewContainer.children) {
        expect(child.visible).toBe(false);
      }
    });

    it("should show warning message for invalid placement", () => {
      const preview: SubwayStationPreviewData = {
        position: { x: 100, y: 100 },
        isValid: false,
      };

      layer.setPreview(preview);

      // Preview container (index 2) should have warning text
      const previewContainer = layer.getContainer().children[2];
      // At least 3 children: graphics, icon text, warning label
      expect(previewContainer.children.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe("setVisible", () => {
    it("should hide the layer when set to false", () => {
      layer.setVisible(false);
      expect(layer.getContainer().visible).toBe(false);
    });

    it("should show the layer when set to true", () => {
      layer.setVisible(false);
      layer.setVisible(true);
      expect(layer.getContainer().visible).toBe(true);
    });
  });

  describe("clear", () => {
    it("should remove all stations", () => {
      const stations: SubwayStationData[] = [
        { id: "1", name: "Central", position: { x: 100, y: 100 }, isTerminus: false },
        { id: "2", name: "North", position: { x: 200, y: 200 }, isTerminus: false },
      ];

      layer.setStations(stations);
      layer.clear();

      // Stations container (index 1) should be empty
      const stationsContainer = layer.getContainer().children[1];
      expect(stationsContainer.children.length).toBe(0);
    });
  });

  describe("tunnels", () => {
    it("should be hidden by default", () => {
      // Tunnels container (index 0) should be hidden by default (underground)
      const tunnelsContainer = layer.getContainer().children[0];
      expect(tunnelsContainer.visible).toBe(false);
    });

    it("should show tunnels when setTunnelsVisible(true) is called", () => {
      layer.setTunnelsVisible(true);
      const tunnelsContainer = layer.getContainer().children[0];
      expect(tunnelsContainer.visible).toBe(true);
    });

    it("should hide tunnels when setTunnelsVisible(false) is called", () => {
      layer.setTunnelsVisible(true);
      layer.setTunnelsVisible(false);
      const tunnelsContainer = layer.getContainer().children[0];
      expect(tunnelsContainer.visible).toBe(false);
    });

    it("should report tunnel visibility correctly", () => {
      expect(layer.getTunnelsVisible()).toBe(false);
      layer.setTunnelsVisible(true);
      expect(layer.getTunnelsVisible()).toBe(true);
    });
  });
});

describe("toSubwayStationData", () => {
  it("should convert TransitStation to SubwayStationData", () => {
    const apiStation: TransitStation = {
      id: "test-id",
      world_id: "world-id",
      district_id: "district-id",
      station_type: "subway",
      name: "Test Station",
      position_x: 150.5,
      position_y: 250.75,
      is_terminus: true,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };

    const result = toSubwayStationData(apiStation);

    expect(result.id).toBe("test-id");
    expect(result.name).toBe("Test Station");
    expect(result.position.x).toBe(150.5);
    expect(result.position.y).toBe(250.75);
    expect(result.isTerminus).toBe(true);
  });

  it("should handle non-terminus station", () => {
    const apiStation: TransitStation = {
      id: "test-id",
      world_id: "world-id",
      district_id: "district-id",
      station_type: "subway",
      name: "Regular Station",
      position_x: 100,
      position_y: 200,
      is_terminus: false,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };

    const result = toSubwayStationData(apiStation);

    expect(result.isTerminus).toBe(false);
  });
});
