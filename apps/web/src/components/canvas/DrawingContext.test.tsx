/**
 * Tests for DrawingContext and freehand drawing functionality.
 */

import { render, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DrawingProvider, useDrawing } from "./DrawingContext";
import type { Point } from "./layers";

// Test component to access context
function TestConsumer({
  onContext,
}: {
  onContext: (ctx: ReturnType<typeof useDrawing>) => void;
}) {
  const ctx = useDrawing();
  onContext(ctx);
  return null;
}

describe("DrawingContext", () => {
  describe("initial state", () => {
    it("has correct initial values", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      expect(context).not.toBeNull();
      expect(context!.state.mode).toBeNull();
      expect(context!.state.inputMode).toBe("click");
      expect(context!.state.vertices).toEqual([]);
      expect(context!.state.isDrawing).toBe(false);
      expect(context!.state.previewPoint).toBeNull();
      expect(context!.state.isFreehandActive).toBe(false);
    });
  });

  describe("startDrawing", () => {
    it("sets mode and isDrawing to true", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
      });

      expect(context!.state.mode).toBe("neighborhood");
      expect(context!.state.isDrawing).toBe(true);
      expect(context!.state.vertices).toEqual([]);
    });

    it("preserves inputMode when starting", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      // Set to freehand mode
      act(() => {
        context!.setInputMode("freehand");
      });

      // Start drawing
      act(() => {
        context!.startDrawing("cityLimits");
      });

      expect(context!.state.inputMode).toBe("freehand");
    });
  });

  describe("setInputMode", () => {
    it("toggles between click and freehand modes", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      expect(context!.state.inputMode).toBe("click");

      act(() => {
        context!.setInputMode("freehand");
      });

      expect(context!.state.inputMode).toBe("freehand");

      act(() => {
        context!.setInputMode("click");
      });

      expect(context!.state.inputMode).toBe("click");
    });
  });

  describe("freehand drawing", () => {
    it("startFreehand sets isFreehandActive and initial vertex", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      // Must start drawing first
      act(() => {
        context!.startDrawing("neighborhood");
      });

      act(() => {
        context!.startFreehand({ x: 10, y: 20 });
      });

      expect(context!.state.isFreehandActive).toBe(true);
      expect(context!.state.vertices).toEqual([{ x: 10, y: 20 }]);
    });

    it("addFreehandPoint adds points when active", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
        context!.startFreehand({ x: 0, y: 0 });
      });

      // Add points with sufficient distance
      act(() => {
        context!.addFreehandPoint({ x: 10, y: 0 });
        context!.addFreehandPoint({ x: 20, y: 0 });
        context!.addFreehandPoint({ x: 30, y: 0 });
      });

      expect(context!.state.vertices.length).toBe(4);
    });

    it("addFreehandPoint filters points too close together", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
        context!.startFreehand({ x: 0, y: 0 });
      });

      // Add points too close together (default minDistance is 5)
      act(() => {
        context!.addFreehandPoint({ x: 1, y: 0 });
        context!.addFreehandPoint({ x: 2, y: 0 });
        context!.addFreehandPoint({ x: 3, y: 0 });
      });

      // Only the initial point should remain
      expect(context!.state.vertices.length).toBe(1);
    });

    it("endFreehand completes and simplifies the path", () => {
      const onComplete = vi.fn();
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider onPolygonComplete={onComplete}>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
        context!.startFreehand({ x: 0, y: 0 });
      });

      // Add enough points to form a valid polygon
      act(() => {
        context!.addFreehandPoint({ x: 50, y: 0 });
        context!.addFreehandPoint({ x: 100, y: 0 });
        context!.addFreehandPoint({ x: 100, y: 50 });
        context!.addFreehandPoint({ x: 50, y: 50 });
        context!.addFreehandPoint({ x: 0, y: 50 });
      });

      act(() => {
        context!.endFreehand();
      });

      // Third arg is the road class (CITY-418).
      expect(onComplete).toHaveBeenCalledWith(
        expect.any(Array),
        "neighborhood",
        "arterial"
      );
      expect(context!.state.isDrawing).toBe(false);
      expect(context!.state.isFreehandActive).toBe(false);
    });

    it("endFreehand cancels if not enough points", () => {
      const onComplete = vi.fn();
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider onPolygonComplete={onComplete}>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
        context!.startFreehand({ x: 0, y: 0 });
      });

      // Only add one more point (total of 2, need 3 minimum)
      act(() => {
        context!.addFreehandPoint({ x: 50, y: 0 });
      });

      act(() => {
        context!.endFreehand();
      });

      expect(onComplete).not.toHaveBeenCalled();
      expect(context!.state.isDrawing).toBe(false);
    });

    it("does not add points when freehand is not active", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
        // Don't call startFreehand
        context!.addFreehandPoint({ x: 50, y: 0 });
      });

      expect(context!.state.vertices.length).toBe(0);
    });
  });

  describe("click mode drawing", () => {
    it("addVertex adds vertices in click mode", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
      });

      act(() => {
        context!.addVertex({ x: 0, y: 0 });
        context!.addVertex({ x: 100, y: 0 });
        context!.addVertex({ x: 50, y: 100 });
      });

      expect(context!.state.vertices).toHaveLength(3);
    });

    it("completeDrawing returns polygon when valid", () => {
      const onComplete = vi.fn();
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider onPolygonComplete={onComplete}>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("cityLimits");
        context!.addVertex({ x: 0, y: 0 });
        context!.addVertex({ x: 100, y: 0 });
        context!.addVertex({ x: 50, y: 100 });
      });

      let result: Point[] | null = null;
      act(() => {
        result = context!.completeDrawing();
      });

      expect(result).toHaveLength(3);
      expect(onComplete).toHaveBeenCalledWith(
        [
          { x: 0, y: 0 },
          { x: 100, y: 0 },
          { x: 50, y: 100 },
        ],
        "cityLimits",
        // Road class (CITY-418) and split target (CITY-565) are passed too.
        "arterial",
        null
      );
    });

    it("cancelDrawing resets state", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
        context!.addVertex({ x: 0, y: 0 });
        context!.addVertex({ x: 100, y: 0 });
      });

      act(() => {
        context!.cancelDrawing();
      });

      expect(context!.state.isDrawing).toBe(false);
      expect(context!.state.mode).toBeNull();
      expect(context!.state.vertices).toEqual([]);
    });

    it("undoLastVertex removes the last vertex", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
        context!.addVertex({ x: 0, y: 0 });
        context!.addVertex({ x: 100, y: 0 });
        context!.addVertex({ x: 50, y: 100 });
      });

      act(() => {
        context!.undoLastVertex();
      });

      expect(context!.state.vertices).toHaveLength(2);
      expect(context!.state.vertices).toEqual([
        { x: 0, y: 0 },
        { x: 100, y: 0 },
      ]);
    });

    it("canComplete returns true when 3+ vertices", () => {
      let context: ReturnType<typeof useDrawing> | null = null;

      render(
        <DrawingProvider>
          <TestConsumer onContext={(ctx) => (context = ctx)} />
        </DrawingProvider>
      );

      act(() => {
        context!.startDrawing("neighborhood");
      });

      expect(context!.canComplete()).toBe(false);

      act(() => {
        context!.addVertex({ x: 0, y: 0 });
        context!.addVertex({ x: 100, y: 0 });
      });

      expect(context!.canComplete()).toBe(false);

      act(() => {
        context!.addVertex({ x: 50, y: 100 });
      });

      expect(context!.canComplete()).toBe(true);
    });
  });
});
