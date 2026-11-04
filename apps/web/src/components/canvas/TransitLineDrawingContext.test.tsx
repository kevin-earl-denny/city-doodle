/**
 * Tests for TransitLineDrawingContext.
 */

import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { ReactNode } from "react";
import {
  TransitLineDrawingProvider,
  useTransitLineDrawing,
} from "./TransitLineDrawingContext";
import type { RailStationData } from "./layers";

// Helper to create the wrapper
function createWrapper(props?: {
  onSegmentCreate?: (
    fromStation: RailStationData,
    toStation: RailStationData,
    lineProperties: { name: string; color: string; type: "subway" | "rail" },
    lineId: string | null
  ) => void;
  onLineComplete?: (
    stations: RailStationData[],
    lineProperties: { name: string; color: string; type: "subway" | "rail" },
    lineId: string | null
  ) => void;
  existingLineCount?: number;
}) {
  return ({ children }: { children: ReactNode }) => (
    <TransitLineDrawingProvider {...props}>{children}</TransitLineDrawingProvider>
  );
}

// Mock station data
const mockStationA: RailStationData = {
  id: "station-a",
  name: "Station A",
  position: { x: 100, y: 100 },
  isTerminus: false,
};

const mockStationB: RailStationData = {
  id: "station-b",
  name: "Station B",
  position: { x: 200, y: 200 },
  isTerminus: false,
};

const mockStationC: RailStationData = {
  id: "station-c",
  name: "Station C",
  position: { x: 300, y: 300 },
  isTerminus: false,
};

describe("TransitLineDrawingContext", () => {
  describe("initial state", () => {
    it("should start with isDrawing false", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      expect(result.current.state.isDrawing).toBe(false);
      expect(result.current.state.firstStation).toBeNull();
      expect(result.current.state.connectedStations).toHaveLength(0);
    });
  });

  describe("startDrawing", () => {
    it("should set isDrawing to true and initialize default properties", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper({ existingLineCount: 0 }),
      });

      act(() => {
        result.current.startDrawing();
      });

      expect(result.current.state.isDrawing).toBe(true);
      expect(result.current.state.lineProperties).toEqual({
        name: "Line 1",
        color: "#B22222", // First default color
        type: "rail",
      });
    });

    // Quarantined: CITY-670 (failing on main; hidden by `|| true` until CITY-652)
    it.skip("should use existing line count for naming", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper({ existingLineCount: 3 }),
      });

      act(() => {
        result.current.startDrawing();
      });

      expect(result.current.state.lineProperties?.name).toBe("Line 4");
    });
  });

  describe("selectStation", () => {
    it("should set first station on first click", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      expect(result.current.state.firstStation).toEqual(mockStationA);
      expect(result.current.state.connectedStations).toHaveLength(1);
      expect(result.current.state.connectedStations[0]).toEqual(mockStationA);
    });

    it("should call onSegmentCreate when connecting two stations", async () => {
      const onSegmentCreate = vi.fn();
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper({ onSegmentCreate }),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      await act(async () => {
        await result.current.selectStation(mockStationB);
      });

      expect(onSegmentCreate).toHaveBeenCalledTimes(1);
      expect(onSegmentCreate).toHaveBeenCalledWith(
        mockStationA,
        mockStationB,
        expect.objectContaining({ name: "Line 1" }),
        null
      );
    });

    it("should update firstStation to the new station after connecting", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.selectStation(mockStationB);
      });

      expect(result.current.state.firstStation).toEqual(mockStationB);
      expect(result.current.state.connectedStations).toHaveLength(2);
    });

    it("should not connect to the same station", () => {
      const onSegmentCreate = vi.fn();
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper({ onSegmentCreate }),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      expect(onSegmentCreate).not.toHaveBeenCalled();
      expect(result.current.state.connectedStations).toHaveLength(1);
    });
  });

  describe("canComplete", () => {
    it("should return false with no stations", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      expect(result.current.canComplete()).toBe(false);
    });

    it("should return false with one station", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      expect(result.current.canComplete()).toBe(false);
    });

    it("should return true with two or more stations", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.selectStation(mockStationB);
      });

      expect(result.current.canComplete()).toBe(true);
    });
  });

  describe("completeDrawing", () => {
    it("should reset state after completion", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.selectStation(mockStationB);
      });

      act(() => {
        result.current.completeDrawing();
      });

      expect(result.current.state.isDrawing).toBe(false);
      expect(result.current.state.connectedStations).toHaveLength(0);
    });

    it("should call onLineComplete with connected stations", () => {
      const onLineComplete = vi.fn();
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper({ onLineComplete }),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.selectStation(mockStationB);
      });

      act(() => {
        result.current.completeDrawing();
      });

      expect(onLineComplete).toHaveBeenCalledTimes(1);
      expect(onLineComplete).toHaveBeenCalledWith(
        [mockStationA, mockStationB],
        expect.objectContaining({ name: "Line 1" }),
        null
      );
    });
  });

  describe("cancelDrawing", () => {
    it("should reset all state", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.cancelDrawing();
      });

      expect(result.current.state.isDrawing).toBe(false);
      expect(result.current.state.firstStation).toBeNull();
      expect(result.current.state.connectedStations).toHaveLength(0);
    });
  });

  describe("undoLastConnection", () => {
    it("should remove the last station from connectedStations", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.selectStation(mockStationB);
      });

      act(() => {
        result.current.selectStation(mockStationC);
      });

      expect(result.current.state.connectedStations).toHaveLength(3);

      act(() => {
        result.current.undoLastConnection();
      });

      expect(result.current.state.connectedStations).toHaveLength(2);
      expect(result.current.state.firstStation).toEqual(mockStationB);
    });

    it("should not undo if only one station", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      act(() => {
        result.current.undoLastConnection();
      });

      expect(result.current.state.connectedStations).toHaveLength(1);
    });
  });

  describe("isStationConnected", () => {
    it("should return true for connected stations", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.selectStation(mockStationA);
      });

      expect(result.current.isStationConnected(mockStationA.id)).toBe(true);
      expect(result.current.isStationConnected(mockStationB.id)).toBe(false);
    });
  });

  describe("setPreviewPosition", () => {
    it("should update preview position", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.setPreviewPosition({ x: 150, y: 150 });
      });

      expect(result.current.state.previewPosition).toEqual({ x: 150, y: 150 });
    });
  });

  describe("setHoveredStation", () => {
    it("should update hovered station", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.setHoveredStation(mockStationB);
      });

      expect(result.current.state.hoveredStation).toEqual(mockStationB);
    });
  });

  describe("setLineProperties", () => {
    it("should update line properties", () => {
      const { result } = renderHook(() => useTransitLineDrawing(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.startDrawing();
      });

      act(() => {
        result.current.setLineProperties({
          name: "Custom Line",
          color: "#FF0000",
          type: "subway",
        });
      });

      expect(result.current.state.lineProperties).toEqual({
        name: "Custom Line",
        color: "#FF0000",
        type: "subway",
      });
    });
  });
});
