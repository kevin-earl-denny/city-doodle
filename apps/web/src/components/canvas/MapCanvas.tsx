import {
  useEffect,
  useRef,
  useState,
  useCallback,
  forwardRef,
  useImperativeHandle,
  useMemo,
} from "react";
import { Application, Container } from "pixi.js";
import { Viewport } from "pixi-viewport";
import {
  TerrainLayer,
  FeaturesLayer,
  LabelLayer,
  SeedsLayer,
  DrawingLayer,
  RailStationLayer,
  SubwayStationLayer,
  RoadEndpointLayer,
  DistrictEditLayer,
  TransitLineDrawingLayer,
  WalkabilityOverlayLayer,
  DEFAULT_LAYER_VISIBILITY,
  type LayerVisibility,
} from "./layers";
import { useDrawingOptional } from "./DrawingContext";
import { useEndpointDragOptional } from "./EndpointDragContext";
import { SnapEngine } from "./snap";
import { useTransitLineDrawingOptional } from "./TransitLineDrawingContext";
import { LayerControls } from "./LayerControls";
import {
  exportCanvasAsPng,
  captureCanvasAsPng,
  type ExportOptions,
  type ExportResult,
} from "./useCanvasExport";
import { useRegisterCanvasExport } from "./MapCanvasContext";
import { useFeaturesStateOptional, useFeaturesDispatchOptional } from "./FeaturesContext";
import { useTerrainOptional } from "./TerrainContext";
import { useTransitOptional } from "./TransitContext";
import { StationContextMenu } from "../build-view/StationContextMenu";
import { StationDeleteWarningModal } from "../build-view/StationDeleteWarningModal";
import { RoadContextMenu } from "../build-view/RoadContextMenu";
import type { RoadContextMenuState } from "./hooks/useCanvasEventHandlers";
import type { RoadClass } from "./layers/types";
import { useZoomOptional } from "../shell/ZoomContext";
import { usePlacementOptional, usePlacedSeedsOptional } from "../palette";
import { useSelectionContextOptional } from "../build-view/SelectionContext";
import type { SelectedFeature } from "../build-view/SelectionContext";
import { useEditLockOptional } from "../shell/EditLockContext";
import { useViewModeOptional } from "../shell/ViewModeContext";
import type { GeographicSetting } from "../../api/types";
import { useWorldTiles, useRegenerateTerrain, useTerrainJobProgress } from "../../api/hooks";
import { useCanvasInit, type CanvasLayerRefs } from "./hooks/useCanvasInit";
import { useViewportSync } from "./hooks/useViewportSync";
import { useLayerSync } from "./hooks/useLayerSync";
import { useCanvasEventHandlers } from "./hooks/useCanvasEventHandlers";
import {
  TerrainLoadingOverlay,
  TerrainErrorOverlay,
  deriveTerrainOverlayStatus,
} from "./TerrainOverlay";

interface MapCanvasProps {
  className?: string;
  seed?: number;
  /** Geographic setting for terrain generation */
  geographicSetting?: GeographicSetting;
  /** World ID for fetching real terrain from the tiles API (CITY-439) */
  worldId?: string;
  /** Controlled zoom level from parent - synced with viewport */
  zoom?: number;
  /** Callback when zoom changes (from wheel/pinch) */
  onZoomChange?: (zoom: number) => void;
  /** Whether to show mock features (set false for new empty worlds) */
  showMockFeatures?: boolean;
  /** Callback when a feature is clicked for selection */
  onFeatureSelect?: (feature: SelectedFeature) => void;
}

/**
 * Imperative handle exposed by MapCanvas for export functionality.
 */
export interface MapCanvasHandle {
  /** Exports the canvas as PNG and triggers download */
  exportAsPng: (options: ExportOptions) => Promise<void>;
  /** Captures the canvas as PNG and returns the result (no download) */
  captureAsPng: (options: ExportOptions) => Promise<ExportResult>;
  /** Whether the canvas is ready for export */
  isReady: boolean;
}

