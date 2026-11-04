"""Main terrain generator combining all terrain features."""

import logging
import time
from typing import Any

import numpy as np

from city_worker.terrain.bays import BayConfig, extract_bays
from city_worker.terrain.clip import clip_features_to_tile
from city_worker.terrain.contours import extract_contours, pad_heightfield_for_contours
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

# Heights at which contour lines are drawn.
CONTOUR_LEVELS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

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

        # CITY-678: Contours run after all tiles exist, because each tile
        # closes its sample grid with its right/bottom neighbours' first
        # row/column so contour lines meet exactly at tile borders.
        t_contours = time.perf_counter()
        by_offset = {(0, 0): center_data, **tiles}
        arrays = {k: np.asarray(t.heightfield, dtype=np.float64) for k, t in by_offset.items()}
        for (dx, dy), tile_data in by_offset.items():
            tile_data.features.extend(
                self._generate_contours(
                    tile_data,
                    arrays[(dx, dy)],
                    right=arrays.get((dx + 1, dy)),
                    bottom=arrays.get((dx, dy + 1)),
                    diagonal=arrays.get((dx + 1, dy + 1)),
                )
            )
        phase_totals["contours"] = time.perf_counter() - t_contours

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

        # Contours are added in generate_3x3 once neighbours exist (CITY-678)

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
            "clip": t_clip - t_beaches,
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
        tile_data: TileTerrainData,
        heightfield: np.ndarray,
        right: np.ndarray | None,
        bottom: np.ndarray | None,
        diagonal: np.ndarray | None,
    ) -> list[TerrainFeature]:
        """Generate connected contour polylines for one tile (CITY-678).

        Replaces the per-cell 2-point segments (capped at 100 per level)
        with whole polylines per level, simplified to keep the payload small.
        """
        cfg = self.config
        cell_size = cfg.tile_size / heightfield.shape[1]
        grid = pad_heightfield_for_contours(heightfield, right, bottom, diagonal)
        return extract_contours(
            grid,
            x0=tile_data.tx * cfg.tile_size,
            y0=tile_data.ty * cfg.tile_size,
            cell_size=cell_size,
            levels=CONTOUR_LEVELS,
            simplify_tolerance=cell_size * 0.5,
            min_loop_length=cell_size * 4,
        )


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
