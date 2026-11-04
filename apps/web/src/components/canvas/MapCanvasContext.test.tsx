import { render, screen, renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  MapCanvasProvider,
  useMapCanvasExport,
  useMapCanvasExportOptional,
  useRegisterCanvasExport,
} from "./MapCanvasContext";

describe("MapCanvasContext", () => {
  describe("useMapCanvasExport", () => {
    it("throws error when used outside provider", () => {
      // Suppress console.error for expected error
      const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

      expect(() => {
        renderHook(() => useMapCanvasExport());
      }).toThrow("useMapCanvasExport must be used within a MapCanvasProvider");

      consoleSpy.mockRestore();
    });

    it("returns context value when used inside provider", () => {
      const { result } = renderHook(() => useMapCanvasExport(), {
        wrapper: MapCanvasProvider,
      });

      expect(result.current.isReady).toBe(false);
      expect(typeof result.current.registerCanvas).toBe("function");
      expect(typeof result.current.exportAsPng).toBe("function");
      expect(typeof result.current.captureAsPng).toBe("function");
    });
  });

  describe("useMapCanvasExportOptional", () => {
    it("returns null when used outside provider", () => {
      const { result } = renderHook(() => useMapCanvasExportOptional());

      expect(result.current).toBeNull();
    });

    it("returns context value when used inside provider", () => {
      const { result } = renderHook(() => useMapCanvasExportOptional(), {
        wrapper: MapCanvasProvider,
      });

      expect(result.current).not.toBeNull();
      expect(result.current?.isReady).toBe(false);
    });
  });

  describe("MapCanvasProvider", () => {
    it("renders children", () => {
      render(
        <MapCanvasProvider>
          <div data-testid="child">Test Child</div>
        </MapCanvasProvider>
      );

      expect(screen.getByTestId("child")).toBeInTheDocument();
    });

    it("updates isReady when canvas is registered", () => {
      const { result } = renderHook(() => useMapCanvasExport(), {
        wrapper: MapCanvasProvider,
      });

      expect(result.current.isReady).toBe(false);

      const mockHandle = {
        exportAsPng: vi.fn(),
        captureAsPng: vi.fn(),
        isReady: true,
      };

      act(() => {
        result.current.registerCanvas(mockHandle);
      });

      expect(result.current.isReady).toBe(true);
    });

    it("updates isReady to false when canvas is unregistered", () => {
      const { result } = renderHook(() => useMapCanvasExport(), {
        wrapper: MapCanvasProvider,
      });

      const mockHandle = {
        exportAsPng: vi.fn(),
        captureAsPng: vi.fn(),
        isReady: true,
      };

      act(() => {
        result.current.registerCanvas(mockHandle);
      });

      expect(result.current.isReady).toBe(true);

      act(() => {
        result.current.registerCanvas(null);
      });

      expect(result.current.isReady).toBe(false);
    });

    it("exportAsPng throws when canvas not ready", async () => {
      const { result } = renderHook(() => useMapCanvasExport(), {
        wrapper: MapCanvasProvider,
      });

      await expect(
        result.current.exportAsPng({ resolution: "1x" })
      ).rejects.toThrow("Canvas not ready for export");
    });

    it("captureAsPng throws when canvas not ready", async () => {
      const { result } = renderHook(() => useMapCanvasExport(), {
        wrapper: MapCanvasProvider,
      });

      await expect(
        result.current.captureAsPng({ resolution: "1x" })
      ).rejects.toThrow("Canvas not ready for export");
    });

    it("exportAsPng calls registered handle", async () => {
      const { result } = renderHook(() => useMapCanvasExport(), {
        wrapper: MapCanvasProvider,
      });

      const mockExport = vi.fn().mockResolvedValue(undefined);
      const mockHandle = {
        exportAsPng: mockExport,
        captureAsPng: vi.fn(),
        isReady: true,
      };

      act(() => {
        result.current.registerCanvas(mockHandle);
      });

      await result.current.exportAsPng({ resolution: "2x" });

      expect(mockExport).toHaveBeenCalledWith({ resolution: "2x" });
    });

    it("captureAsPng calls registered handle", async () => {
      const { result } = renderHook(() => useMapCanvasExport(), {
        wrapper: MapCanvasProvider,
      });

      const mockCapture = vi.fn().mockResolvedValue({
        blob: new Blob(),
        dataUrl: "data:image/png;base64,test",
        width: 1920,
        height: 1080,
      });
      const mockHandle = {
        exportAsPng: vi.fn(),
        captureAsPng: mockCapture,
        isReady: true,
      };

      act(() => {
        result.current.registerCanvas(mockHandle);
      });

      const res = await result.current.captureAsPng({ resolution: "4x" });

      expect(mockCapture).toHaveBeenCalledWith({ resolution: "4x" });
      expect(res.width).toBe(1920);
      expect(res.height).toBe(1080);
    });
  });

  // CITY-698: registering with a context-valued effect dependency re-rendered
  // the canvas forever once it was ready, which grew the heap until Chrome
  // killed the tab.
  describe("useRegisterCanvasExport", () => {
    let renders = 0;
    beforeEach(() => {
      renders = 0;
    });

    // Like MapCanvas: a brand-new handle object on every render.
    function Canvas({ isReady }: { isReady: boolean }) {
      // Fail fast instead of looping until the test worker runs out of heap.
      if (++renders > 50) throw new Error("render loop: Canvas rendered more than 50 times");
      useRegisterCanvasExport({ exportAsPng: vi.fn(), captureAsPng: vi.fn(), isReady }, isReady);
      return null;
    }

    function ReadyProbe() {
      const { isReady } = useMapCanvasExport();
      return <span data-testid="ready">{String(isReady)}</span>;
    }

    function Tree({ isReady, mounted = true }: { isReady: boolean; mounted?: boolean }) {
      return (
        <MapCanvasProvider>
          {mounted && <Canvas isReady={isReady} />}
          <ReadyProbe />
        </MapCanvasProvider>
      );
    }

    it("registers once when ready without a render loop", () => {
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      const { rerender } = render(<Tree isReady={false} />);
      expect(screen.getByTestId("ready")).toHaveTextContent("false");

      renders = 0;
      rerender(<Tree isReady />);

      expect(screen.getByTestId("ready")).toHaveTextContent("true");
      // The prop change plus one provider update; the old effect never settled.
      expect(renders).toBeLessThanOrEqual(3);
      expect(errorSpy).not.toHaveBeenCalledWith(
        expect.stringContaining("Maximum update depth"),
        expect.anything()
      );
      errorSpy.mockRestore();
    });

    it("unregisters when the canvas stops being ready or unmounts", () => {
      const { rerender } = render(<Tree isReady />);
      expect(screen.getByTestId("ready")).toHaveTextContent("true");

      rerender(<Tree isReady={false} />);
      expect(screen.getByTestId("ready")).toHaveTextContent("false");

      rerender(<Tree isReady />);
      expect(screen.getByTestId("ready")).toHaveTextContent("true");

      rerender(<Tree isReady mounted={false} />);
      expect(screen.getByTestId("ready")).toHaveTextContent("false");
    });

    it("is a no-op outside a provider", () => {
      expect(() => render(<Canvas isReady />)).not.toThrow();
    });
  });
});
