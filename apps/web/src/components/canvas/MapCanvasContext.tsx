/**
 * Context for sharing MapCanvas export capabilities.
 *
 * This allows components like ExportView to access the canvas export
 * functionality without needing direct parent-child relationships.
 */

import { createContext, useContext, useState, useCallback, useEffect, useMemo, useRef, ReactNode } from "react";
import type { ExportOptions, ExportResult } from "./useCanvasExport";

interface MapCanvasContextValue {
  /** Whether the canvas is ready for export */
  isReady: boolean;
  /** Register the canvas export functions */
  registerCanvas: (handle: CanvasExportHandle | null) => void;
  /** Export the canvas as PNG and trigger download */
  exportAsPng: (options: ExportOptions) => Promise<void>;
  /** Capture the canvas as PNG (no download) */
  captureAsPng: (options: ExportOptions) => Promise<ExportResult>;
}

interface CanvasExportHandle {
  exportAsPng: (options: ExportOptions) => Promise<void>;
  captureAsPng: (options: ExportOptions) => Promise<ExportResult>;
  isReady: boolean;
}

const MapCanvasContext = createContext<MapCanvasContextValue | null>(null);

interface MapCanvasProviderProps {
  children: ReactNode;
}

export function MapCanvasProvider({ children }: MapCanvasProviderProps) {
  const [canvasHandle, setCanvasHandle] = useState<CanvasExportHandle | null>(null);

  const registerCanvas = useCallback((handle: CanvasExportHandle | null) => {
    setCanvasHandle(handle);
  }, []);

  const exportAsPng = useCallback(
    async (options: ExportOptions) => {
      if (!canvasHandle?.isReady) {
        throw new Error("Canvas not ready for export");
      }
      return canvasHandle.exportAsPng(options);
    },
    [canvasHandle]
  );

  const captureAsPng = useCallback(
    async (options: ExportOptions) => {
      if (!canvasHandle?.isReady) {
        throw new Error("Canvas not ready for export");
      }
      return canvasHandle.captureAsPng(options);
    },
    [canvasHandle]
  );

  const isReady = canvasHandle?.isReady ?? false;
  const value = useMemo<MapCanvasContextValue>(
    () => ({ isReady, registerCanvas, exportAsPng, captureAsPng }),
    [isReady, registerCanvas, exportAsPng, captureAsPng]
  );

  return (
    <MapCanvasContext.Provider value={value}>
      {children}
    </MapCanvasContext.Provider>
  );
}

/**
 * Hook to access canvas export functionality.
 * Throws if not within a MapCanvasProvider.
 */
export function useMapCanvasExport() {
  const context = useContext(MapCanvasContext);
  if (!context) {
    throw new Error("useMapCanvasExport must be used within a MapCanvasProvider");
  }
  return context;
}

/**
 * Hook to optionally access canvas export functionality.
 * Returns null if not within a MapCanvasProvider (safe to use anywhere).
 */
export function useMapCanvasExportOptional() {
  return useContext(MapCanvasContext);
}

/**
 * Register a canvas's export handle with the nearest MapCanvasProvider (no-op
 * outside one). It registers when `isReady` turns true and unregisters when it
 * turns false or the canvas unmounts.
 *
 * `handle` may be a new object on every render. Only the first one after
 * `isReady` turns true is registered, so its methods must read live state
 * from refs.
 *
 * CITY-698: the effect depends on the stable `registerCanvas` callback, never
 * on the context value. Registering stores the handle in provider state, which
 * re-renders the canvas, and depending on the value turned that into an
 * endless effect -> setState -> render loop. The loop grew the JS heap
 * ~15 MB/s until Chrome killed the tab ("Aw, Snap!", error code 5).
 */
export function useRegisterCanvasExport(handle: CanvasExportHandle, isReady: boolean) {
  const registerCanvas = useContext(MapCanvasContext)?.registerCanvas;
  const handleRef = useRef(handle);
  handleRef.current = handle;

  useEffect(() => {
    if (!registerCanvas) return;
    registerCanvas(isReady ? handleRef.current : null);
    return () => {
      registerCanvas(null);
    };
  }, [registerCanvas, isReady]);
}