export const MapCanvas = forwardRef<MapCanvasHandle, MapCanvasProps>(
  function MapCanvas({ className, seed = 12345, geographicSetting, worldId, zoom: zoomProp, onZoomChange: onZoomChangeProp, showMockFeatures = true, onFeatureSelect: onFeatureSelectProp }, ref) {
  // --- Refs ---
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const viewportRef = useRef<Viewport | null>(null);
  const terrainLayerRef = useRef<TerrainLayer | null>(null);
  const featuresLayerRef = useRef<FeaturesLayer | null>(null);
  const labelLayerRef = useRef<LabelLayer | null>(null);
  const seedsLayerRef = useRef<SeedsLayer | null>(null);
  const drawingLayerRef = useRef<DrawingLayer | null>(null);
  const railStationLayerRef = useRef<RailStationLayer | null>(null);
  const subwayStationLayerRef = useRef<SubwayStationLayer | null>(null);
  const roadEndpointLayerRef = useRef<RoadEndpointLayer | null>(null);
  const districtEditLayerRef = useRef<DistrictEditLayer | null>(null);
  const walkabilityOverlayLayerRef = useRef<WalkabilityOverlayLayer | null>(null);
  const transitLineDrawingLayerRef = useRef<TransitLineDrawingLayer | null>(null);
  const gridContainerRef = useRef<Container | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>(
    DEFAULT_LAYER_VISIBILITY
  );

  // CITY-376: Hover tooltip state for stations
  const [hoveredStationTooltip, setHoveredStationTooltip] = useState<{
    name: string;
    stationType: "rail" | "subway";
    lines: { name: string; color: string }[];
    screenX: number;
    screenY: number;
  } | null>(null);

  // CITY-405: Hover tooltip state for POIs
  const [hoveredPoiTooltip, setHoveredPoiTooltip] = useState<{
    name: string;
    poiType: string;
    screenX: number;
    screenY: number;
  } | null>(null);

  // CITY-528: Right-click context menu state for stations
  const [stationContextMenu, setStationContextMenu] = useState<{
    x: number;
    y: number;
    stationId: string;
    stationName: string;
    stationType: "rail" | "subway";
  } | null>(null);

  // CITY-567: Right-click context menu state for roads
  const [roadContextMenu, setRoadContextMenu] = useState<RoadContextMenuState | null>(null);

  // CITY-528: Warning modal state for unsafe station deletion
  const [deleteWarning, setDeleteWarning] = useState<{
    stationName: string;
    orphanedStations: string[];
    affectedLines: string[];
  } | null>(null);

  // --- Contexts ---
  const zoomContext = useZoomOptional();
  const zoom = zoomContext?.zoom ?? zoomProp;
  const onZoomChange = zoomContext?.setZoom ?? onZoomChangeProp;
  const placementContext = usePlacementOptional();
  const placedSeedsContext = usePlacedSeedsOptional();
  const selectionContext = useSelectionContextOptional();
  const onFeatureSelect = onFeatureSelectProp ?? selectionContext?.selectFeature;
  const featuresState = useFeaturesStateOptional();
  const featuresDispatch = useFeaturesDispatchOptional();
  const terrainContext = useTerrainOptional();
  const transitContext = useTransitOptional();
  const transitLineDrawingContext = useTransitLineDrawingOptional();
  const editLockContext = useEditLockOptional();
  const isEditingAllowed = editLockContext?.isEditing ?? true;
  const viewModeContext = useViewModeOptional();
  const viewMode = viewModeContext?.viewMode ?? "build";

  // CITY-439: Fetch tiles from API when worldId is provided
  const { data: tiles } = useWorldTiles(worldId || "", {
    enabled: !!worldId,
  });

  // CITY-595: Derive terrain overlay status from tile data
  const terrainOverlay = useMemo(() => deriveTerrainOverlayStatus(tiles), [tiles]);

  // CITY-626: Poll the terrain generation job for progress data
  const { progress: terrainProgress } = useTerrainJobProgress(
    tiles,
    terrainOverlay.status === "loading",
  );

  // CITY-595: Regenerate terrain mutation for retry on failure
  const regenerateTerrain = useRegenerateTerrain();
  const handleRetryTerrain = useCallback(() => {
    if (terrainOverlay.failedTileId) {
      regenerateTerrain.mutate(terrainOverlay.failedTileId);
    }
  }, [terrainOverlay.failedTileId, regenerateTerrain]);

  // Ref to setTerrainData for use in init effect (avoids stale closure)
  const setTerrainDataRef = useRef(terrainContext?.setTerrainData);
  useEffect(() => {
    setTerrainDataRef.current = terrainContext?.setTerrainData;
  }, [terrainContext?.setTerrainData]);

  // Get drawing context for polygon drawing mode
  const drawingContext = useDrawingOptional();

  // Get endpoint drag context for road endpoint dragging (CITY-147)
  const endpointDragContext = useEndpointDragOptional();

  // CITY-292: Warn before navigating away while actively drawing
  const isAnyDrawingActive =
    drawingContext?.state.isDrawing || transitLineDrawingContext?.state.isDrawing;
  useEffect(() => {
    if (!isAnyDrawingActive) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isAnyDrawingActive]);

  // --- Snap engine ---
  const snapEngine = useMemo(() => {
    const engine = new SnapEngine({
      threshold: 20,
      snapToVertex: true,
      snapToNearest: true,
      snapToMidpoint: false,
      snapToIntersection: false,
      geometryTypes: ["district"],
    });
    return engine;
  }, []);

  // --- Event state ref (updated every render, avoids re-registering handlers) ---
  const eventStateRef = useRef({
    placementContext,
    drawingContext,
    endpointDragContext,
    transitLineDrawingContext,
    transitContext,
    featuresContext: featuresState && featuresDispatch ? { features: featuresState.features, updateRoad: featuresDispatch.updateRoad, updateDistrict: featuresDispatch.updateDistrict } : null,
    onFeatureSelect,
    onToggleMultiSelect: selectionContext?.toggleMultiSelect,
    isEditingAllowed,
    viewMode,
    setHoveredStationTooltip,
    setHoveredPoiTooltip,
    snapEngine,
  });

  eventStateRef.current = {
    placementContext,
    drawingContext,
    endpointDragContext,
    transitLineDrawingContext,
    transitContext,
    featuresContext: featuresState && featuresDispatch ? { features: featuresState.features, updateRoad: featuresDispatch.updateRoad, updateDistrict: featuresDispatch.updateDistrict } : null,
    onFeatureSelect,
    onToggleMultiSelect: selectionContext?.toggleMultiSelect,
    isEditingAllowed,
    viewMode,
    setHoveredStationTooltip,
    setHoveredPoiTooltip,
    snapEngine,
  };

  // --- Export handle ---
  const exportHandle = {
    exportAsPng: async (options: ExportOptions) => {
      if (!appRef.current || !viewportRef.current) {
        throw new Error("Canvas not ready for export");
      }
      return exportCanvasAsPng(appRef.current, viewportRef.current, options);
    },
    captureAsPng: async (options: ExportOptions) => {
      if (!appRef.current || !viewportRef.current) {
        throw new Error("Canvas not ready for export");
      }
      return captureCanvasAsPng(appRef.current, viewportRef.current, options);
    },
    isReady,
  };

  useImperativeHandle(ref, () => exportHandle, [isReady]);

  // Register with the export context, if any (CITY-698: see useRegisterCanvasExport)
  useRegisterCanvasExport(exportHandle, isReady);

  // --- Visibility change callback ---
  const handleVisibilityChange = useCallback(
    (visibility: LayerVisibility) => {
      setLayerVisibility(visibility);

      if (terrainLayerRef.current) {
        terrainLayerRef.current.setVisibility(visibility);
      }
      if (featuresLayerRef.current) {
        featuresLayerRef.current.setVisibility(visibility);
      }
      if (labelLayerRef.current) {
        labelLayerRef.current.setVisibility(visibility);
      }
      if (gridContainerRef.current) {
        gridContainerRef.current.visible = visibility.grid;
      }
      if (subwayStationLayerRef.current) {
        subwayStationLayerRef.current.setTunnelsVisible(visibility.subwayTunnels);
      }
      if (railStationLayerRef.current) {
        railStationLayerRef.current.setLabelsVisible(visibility.labels);
      }
      if (subwayStationLayerRef.current) {
        subwayStationLayerRef.current.setLabelsVisible(visibility.labels);
      }
    },
    []
  );

  // --- Extracted hooks (CITY-231) ---

  const layerRefs: CanvasLayerRefs = {
    appRef,
    viewportRef,
    terrainLayerRef,
    featuresLayerRef,
    labelLayerRef,
    seedsLayerRef,
    drawingLayerRef,
    railStationLayerRef,
    subwayStationLayerRef,
    roadEndpointLayerRef,
    districtEditLayerRef,
    walkabilityOverlayLayerRef,
    transitLineDrawingLayerRef,
    gridContainerRef,
  };

  useCanvasInit({
    containerRef,
    layerRefs,
    seed,
    geographicSetting,
    showMockFeatures,
    layerVisibility,
    tiles,
    setTerrainDataRef,
    onReady: () => setIsReady(true),
  });

  useViewportSync({
    isReady,
    viewportRef,
    featuresLayerRef,
    zoom,
    onZoomChange,
  });

  useLayerSync({
    isReady,
    terrainLayerRef,
    featuresLayerRef,
    labelLayerRef,
    seedsLayerRef,
    drawingLayerRef,
    railStationLayerRef,
    subwayStationLayerRef,
    roadEndpointLayerRef,
    districtEditLayerRef,
    walkabilityOverlayLayerRef,
    transitLineDrawingLayerRef,
    gridContainerRef,
    setTerrainDataRef,
    layerVisibility,
    setLayerVisibility,
    viewMode,
    featuresContext: featuresState,
    transitContext,
    drawingContext,
    endpointDragContext,
    placementContext,
    placedSeedsContext,
    selectionContext,
    transitLineDrawingContext,
    snapEngine,
    showMockFeatures,
    tiles,
  });

  // --- Event handlers (CITY-231) ---
  useCanvasEventHandlers({
    isReady,
    containerRef,
    viewportRef,
    eventStateRef,
    roadEndpointLayerRef,
    districtEditLayerRef,
    railStationLayerRef,
    subwayStationLayerRef,
    featuresLayerRef,
    drawingLayerRef,
    seedsLayerRef,
    setStationContextMenu,
    setRoadContextMenu,
  });

  // CITY-528: Handle station deletion from context menu with orphan protection
  const handleContextMenuDelete = useCallback(() => {
    if (!stationContextMenu || !transitContext) return;

    const { stationId, stationName, stationType } = stationContextMenu;

    // Check deletion safety
    const safety = transitContext.checkStationDeletionSafety(stationId);

    if (!safety.safe) {
      // Show warning modal
      setDeleteWarning({
        stationName,
        orphanedStations: safety.wouldOrphanStations,
        affectedLines: safety.affectedLines,
      });
      return;
    }

    // Safe to delete - proceed
    if (stationType === "rail") {
      transitContext.removeRailStation(stationId);
    } else {
      transitContext.removeSubwayStation(stationId);
    }
  }, [stationContextMenu, transitContext]);

  // CITY-567: Handle road context menu actions
  const handleRoadChangeClass = useCallback(
    (newClass: RoadClass) => {
      if (!roadContextMenu || !featuresDispatch) return;
      featuresDispatch.updateRoad(roadContextMenu.roadId, { roadClass: newClass });
    },
    [roadContextMenu, featuresDispatch]
  );

  const handleRoadRename = useCallback(
    (newName: string) => {
      if (!roadContextMenu || !featuresDispatch) return;
      featuresDispatch.updateRoad(roadContextMenu.roadId, { name: newName });
    },
    [roadContextMenu, featuresDispatch]
  );

  const handleRoadDelete = useCallback(() => {
    if (!roadContextMenu || !featuresDispatch) return;
    featuresDispatch.removeRoad(roadContextMenu.roadId);
    // Clear selection if this road was selected
    if (selectionContext?.selection?.type === "road" && selectionContext.selection.id === roadContextMenu.roadId) {
      selectionContext.clearSelection();
    }
  }, [roadContextMenu, featuresDispatch, selectionContext]);

  // --- Render ---
  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full overflow-hidden ${className || ""}`}
      style={transitContext?.isPlacingStation ? { cursor: "wait" } : undefined}
    >
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <span className="text-gray-500">Loading canvas...</span>
        </div>
      )}
      {isReady && (
        <LayerControls
          visibility={layerVisibility}
          onChange={handleVisibilityChange}
        />
      )}
      {/* CITY-595/626: Terrain loading overlay with progress bar */}
      {isReady && terrainOverlay.status === "loading" && (
        <TerrainLoadingOverlay visible progress={terrainProgress} />
      )}
      {/* CITY-595: Terrain error overlay with retry */}
      {isReady && terrainOverlay.status === "failed" && (
        <TerrainErrorOverlay
          visible
          errorMessage={terrainOverlay.errorMessage}
          onRetry={handleRetryTerrain}
          isRetrying={regenerateTerrain.isPending}
        />
      )}
      {/* CITY-376: Station hover tooltip */}
      {hoveredStationTooltip && (
        <div
          className="absolute pointer-events-none z-50"
          style={{
            left: hoveredStationTooltip.screenX + 12,
            top: hoveredStationTooltip.screenY - 8,
          }}
        >
          <div className="bg-gray-900 text-white text-xs rounded-md px-3 py-2 shadow-lg max-w-48">
            <div className="font-medium">{hoveredStationTooltip.name}</div>
            <div className="text-gray-400 text-[10px] mt-0.5">
              {hoveredStationTooltip.stationType === "subway" ? "Subway" : "Rail"} Station
            </div>
            {hoveredStationTooltip.lines.length > 0 && (
              <div className="mt-1 pt-1 border-t border-gray-700 space-y-0.5">
                {hoveredStationTooltip.lines.map((line) => (
                  <div key={line.name} className="flex items-center gap-1.5">
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: line.color }}
                    />
                    <span className="text-gray-300">{line.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      {/* CITY-405: POI hover tooltip */}
      {hoveredPoiTooltip && !hoveredStationTooltip && (
        <div
          className="absolute pointer-events-none z-50"
          style={{
            left: hoveredPoiTooltip.screenX + 12,
            top: hoveredPoiTooltip.screenY - 8,
          }}
        >
          <div className="bg-gray-900 text-white text-xs rounded-md px-3 py-2 shadow-lg max-w-48">
            <div className="font-medium">{hoveredPoiTooltip.name}</div>
            <div className="text-gray-400 text-[10px] mt-0.5 capitalize">
              {hoveredPoiTooltip.poiType}
            </div>
          </div>
        </div>
      )}
      {/* CITY-528: Station right-click context menu */}
      {stationContextMenu && (
        <StationContextMenu
          x={stationContextMenu.x}
          y={stationContextMenu.y}
          stationName={stationContextMenu.stationName}
          stationType={stationContextMenu.stationType}
          onDelete={handleContextMenuDelete}
          onClose={() => setStationContextMenu(null)}
        />
      )}
      {/* CITY-567: Road right-click context menu */}
      {roadContextMenu && (
        <RoadContextMenu
          x={roadContextMenu.x}
          y={roadContextMenu.y}
          roadName={roadContextMenu.roadName}
          roadClass={roadContextMenu.roadClass}
          onChangeClass={handleRoadChangeClass}
          onRename={handleRoadRename}
          onDelete={handleRoadDelete}
          onClose={() => setRoadContextMenu(null)}
        />
      )}
      {/* CITY-528: Station deletion warning modal */}
      {deleteWarning && (
        <StationDeleteWarningModal
          stationName={deleteWarning.stationName}
          orphanedStations={deleteWarning.orphanedStations}
          affectedLines={deleteWarning.affectedLines}
          onClose={() => setDeleteWarning(null)}
        />
      )}
    </div>
  );
  }
);

