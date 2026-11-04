import { ReactNode, useCallback, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { TransitLinesPanel, TransitLine } from "./TransitLinesPanel";
import { TransitLineInspector } from "./TransitLineInspector";
import type { SegmentDisplayData } from "./TransitLineInspector";
import { TransitStationInspector, StationInspectorData } from "./TransitStationInspector";
import { useTransitLinesData } from "./useTransitLinesData";
import { useTransitOptional } from "../canvas/TransitContext";
import { useTransitLineDrawingOptional } from "../canvas/TransitLineDrawingContext";
import type { TransitLineProperties } from "../canvas/TransitLineDrawingContext";
import { usePlacementOptional } from "../palette/PlacementContext";
import { SEED_TYPES } from "../palette/types";
import { useViewMode } from "../shell/ViewModeContext";
import { TransitLinePropertiesDialog } from "../build-view/TransitLinePropertiesDialog";
import { useSelectionContextOptional } from "../build-view/SelectionContext";
import type { RailStationData } from "../canvas/layers";
import { useDeleteTransitLineSegment, useDeleteTransitStation } from "../../api/hooks";

interface TransitViewProps {
  children: ReactNode;
  /** Optional lines to display (overrides fetched data if provided) */
  lines?: TransitLine[];
  onLineClick?: (line: TransitLine) => void;
}

/**
 * Transit view wrapper with a left sidebar for transit line management
 * connected to real transit network data from TransitContext.
 *
 * Layout: left sidebar (lines list + inspector) | map canvas
 */
export function TransitView({
  children,
  lines: propLines,
  onLineClick,
}: TransitViewProps) {
  const transitContext = useTransitOptional();
  const transitLineDrawingContext = useTransitLineDrawingOptional();
  const placementContext = usePlacementOptional();
  const { setViewMode } = useViewMode();
  const { worldId } = useParams<{ worldId: string }>();
  const deleteSegmentMutation = useDeleteTransitLineSegment();
  const deleteStationMutation = useDeleteTransitStation();

  const [selectedLine, setSelectedLine] = useState<TransitLine | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [showLinePropertiesDialog, setShowLinePropertiesDialog] = useState(false);
  const [terminusChoices, setTerminusChoices] = useState<{
    lineId: string;
    lineName: string;
    lineColor: string;
    lineType: "subway" | "rail";
    termini: RailStationData[];
  } | null>(null);

  const selectionContext = useSelectionContextOptional();
  const [isStationUpdating, setIsStationUpdating] = useState(false);

  const networkLines = useTransitLinesData(transitContext?.transitNetwork);
  const lines = propLines ?? networkLines;

  // CITY-375: Build station inspector data from selection context
  const selectedStation: StationInspectorData | null = useMemo(() => {
    const selection = selectionContext?.selection;
    if (!selection) return null;
    if (selection.type !== "rail_station" && selection.type !== "subway_station") return null;

    const stationLines = (transitContext?.getLinesForStation(selection.id) ?? [])
      .map(l => ({ id: l.id, name: l.name, color: l.color }));

    return {
      id: selection.id,
      name: selection.name,
      stationType: selection.type === "rail_station" ? "rail" : "subway",
      isTerminus: selection.isTerminus,
      lines: stationLines,
    };
  }, [selectionContext?.selection, transitContext?.getLinesForStation]);

  // Station placement via PlacementContext
  const subwaySeed = SEED_TYPES.find((s) => s.id === "subway") ?? null;
  const railSeed = SEED_TYPES.find((s) => s.id === "rail_station") ?? null;

  const handlePlaceSubwayStation = useCallback(() => {
    if (placementContext && subwaySeed) {
      // Cancel any active line drawing before starting placement
      if (transitLineDrawingContext?.state.isDrawing) {
        transitLineDrawingContext.cancelDrawing();
      }
      placementContext.selectSeed(subwaySeed);
    }
  }, [placementContext, subwaySeed, transitLineDrawingContext]);

  const handlePlaceRailStation = useCallback(() => {
    if (placementContext && railSeed) {
      // Cancel any active line drawing before starting placement
      if (transitLineDrawingContext?.state.isDrawing) {
        transitLineDrawingContext.cancelDrawing();
      }
      placementContext.selectSeed(railSeed);
    }
  }, [placementContext, railSeed, transitLineDrawingContext]);

  const placingStationType: "subway" | "rail" | null =
    placementContext?.isPlacing && placementContext.selectedSeed?.id === "subway"
      ? "subway"
      : placementContext?.isPlacing &&
          placementContext.selectedSeed?.id === "rail_station"
        ? "rail"
        : null;

  // Line drawing via TransitLineDrawingContext
  const handleDrawNewLine = useCallback(() => {
    if (transitLineDrawingContext?.state.isDrawing) {
      // Already drawing - complete the current line
      transitLineDrawingContext.completeDrawing();
      return;
    }
    setShowLinePropertiesDialog(true);
  }, [transitLineDrawingContext]);

  const handleLinePropertiesConfirm = useCallback(
    (properties: TransitLineProperties) => {
      setShowLinePropertiesDialog(false);
      if (transitLineDrawingContext) {
        // Cancel any active station placement
        placementContext?.cancelPlacing();
        // Pass properties directly so startDrawing() uses them instead of defaults
        transitLineDrawingContext.startDrawing(properties);
      }
    },
    [transitLineDrawingContext, placementContext]
  );

  const handleLinePropertiesCancel = useCallback(() => {
    setShowLinePropertiesDialog(false);
  }, []);

  const isDrawingLine = transitLineDrawingContext?.state.isDrawing ?? false;

  const handleLineClick = useCallback(
    (line: TransitLine) => {
      onLineClick?.(line);
      // Toggle selection: clicking same line deselects
      setSelectedLine((prev) => (prev?.id === line.id ? null : line));
      // Highlight line on map
      if (transitContext) {
        if (transitContext.highlightedLineId === line.id) {
          transitContext.setHighlightedLineId(null);
        } else {
          transitContext.setHighlightedLineId(line.id);
        }
      }
    },
    [onLineClick, transitContext]
  );

  const handleCloseInspector = useCallback(() => {
    setSelectedLine(null);
    transitContext?.setHighlightedLineId(null);
  }, [transitContext]);

  const handleUpdateLine = useCallback(
    async (lineId: string, updates: { name?: string; color?: string }) => {
      if (!transitContext?.updateLine) return;

      setIsUpdating(true);
      try {
        const success = await transitContext.updateLine(lineId, updates);
        if (success) {
          setSelectedLine((prev) =>
            prev && prev.id === lineId ? { ...prev, ...updates } : prev
          );
        }
      } finally {
        setIsUpdating(false);
      }
    },
    [transitContext]
  );

  // CITY-363: Extend an existing line from its terminus
  // CITY-368: Show terminus choice when a line has 2 termini
  const handleExtendLine = useCallback(
    (lineId: string) => {
      if (!transitContext || !transitLineDrawingContext) return;

      const network = transitContext.transitNetwork;
      if (!network) return;

      const line = network.lines.find((l) => l.id === lineId);
      if (!line || line.segments.length === 0) return;

      // Find terminus stations (stations that appear in only one segment endpoint)
      const stationOccurrences = new Map<string, number>();
      for (const seg of line.segments) {
        stationOccurrences.set(seg.from_station_id, (stationOccurrences.get(seg.from_station_id) || 0) + 1);
        stationOccurrences.set(seg.to_station_id, (stationOccurrences.get(seg.to_station_id) || 0) + 1);
      }

      // A terminus appears in exactly 1 segment endpoint
      const terminusIds = Array.from(stationOccurrences.entries())
        .filter(([, count]) => count === 1)
        .map(([id]) => id);

      if (terminusIds.length === 0) return;

      // Find the station data for rendering (filter by line type to prevent mixing)
      const stationPool = line.line_type === "subway"
        ? transitContext.subwayStations
        : transitContext.railStations;

      if (terminusIds.length >= 2) {
        // CITY-368: Two termini — show picker
        const terminiStations = terminusIds
          .map((id) => stationPool.find((s) => s.id === id))
          .filter((s): s is RailStationData => s != null);

        if (terminiStations.length >= 2) {
          setTerminusChoices({
            lineId,
            lineName: line.name,
            lineColor: line.color,
            lineType: line.line_type,
            termini: terminiStations,
          });
          return;
        }
      }

      // Single terminus — extend immediately (original behavior)
      const lastSegment = line.segments.reduce((a, b) =>
        a.order_in_line > b.order_in_line ? a : b
      );
      const lastTerminusId = terminusIds.includes(lastSegment.to_station_id)
        ? lastSegment.to_station_id
        : terminusIds[terminusIds.length - 1];

      const terminus = stationPool.find((s) => s.id === lastTerminusId);
      if (!terminus) return;

      placementContext?.cancelPlacing();
      transitLineDrawingContext.extendLine(lineId, terminus, {
        name: line.name,
        color: line.color,
        type: line.line_type,
      });
    },
    [transitContext, transitLineDrawingContext, placementContext]
  );

  // CITY-368: Handle terminus selection from the picker
  const handleTerminusChoice = useCallback(
    (station: RailStationData) => {
      if (!terminusChoices || !transitLineDrawingContext) return;

      placementContext?.cancelPlacing();
      transitLineDrawingContext.extendLine(terminusChoices.lineId, station, {
        name: terminusChoices.lineName,
        color: terminusChoices.lineColor,
        type: terminusChoices.lineType,
      });
      setTerminusChoices(null);
    },
    [terminusChoices, transitLineDrawingContext, placementContext]
  );

  // CITY-375: Station rename handler
  const handleStationRename = useCallback(
    async (stationId: string, newName: string): Promise<boolean> => {
      if (!transitContext?.renameStation) return false;
      setIsStationUpdating(true);
      try {
        const success = await transitContext.renameStation(stationId, newName);
        if (success && selectionContext?.selection) {
          // Update selection state to reflect new name
          selectionContext.selectFeature({ ...selectionContext.selection, name: newName });
        }
        return success;
      } finally {
        setIsStationUpdating(false);
      }
    },
    [transitContext, selectionContext]
  );

  // CITY-375: Station delete handler
  const handleStationDelete = useCallback(
    async (stationId: string) => {
      if (!transitContext) return;
      // Find the station type to call the correct delete method
      const isRail = transitContext.railStations.some((s) => s.id === stationId);
      if (isRail) {
        await transitContext.removeRailStation(stationId);
      } else {
        await transitContext.removeSubwayStation(stationId);
      }
      selectionContext?.clearSelection();
    },
    [transitContext, selectionContext]
  );

  const handleCloseStationInspector = useCallback(() => {
    selectionContext?.clearSelection();
  }, [selectionContext]);

  // CITY-367: Compute segment display data for the selected line
  const selectedLineSegments: SegmentDisplayData[] | undefined = useMemo(() => {
    if (!selectedLine || !transitContext?.transitNetwork) return undefined;
    const network = transitContext.transitNetwork;
    const line = network.lines.find((l) => l.id === selectedLine.id);
    if (!line || line.segments.length === 0) return undefined;

    return line.segments.map((seg) => {
      const fromStation = network.stations.find((s) => s.id === seg.from_station_id);
      const toStation = network.stations.find((s) => s.id === seg.to_station_id);
      return {
        id: seg.id,
        fromStationId: seg.from_station_id,
        toStationId: seg.to_station_id,
        fromStationName: fromStation?.name ?? "Unknown",
        toStationName: toStation?.name ?? "Unknown",
        orderInLine: seg.order_in_line,
      };
    });
  }, [selectedLine, transitContext?.transitNetwork]);

  // Compute station IDs that appear in OTHER lines' segments (won't be orphaned)
  const stationIdsUsedByOtherLines: Set<string> = useMemo(() => {
    if (!selectedLine || !transitContext?.transitNetwork) return new Set();
    const network = transitContext.transitNetwork;
    const ids = new Set<string>();
    for (const line of network.lines) {
      if (line.id === selectedLine.id) continue;
      for (const seg of line.segments) {
        ids.add(seg.from_station_id);
        ids.add(seg.to_station_id);
      }
    }
    return ids;
  }, [selectedLine, transitContext?.transitNetwork]);

  // Delete a station by ID
  const deleteStation = useCallback(
    (stationId: string) => {
      if (!worldId) return;
      deleteStationMutation.mutate({ stationId, worldId });
    },
    [deleteStationMutation, worldId]
  );

  // CITY-367: Delete a segment (with optional orphan cleanup)
  const handleDeleteSegment = useCallback(
    (segmentId: string, deleteOrphanedStations: boolean) => {
      if (!selectedLine || !selectedLineSegments) return;

      // If deleting orphans, find which stations will be orphaned
      const stationIdsToDelete: string[] = [];
      if (deleteOrphanedStations) {
        const seg = selectedLineSegments.find((s) => s.id === segmentId);
        if (seg) {
          for (const stationId of [seg.fromStationId, seg.toStationId]) {
            if (stationIdsUsedByOtherLines.has(stationId)) continue;
            const otherRefs = selectedLineSegments.filter(
              (s) =>
                s.id !== segmentId &&
                (s.fromStationId === stationId || s.toStationId === stationId)
            );
            if (otherRefs.length === 0) {
              stationIdsToDelete.push(stationId);
            }
          }
        }
      }

      // Delete the segment first
      deleteSegmentMutation.mutate(
        { segmentId, lineId: selectedLine.id, worldId },
        {
          onSuccess: () => {
            // Then delete orphaned stations
            for (const stationId of stationIdsToDelete) {
              deleteStation(stationId);
            }
          },
        }
      );
    },
    [selectedLine, selectedLineSegments, stationIdsUsedByOtherLines, deleteSegmentMutation, worldId, deleteStation]
  );

  // Delete the entire line (with optional orphan station cleanup)
  const handleDeleteLine = useCallback(
    async (lineId: string, deleteOrphanedStations: boolean) => {
      if (!transitContext?.deleteLine) return;

      // Collect station IDs to delete before the line is removed
      let stationIdsToDelete: string[] = [];
      if (deleteOrphanedStations && selectedLineSegments) {
        const stationMap = new Map<string, boolean>();
        for (const seg of selectedLineSegments) {
          stationMap.set(seg.fromStationId, true);
          stationMap.set(seg.toStationId, true);
        }
        stationIdsToDelete = Array.from(stationMap.keys()).filter(
          (id) => !stationIdsUsedByOtherLines.has(id)
        );
      }

      const success = await transitContext.deleteLine(lineId);
      if (success) {
        setSelectedLine(null);
        transitContext.setHighlightedLineId(null);
        // Delete orphaned stations after line deletion
        for (const stationId of stationIdsToDelete) {
          deleteStation(stationId);
        }
      }
    },
    [transitContext, selectedLineSegments, stationIdsUsedByOtherLines, deleteStation]
  );
  const handleBackgroundClick = useCallback(() => {
    transitContext?.setHighlightedLineId(null);
  }, [transitContext]);

  const handleSwitchToBuild = useCallback(() => {
    // CITY-423: Cancel active transit line drawing before leaving transit view
    if (transitLineDrawingContext?.state.isDrawing) {
      transitLineDrawingContext.cancelDrawing();
    }
    // CITY-424: Cancel active station placement before leaving transit view
    placementContext?.cancelPlacing();
    // CITY-426: Clear transit line highlighting so stations aren't dimmed in build view
    transitContext?.setHighlightedLineId(null);
    // CITY-427: Clear feature selection to avoid stale inspector state
    selectionContext?.clearSelection();
    setViewMode("build");
  }, [setViewMode, transitLineDrawingContext, placementContext, transitContext, selectionContext]);

  return (
    <div className="flex w-full h-full">
      {/* Left sidebar */}
      <div
        className="w-72 shrink-0 bg-white border-r border-gray-200 flex flex-col overflow-hidden z-10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Transit lines list */}
        <div className="flex-1 overflow-y-auto">
          <TransitLinesPanel
            lines={lines}
            onLineClick={handleLineClick}
            isLoading={transitContext?.isLoading ?? false}
            highlightedLineId={transitContext?.highlightedLineId ?? null}
            onSwitchToBuild={handleSwitchToBuild}
            onPlaceSubwayStation={handlePlaceSubwayStation}
            onPlaceRailStation={handlePlaceRailStation}
            onDrawNewLine={handleDrawNewLine}
            placingStationType={placingStationType}
            isDrawingLine={isDrawingLine}
          />
        </div>

        {/* Line inspector (below lines list when a line is selected) */}
        {selectedLine && (
          <div className="border-t border-gray-200 overflow-y-auto max-h-[50%]">
            <TransitLineInspector
              line={selectedLine}
              onUpdate={handleUpdateLine}
              onDelete={handleDeleteLine}
              onExtend={handleExtendLine}
              onClose={handleCloseInspector}
              isUpdating={isUpdating}
              isExtending={isDrawingLine}
              segments={selectedLineSegments}
              onDeleteSegment={handleDeleteSegment}
              stationIdsUsedByOtherLines={stationIdsUsedByOtherLines}
            />
          </div>
        )}

        {/* CITY-375: Station inspector (when a station is selected on the map) */}
        {selectedStation && !selectedLine && (
          <div className="border-t border-gray-200 overflow-y-auto max-h-[50%]">
            <TransitStationInspector
              station={selectedStation}
              onRename={handleStationRename}
              onDelete={handleStationDelete}
              onClose={handleCloseStationInspector}
              isUpdating={isStationUpdating}
            />
          </div>
        )}
      </div>

      {/* Map content */}
      <div className="flex-1 relative" onClick={handleBackgroundClick}>
        <div className="absolute inset-0 transit-view-overlay">
          {children}
        </div>

        {/* Placement mode indicator */}
        {placingStationType && (
          <div className="absolute top-4 left-4 z-10 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
            <span className="text-lg">
              {placingStationType === "subway" ? "🚇" : "🚂"}
            </span>
            <span className="text-sm font-medium">
              Click on a district to place{" "}
              {placingStationType === "subway" ? "subway" : "rail"} station
            </span>
            <button
              onClick={() => placementContext?.cancelPlacing()}
              className="ml-2 text-blue-200 hover:text-white text-xs"
            >
              Cancel (Esc)
            </button>
          </div>
        )}

        {/* Drawing mode indicator */}
        {isDrawingLine && transitLineDrawingContext && (
          <div className="absolute top-4 left-4 z-10 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
            <span className="text-sm font-medium">
              {transitLineDrawingContext.state.connectedStations.length === 0
                ? "Click a station or empty space to start"
                : "Click a station or empty space to extend"}
              {transitLineDrawingContext.state.connectedStations.length >= 2 && (
                <> — Press <kbd className="px-1 py-0.5 bg-blue-500 rounded text-xs font-mono">Enter</kbd> to finish</>
              )}
            </span>
            {transitLineDrawingContext.state.connectedStations.length >= 2 && (
              <button
                onClick={() => transitLineDrawingContext.undoLastConnection()}
                className="ml-1 text-blue-200 hover:text-white text-xs"
              >
                Undo (Ctrl+Z)
              </button>
            )}
            <button
              onClick={() => transitLineDrawingContext.cancelDrawing()}
              className="ml-1 text-blue-200 hover:text-white text-xs"
            >
              Cancel (Esc)
            </button>
          </div>
        )}
      </div>

      {/* Transit line properties dialog */}
      <TransitLinePropertiesDialog
        isOpen={showLinePropertiesDialog}
        initialProperties={
          transitLineDrawingContext?.state.lineProperties || undefined
        }
        existingLineNames={transitContext?.transitNetwork?.lines.map((l) => l.name) ?? []}
        onConfirm={handleLinePropertiesConfirm}
        onCancel={handleLinePropertiesCancel}
      />

      {/* CITY-368: Terminus choice picker */}
      {terminusChoices && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-lg shadow-xl p-4 max-w-xs w-full mx-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">Extend from which end?</h3>
            <p className="text-xs text-gray-500 mb-3">
              Choose a terminus station to extend from
            </p>
            <div className="space-y-2">
              {terminusChoices.termini.map((station) => (
                <button
                  key={station.id}
                  onClick={() => handleTerminusChoice(station)}
                  className="w-full flex items-center gap-2 p-2 text-sm text-left rounded-md border border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  <div
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: terminusChoices.lineColor }}
                  />
                  {station.name}
                </button>
              ))}
            </div>
            <button
              onClick={() => setTerminusChoices(null)}
              className="w-full mt-3 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
