/**
 * Tests for RailStationLayer.
 */

import { describe, it, expect, beforeEach } from "vitest";
import {
  RailStationLayer,
  type RailStationData,
  type TrackSegmentData,
  type RailStationPreviewData,
} from "./RailStationLayer";

describe("RailStationLayer", () => {
  let layer: RailStationLayer;

  beforeEach(() => {
    layer = new RailStationLayer();
  });

  describe("constructor", () => {
    it("creates a container with correct label", () => {
      const container = layer.getContainer();
      expect(container.label).toBe("rail-stations");
    });

    it("creates child containers for tracks, stations, and preview", () => {
      const container = layer.getContainer();
      expect(container.children).toHaveLength(3);
      expect(container.children[0].label).toBe("rail-tracks");
      expect(container.children[1].label).toBe("rail-station-markers");
      expect(container.children[2].label).toBe("rail-station-preview");
    });
  });

  describe("setStations", () => {
    it("adds station graphics for each station", () => {
      const stations: RailStationData[] = [
        {
          id: "station-1",
          name: "Central Station",
          position: { x: 100, y: 100 },
          isTerminus: false,
        },
        {
          id: "station-2",
          name: "North Station",
          position: { x: 200, y: 50 },
          isTerminus: true,
        },
      ];

      layer.setStations(stations);

      // Check that the stations container has children
      const stationsContainer = layer.getContainer().children[1];
      expect(stationsContainer.children.length).toBe(2);
    });

    it("removes station graphics when station is removed", () => {
      const stations: RailStationData[] = [
        {
          id: "station-1",
          name: "Central Station",
          position: { x: 100, y: 100 },
          isTerminus: false,
        },
        {
          id: "station-2",
          name: "North Station",
          position: { x: 200, y: 50 },
          isTerminus: false,
        },
      ];

      layer.setStations(stations);
      let stationsContainer = layer.getContainer().children[1];
      expect(stationsContainer.children.length).toBe(2);

      // Remove one station
      layer.setStations([stations[0]]);
      stationsContainer = layer.getContainer().children[1];
      expect(stationsContainer.children.length).toBe(1);
    });

    it("updates existing station when data changes", () => {
      const station: RailStationData = {
        id: "station-1",
        name: "Central Station",
        position: { x: 100, y: 100 },
        isTerminus: false,
      };

      layer.setStations([station]);

      // Update the station name
      const updatedStation: RailStationData = {
        ...station,
        name: "Updated Station",
        position: { x: 150, y: 150 },
      };

      layer.setStations([updatedStation]);

      const stationsContainer = layer.getContainer().children[1];
      expect(stationsContainer.children.length).toBe(1);
    });
  });

  describe("setTracks", () => {
    it("adds track graphics for each segment", () => {
      const tracks: TrackSegmentData[] = [
        {
          id: "track-1",
          fromStation: { x: 100, y: 100 },
          toStation: { x: 200, y: 100 },
          lineColor: "#B22222",
          isUnderground: false,
        },
        {
          id: "track-2",
          fromStation: { x: 200, y: 100 },
          toStation: { x: 300, y: 150 },
          lineColor: "#B22222",
          isUnderground: false,
        },
      ];

      layer.setTracks(tracks);

      const tracksContainer = layer.getContainer().children[0];
      expect(tracksContainer.children.length).toBe(2);
    });

    it("removes track graphics when segment is removed", () => {
      const tracks: TrackSegmentData[] = [
        {
          id: "track-1",
          fromStation: { x: 100, y: 100 },
          toStation: { x: 200, y: 100 },
          lineColor: "#B22222",
          isUnderground: false,
        },
        {
          id: "track-2",
          fromStation: { x: 200, y: 100 },
          toStation: { x: 300, y: 150 },
          lineColor: "#B22222",
          isUnderground: false,
        },
      ];

      layer.setTracks(tracks);
      layer.setTracks([tracks[0]]);

      const tracksContainer = layer.getContainer().children[0];
      expect(tracksContainer.children.length).toBe(1);
    });

    it("supports intermediate geometry points", () => {
      const tracks: TrackSegmentData[] = [
        {
          id: "track-1",
          fromStation: { x: 100, y: 100 },
          toStation: { x: 300, y: 100 },
          lineColor: "#B22222",
          geometry: [
            { x: 150, y: 120 },
            { x: 200, y: 130 },
            { x: 250, y: 120 },
          ],
          isUnderground: false,
        },
      ];

      layer.setTracks(tracks);

      const tracksContainer = layer.getContainer().children[0];
      expect(tracksContainer.children.length).toBe(1);
    });
  });

  describe("setPreview", () => {
    it("shows preview when position is valid", () => {
      const preview: RailStationPreviewData = {
        position: { x: 100, y: 100 },
        isValid: true,
      };

      layer.setPreview(preview);

      const previewContainer = layer.getContainer().children[2];
      expect(previewContainer.children.length).toBeGreaterThan(0);
    });

    it("shows invalid indicator when position is invalid", () => {
      const preview: RailStationPreviewData = {
        position: { x: 100, y: 100 },
        isValid: false,
      };

      layer.setPreview(preview);

      const previewContainer = layer.getContainer().children[2];
      expect(previewContainer.children.length).toBeGreaterThan(0);
      // The invalid preview should have a text indicator
    });

    it("clears preview when set to null", () => {
      const preview: RailStationPreviewData = {
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
  });

  describe("setVisible", () => {
    it("hides the container when set to false", () => {
      layer.setVisible(false);
      expect(layer.getContainer().visible).toBe(false);
    });

    it("shows the container when set to true", () => {
      layer.setVisible(false);
      layer.setVisible(true);
      expect(layer.getContainer().visible).toBe(true);
    });
  });

  describe("destroy", () => {
    it("destroys the container and clears data", () => {
      // Add some data first
      layer.setStations([
        {
          id: "station-1",
          name: "Test Station",
          position: { x: 100, y: 100 },
          isTerminus: false,
        },
      ]);
      layer.setTracks([
        {
          id: "track-1",
          fromStation: { x: 100, y: 100 },
          toStation: { x: 200, y: 100 },
          lineColor: "#B22222",
          isUnderground: false,
        },
      ]);

      // Destroy should not throw
      expect(() => layer.destroy()).not.toThrow();
    });
  });
});
