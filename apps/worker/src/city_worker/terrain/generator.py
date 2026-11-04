"""Main terrain generator combining all terrain features."""

import logging
import time
from typing import Any

import numpy as np

from city_worker.terrain.bays import BayConfig, extract_bays
from city_worker.terrain.clip import clip_features_to_tile
from city_worker.terrain.geographic_masks import apply_geographic_mask
from city_worker.terrain.noise import apply_erosion, generate_heightfield
from city_worker.terrain.types import (
    TerrainConfig,
    TerrainFeature,
    TerrainResult,
    TileTerrainData,
)
from city_worker.terrain.barrier_islands import (
    BarrierIslandConfig,
    extract_barrier_islands,
)
from city_worker.terrain.deltas import extract_deltas
from city_worker.terrain.water import (
    calculate_flow_accumulation,
    extract_beaches,
    extract_coastlines,
    extract_lakes,
    extract_rivers,
)

logger = logging.getLogger(__name__)

# Water level below which rivers and lakes are suppressed entirely.
# This prevents stray water features on dry presets like "inland".
WATER_LEVEL_SUPPRESS_THRESHOLD = 0.2


class TerrainGenerator:
    """Generates terrain for a 3x3 tile neighborhood."""

    def __init__(self, config: TerrainConfig) -> None:
        self.config = config

    def generate_3x3(self, center_tx: int, center_ty: int) -> TerrainResult:
        """Generate terrain for center tile and 8 neighbors.

        Args:
            center_tx, center_ty: Coordinates of the center tile

        Returns:
            TerrainResult containing all 9 tiles with seamless borders
        """
        logger.info("Generating 3x3 terrain centered at (%d, %d)", center_tx, center_ty)

        t_start = time.perf_counter()

        # Phase names used for aggregated timing summary
        phase_names = [
            "heightfield", "mask", "erosion", "flow", "coastlines",
            "bays", "barriers", "rivers", "deltas", "lakes", "beaches",
            "contours", "clip",
        ]
        phase_totals = {name: 0.0 for name in phase_names}

        # Generate all 9 tiles
        tiles: dict[tuple[int, int], TileTerrainData] = {}
        center_data: TileTerrainData | None = None

        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                tx = center_tx + dx
                ty = center_ty + dy

                tile_data, tile_timings = self._generate_tile(tx, ty)
                for name in phase_names:
                    phase_totals[name] += tile_timings.get(name, 0.0)

                if dx == 0 and dy == 0:
                    center_data = tile_data
                else:
                    tiles[(dx, dy)] = tile_data

        assert center_data is not None

        total_features = sum(len(t.features) for t in [center_data, *tiles.values()])
        total_s = time.perf_counter() - t_start

        # CITY-594: Log aggregated per-phase timing summary with geographic_setting
        timing_parts = " ".join(f"{name}={phase_totals[name]:.1f}s" for name in phase_names)
        logger.info(
            "[Terrain] Generated 3x3 in %.1fs (%s) setting=%s features=%d",
            total_s, timing_parts, self.config.geographic_setting, total_features,
        )

        return TerrainResult(center=center_data, neighbors=tiles)

    def _generate_tile(self, tx: int, ty: int) -> tuple[TileTerrainData, dict[str, float]]:
        """Generate terrain for a single tile.

        Returns:
            Tuple of (tile data, phase timings dict in seconds).
        """
        cfg = self.config

        t0 = time.perf_counter()

        # Generate base heightfield
        heightfield = generate_heightfield(
            seed=cfg.world_seed,
            tx=tx,
            ty=ty,
            tile_size=cfg.tile_size,
            resolution=cfg.resolution,
            octaves=cfg.height_octaves,
            persistence=cfg.height_persistence,
            lacunarity=cfg.height_lacunarity,
            scale=cfg.height_scale,
        )

        t_heightfield = time.perf_counter()

        # Apply geographic mask to shape terrain per world type (CITY-386)
        heightfield = apply_geographic_mask(
            heightfield=heightfield,
            geographic_setting=cfg.geographic_setting,
            tx=tx,
            ty=ty,
            tile_size=cfg.tile_size,
            resolution=cfg.resolution,
            seed=cfg.world_seed,
        )

        t_mask = time.perf_counter()

        # Apply erosion for more realistic features
        # Derive tile-specific seed from world seed and tile coordinates
        # Use abs() to ensure non-negative seed for numpy's RNG
        erosion_seed = abs(cfg.world_seed ^ (tx * 7919 + ty * 7927))
        heightfield = apply_erosion(heightfield, seed=erosion_seed, iterations=30)

        t_erosion = time.perf_counter()

        # Calculate flow accumulation for river and bay detection
        flow_accumulation = calculate_flow_accumulation(heightfield)

        t_flow = time.perf_counter()

        # Extract water features
        features: list[TerrainFeature] = []

        # Coastlines (land polygons) with fractal detail (CITY-322)
        coastline_seed = abs(cfg.world_seed ^ (tx * 6271 + ty * 6277))
        coastlines = extract_coastlines(
            heightfield=heightfield,
            water_level=cfg.water_level,
            tile_x=tx,
            tile_y=ty,
            tile_size=cfg.tile_size,
            smoothing_iterations=cfg.coastline_smoothing,
            fractal_seed=coastline_seed,
        )
        features.extend(coastlines)

        t_coastlines = time.perf_counter()

        # Bays (concave coastline formations)
        bays: list[TerrainFeature] = []
        if cfg.bay_enabled:
            bay_config = BayConfig(
                min_concavity_angle=cfg.bay_min_concavity_angle,
                min_area=cfg.bay_min_area,
                max_depth_ratio=cfg.bay_max_depth_ratio,
                cove_max_area=cfg.bay_cove_max_area,
                harbor_min_area=cfg.bay_harbor_min_area,
                river_mouth_factor=cfg.bay_river_mouth_factor,
            )
            bays = extract_bays(
                heightfield=heightfield,
                water_level=cfg.water_level,
                tile_x=tx,
                tile_y=ty,
                tile_size=cfg.tile_size,
                flow_accumulation=flow_accumulation,
                config=bay_config,
            )
            features.extend(bays)

        # Collect bay polygons for beach exclusion (CITY-548)
        bay_polygons: list = []
        if cfg.bay_enabled and bays:
            for f in bays:
                if f.type == "bay":
                    from shapely.geometry import shape as _shape
                    bay_polygons.append(_shape(f.geometry))

        t_bays = time.perf_counter()

        # Barrier islands (moved before beaches so lagoon polygons can
        # be used to exclude lagoon-side beaches — CITY-525)
        lagoon_polygons: list = []
        if cfg.barrier_islands_enabled:
            barrier_island_config = BarrierIslandConfig(
                island_offset_min=cfg.barrier_island_offset_min,
                island_offset_max=cfg.barrier_island_offset_max,
                island_width_min=cfg.barrier_island_width_min,
                island_width_max=cfg.barrier_island_width_max,
                island_length_min=cfg.barrier_island_length_min,
                inlet_spacing_min=cfg.barrier_inlet_spacing_min,
                inlet_spacing_max=cfg.barrier_inlet_spacing_max,
            )
            barrier_islands = extract_barrier_islands(
                heightfield=heightfield,
                water_level=cfg.water_level,
                tile_x=tx,
                tile_y=ty,
                tile_size=cfg.tile_size,
                seed=cfg.world_seed,
                config=barrier_island_config,
            )
            features.extend(barrier_islands)
            # Collect lagoon polygons for beach filtering
            for f in barrier_islands:
                if f.type == "lagoon":
                    from shapely.geometry import shape
                    lagoon_polygons.append(shape(f.geometry))

        t_barriers = time.perf_counter()

        # CITY-576: Collect coastline polygons for river endpoint snapping
        coastline_polys: list = []
        for f in coastlines:
            if f.type == "coastline":
                from shapely.geometry import shape as _shape_coast
                coastline_polys.append(_shape_coast(f.geometry))

        # Rivers (moved before beaches so river geometries can be used
        # to filter out river-adjacent beaches — CITY-546)
        # CITY-551: Skip river extraction when water_level is very low
        # (e.g. inland preset) to prevent stray water features.
        rivers: list[TerrainFeature] = []
        if cfg.water_level >= WATER_LEVEL_SUPPRESS_THRESHOLD:
            rivers = extract_rivers(
                heightfield=heightfield,
                water_level=cfg.water_level,
                tile_x=tx,
                tile_y=ty,
                tile_size=cfg.tile_size,
                flow_threshold=cfg.resolution * 0.8,  # Scale with resolution
                min_length=cfg.min_river_length,
                flow_accumulation=flow_accumulation,
                coastline_polys=coastline_polys if coastline_polys else None,
            )
        features.extend(rivers)

        # Collect river geometries for beach filtering (CITY-546)
        river_lines: list = []
        for f in rivers:
            from shapely.geometry import shape as _shape
            river_lines.append(_shape(f.geometry))

        t_rivers = time.perf_counter()

        # River deltas and estuaries (CITY-179)
        delta_seed = abs(cfg.world_seed ^ (tx * 8311 + ty * 8317))
        deltas = extract_deltas(
            rivers=rivers,
            heightfield=heightfield,
            water_level=cfg.water_level,
            flow_accumulation=flow_accumulation,
            tile_x=tx,
            tile_y=ty,
            tile_size=cfg.tile_size,
            seed=delta_seed,
            min_flow=cfg.resolution * 0.4,  # Lower threshold than rivers
        )
        features.extend(deltas)

        t_deltas = time.perf_counter()

        # Lakes (moved before beaches so lake polygons can be used
        # to cap lake beach coverage — CITY-547)
        # CITY-551: Skip lake extraction when water_level is very low
        # (e.g. inland preset) to prevent stray water features.
        lakes: list[TerrainFeature] = []
        if cfg.water_level >= WATER_LEVEL_SUPPRESS_THRESHOLD:
            lakes = extract_lakes(
                heightfield=heightfield,
                water_level=cfg.water_level,
                tile_x=tx,
                tile_y=ty,
                tile_size=cfg.tile_size,
                max_lakes=cfg.max_lakes,
            )
        features.extend(lakes)

        # Collect lake polygons for beach filtering (CITY-547)
        lake_polygons: list = []
        for f in lakes:
            from shapely.geometry import shape as _shape
            lake_polygons.append(_shape(f.geometry))

        t_lakes = time.perf_counter()

        # Beaches (transition zones between water and land)
        if cfg.beach_enabled:
            beach_seed = abs(cfg.world_seed ^ (tx * 5413 + ty * 5417))
            beaches = extract_beaches(
                heightfield=heightfield,
                water_level=cfg.water_level,
                beach_height_band=cfg.beach_height_band,
                tile_x=tx,
                tile_y=ty,
                tile_size=cfg.tile_size,
                min_length=cfg.beach_min_length,
                max_slope=cfg.beach_slope_max,
                width_multiplier=cfg.beach_width_multiplier,
                max_segment_cells=cfg.beach_max_segment_cells,
                gap_cells=cfg.beach_gap_cells,
                seed=beach_seed,
                lagoon_polygons=lagoon_polygons,
                bay_polygons=bay_polygons,
                river_lines=river_lines,
                lake_polygons=lake_polygons,
            )
            features.extend(beaches)

        t_beaches = time.perf_counter()

        # Generate contour lines
        contours = self._generate_contours(
            heightfield=heightfield,
            tx=tx,
            ty=ty,
            levels=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        )
        features.extend(contours)

        t_contours = time.perf_counter()

        # Clip all features to tile boundaries (CITY-530)
        features = clip_features_to_tile(features, tx, ty, cfg.tile_size)

        t_clip = time.perf_counter()

        # Per-phase timing in seconds (CITY-591, CITY-594)
        timings = {
            "heightfield": t_heightfield - t0,
            "mask": t_mask - t_heightfield,
            "erosion": t_erosion - t_mask,
            "flow": t_flow - t_erosion,
            "coastlines": t_coastlines - t_flow,
            "bays": t_bays - t_coastlines,
            "barriers": t_barriers - t_bays,
            "rivers": t_rivers - t_barriers,
            "deltas": t_deltas - t_rivers,
            "lakes": t_lakes - t_deltas,
            "beaches": t_beaches - t_lakes,
            "contours": t_contours - t_beaches,
            "clip": t_clip - t_contours,
        }
        total_s = t_clip - t0
        timing_parts = " ".join(f"{k}={v:.1f}s" for k, v in timings.items())
        logger.info(
            "[Terrain] Tile (%d, %d) in %.1fs (%s) features=%d",
            tx, ty, total_s, timing_parts, len(features),
        )

        tile_data = TileTerrainData(
            tx=tx,
            ty=ty,
            heightfield=heightfield.tolist(),
            features=features,
        )
        return tile_data, timings

    def _generate_contours(
        self,
        heightfield: np.ndarray,
        tx: int,
        ty: int,
        levels: list[float],
    ) -> list[TerrainFeature]:
        """Generate contour lines at specified height levels.

        CITY-625: Vectorized marching squares.  The case index for every
        cell is computed with numpy boolean operations in one pass, then
        only cells with interesting cases (not 0 or 15) are processed.
        Edge interpolation is also vectorized across all active cells at
        once, eliminating the inner Python double-loop entirely.
        """
        cfg = self.config
        h, w = heightfield.shape
        cell_size = cfg.tile_size / w
        features = []

        # CITY-514: Cap segments per level.
        max_segments_per_level = 100

        # Pre-compute corner value arrays (each shifted view of the grid)
        v00 = heightfield[:-1, :-1]  # top-left
        v10 = heightfield[1:, :-1]   # bottom-left
        v01 = heightfield[:-1, 1:]   # top-right
        v11 = heightfield[1:, 1:]    # bottom-right

        # World-coordinate origins for each cell
        js = np.arange(w - 1, dtype=np.float64)
        is_ = np.arange(h - 1, dtype=np.float64)
        x0_all = tx * cfg.tile_size + js[np.newaxis, :] * cell_size  # (1, w-1)
        y0_all = ty * cfg.tile_size + is_[:, np.newaxis] * cell_size  # (h-1, 1)

        # Marching-squares segment lookup.  Each case maps to a list of
        # segment templates.  A segment template is a pair of edge
        # identifiers: 0=top, 1=bottom, 2=left, 3=right.
        _seg_table: dict[int, list[tuple[int, int]]] = {
            1: [(2, 0)],          # left-top
            2: [(0, 3)],          # top-right
            3: [(2, 3)],          # left-right
            4: [(3, 1)],          # right-bottom
            5: [(2, 0), (3, 1)],  # left-top, right-bottom
            6: [(0, 1)],          # top-bottom
            7: [(2, 1)],          # left-bottom
            8: [(1, 2)],          # bottom-left
            9: [(0, 1)],          # top-bottom
            10: [(0, 3), (1, 2)], # top-right, bottom-left
            11: [(3, 1)],         # right-bottom
            12: [(0, 3)],         # top-right
            13: [(0, 3)],         # top-right
            14: [(2, 0)],         # left-top
        }

        def _safe_lerp(va: np.ndarray, vb: np.ndarray, lev: float) -> np.ndarray:
            """Vectorized linear interpolation for edge crossing."""
            diff = vb - va
            safe = np.where(np.abs(diff) < 1e-10, 1.0, diff)
            return np.where(np.abs(diff) < 1e-10, 0.5, (lev - va) / safe)

        for level in levels:
            # Compute case index for all cells at once
            case = np.zeros((h - 1, w - 1), dtype=np.int32)
            case += (v00 >= level).astype(np.int32)
            case += (v10 >= level).astype(np.int32) * 2
            case += (v01 >= level).astype(np.int32) * 4
            case += (v11 >= level).astype(np.int32) * 8

            # Mask of cells with contour crossings (case not 0 or 15)
            active = (case != 0) & (case != 15)
            active_indices = np.argwhere(active)  # (N, 2) with [i, j]

            if active_indices.size == 0:
                continue

            # Cap to max_segments_per_level cells (each cell produces
            # at most 2 segments, but capping input cells is simpler and
            # preserves the existing behaviour of taking the first N).
            if len(active_indices) > max_segments_per_level:
                active_indices = active_indices[:max_segments_per_level]

            ai = active_indices[:, 0]
            aj = active_indices[:, 1]

            # Extract corner values for active cells
            av00 = v00[ai, aj]
            av10 = v10[ai, aj]
            av01 = v01[ai, aj]
            av11 = v11[ai, aj]
            ax0 = x0_all[0, aj]
            ay0 = y0_all[ai, 0]

            # Compute all four edge crossing points (vectorized)
            t_top = _safe_lerp(av00, av01, level)       # top edge
            t_bottom = _safe_lerp(av10, av11, level)     # bottom edge
            t_left = _safe_lerp(av00, av10, level)       # left edge
            t_right = _safe_lerp(av01, av11, level)      # right edge

            # Edge point coordinates: (x, y) for each of the 4 edges
            # 0=top, 1=bottom, 2=left, 3=right
            edge_x = np.stack([
                ax0 + t_top * cell_size,                 # top
                ax0 + t_bottom * cell_size,              # bottom
                ax0 + np.zeros_like(t_left),             # left (x = x0)
                ax0 + np.full_like(t_right, cell_size),  # right (x = x0 + cell_size)
            ])  # (4, N)
            edge_y = np.stack([
                ay0 + np.zeros_like(t_top),              # top (y = y0)
                ay0 + np.full_like(t_bottom, cell_size), # bottom (y = y0 + cell_size)
                ay0 + t_left * cell_size,                # left
                ay0 + t_right * cell_size,               # right
            ])  # (4, N)

            # Emit segments
            cases = case[ai, aj]
            contour_segments: list[list[tuple[float, float]]] = []

            for k in range(len(ai)):
                c = int(cases[k])
                seg_templates = _seg_table.get(c)
                if seg_templates is None:
                    continue
                for e1, e2 in seg_templates:
                    seg = [
                        (float(edge_x[e1, k]), float(edge_y[e1, k])),
                        (float(edge_x[e2, k]), float(edge_y[e2, k])),
                    ]
                    contour_segments.append(seg)
                    if len(contour_segments) >= max_segments_per_level:
                        break
                if len(contour_segments) >= max_segments_per_level:
                    break

            for seg in contour_segments[:max_segments_per_level]:
                features.append(
                    TerrainFeature(
                        type="contour",
                        geometry={
                            "type": "LineString",
                            "coordinates": seg,
                        },
                        properties={"elevation": level},
                    )
                )

        return features


def generate_terrain_3x3(
    world_seed: int,
    center_tx: int,
    center_ty: int,
    config_overrides: dict[str, Any] | None = None,
) -> TerrainResult:
    """Convenience function to generate 3x3 terrain.

    Args:
        world_seed: Seed for deterministic generation
        center_tx, center_ty: Center tile coordinates
        config_overrides: Optional config parameter overrides

    Returns:
        TerrainResult with 9 tiles
    """
    config_kwargs: dict[str, Any] = {"world_seed": world_seed}
    if config_overrides:
        config_kwargs.update(config_overrides)

    config = TerrainConfig(**config_kwargs)
    generator = TerrainGenerator(config)
    return generator.generate_3x3(center_tx, center_ty)
