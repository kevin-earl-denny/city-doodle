"""Barrier island generation for coastal areas.

Barrier islands are long, narrow islands that form parallel to mainland coastlines.
They feature:
- Dune formations on the ocean side (higher elevation)
- Tidal flats on the lagoon side (lower elevation)
- Inlets that break up islands at natural intervals
- Lagoons/sounds between islands and mainland

Reference examples: Outer Banks, Miami Beach, Fire Island, Galveston.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, MultiPolygon, Polygon

from city_worker.terrain.types import TerrainFeature

logger = logging.getLogger(__name__)


@dataclass
class BarrierIslandConfig:
    """Configuration for barrier island generation."""

    # Distance from mainland coast (in cell units)
    island_offset_min: float = 8.0
    island_offset_max: float = 15.0

    # Island dimensions (in cell units)
    island_width_min: float = 2.0
    island_width_max: float = 5.0
    island_length_min: float = 20.0

    # Inlet parameters
    inlet_spacing_min: float = 30.0  # Minimum cells between inlets
    inlet_spacing_max: float = 60.0  # Maximum cells between inlets
    inlet_width_min: float = 2.0
    inlet_width_max: float = 5.0

    # Dune parameters (ocean-side elevation)
    dune_height: float = 0.15  # Height above water level
    dune_width_ratio: float = 0.3  # Portion of island width for dune

    # Tidal flat parameters (lagoon-side)
    tidal_flat_height: float = 0.03  # Just above water level
    tidal_flat_width_ratio: float = 0.25

    # Lagoon parameters
    lagoon_depth: float = 0.02  # Shallow water depth below water level

    # Minimum coastline slope for barrier island formation
    max_slope_threshold: float = 0.12  # Gradual slopes only


def detect_coastline_segments(
    heightfield: NDArray[np.float64],
    water_level: float,
    max_slope: float,
    min_segment_length: int = 15,
) -> list[list[tuple[int, int]]]:
    """Detect coastline segments suitable for barrier island formation.

    Barrier islands form along coastlines with gradual slopes, not steep cliffs.

    Args:
        heightfield: 2D height array normalized to [0, 1]
        water_level: Threshold below which is water
        max_slope: Maximum slope gradient for suitable coastlines
        min_segment_length: Minimum length of coastline segment

    Returns:
        List of coastline segments, each a list of (i, j) cell coordinates
    """
    h, w = heightfield.shape

    # Calculate slope magnitude
    grad_y = np.zeros_like(heightfield)
    grad_x = np.zeros_like(heightfield)
    grad_y[1:-1, :] = (heightfield[2:, :] - heightfield[:-2, :]) / 2
    grad_x[:, 1:-1] = (heightfield[:, 2:] - heightfield[:, :-2]) / 2
    slope = np.sqrt(grad_x**2 + grad_y**2)

    # Create water mask
    water_mask = heightfield < water_level

    # Find coastal cells (land cells adjacent to water with gentle slope)
    coastal_mask = np.zeros_like(water_mask, dtype=bool)

    for i in range(1, h - 1):
        for j in range(1, w - 1):
            if not water_mask[i, j] and slope[i, j] <= max_slope:
                # Check if adjacent to water
                for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ni, nj = i + di, j + dj
                    if water_mask[ni, nj]:
                        coastal_mask[i, j] = True
                        break

    # Trace connected coastal segments
    segments = []
    visited = np.zeros_like(coastal_mask, dtype=bool)

    for i in range(h):
        for j in range(w):
            if coastal_mask[i, j] and not visited[i, j]:
                segment = _trace_coastal_segment(coastal_mask, visited, i, j)
                if len(segment) >= min_segment_length:
                    segments.append(segment)

    return segments


def _trace_coastal_segment(
    coastal_mask: NDArray[np.bool_],
    visited: NDArray[np.bool_],
    start_i: int,
    start_j: int,
) -> list[tuple[int, int]]:
    """Trace a connected coastal segment using flood fill."""
    h, w = coastal_mask.shape
    segment = []
    stack = [(start_i, start_j)]

    while stack:
        i, j = stack.pop()
        if i < 0 or i >= h or j < 0 or j >= w:
            continue
        if visited[i, j] or not coastal_mask[i, j]:
            continue

        visited[i, j] = True
        segment.append((i, j))

        # 8-connectivity for smoother segments
        for di in [-1, 0, 1]:
            for dj in [-1, 0, 1]:
                if di == 0 and dj == 0:
                    continue
                stack.append((i + di, j + dj))

    return segment


def calculate_coastline_normal(
    segment: list[tuple[int, int]],
    water_mask: NDArray[np.bool_],
) -> list[tuple[float, float]]:
    """Calculate outward normal vectors for each point in a coastline segment.

    The normal points from land toward water (toward where islands should form).

    Args:
        segment: List of (i, j) coastal cell coordinates
        water_mask: Boolean mask of water cells

    Returns:
        List of (ni, nj) normal vectors for each point
    """
    h, w = water_mask.shape
    normals = []

    for i, j in segment:
        # Find direction to nearest water
        water_di, water_dj = 0.0, 0.0
        count = 0

        for di in [-2, -1, 0, 1, 2]:
            for dj in [-2, -1, 0, 1, 2]:
                if di == 0 and dj == 0:
                    continue
                ni, nj = i + di, j + dj
                if 0 <= ni < h and 0 <= nj < w and water_mask[ni, nj]:
                    dist = np.sqrt(di**2 + dj**2)
                    water_di += di / dist
                    water_dj += dj / dist
                    count += 1

        if count > 0:
            # Normalize
            mag = np.sqrt(water_di**2 + water_dj**2)
            if mag > 0:
                normals.append((water_di / mag, water_dj / mag))
            else:
                normals.append((0.0, 1.0))  # Default: point down
        else:
            normals.append((0.0, 1.0))

    return normals


def compute_wave_energy(
    segment: list[tuple[int, int]],
    normals: list[tuple[float, float]],
    water_mask: NDArray[np.bool_],
    seed: int,
) -> list[float]:
    """Compute relative wave energy along a coastline segment.

    Higher wave energy = more likely to have inlets (erosion points).
    Energy is based on:
    - Fetch distance (how far waves can travel)
    - Coastline orientation
    - Random variation

    Args:
        segment: Coastline cell coordinates
        normals: Normal vectors pointing toward water
        water_mask: Water mask
        seed: Random seed for variation

    Returns:
        List of energy values (0-1) for each point
    """
    rng = np.random.default_rng(seed)
    h, w = water_mask.shape
    energy = []

    for idx, (i, j) in enumerate(segment):
        ni, nj = normals[idx]

        # Calculate fetch (distance to land in wave direction)
        fetch = 0
        ci, cj = float(i), float(j)
        for _ in range(50):  # Max fetch distance
            ci += ni
            cj += nj
            ii, jj = int(round(ci)), int(round(cj))
            if ii < 0 or ii >= h or jj < 0 or jj >= w:
                fetch += 10  # Open water at edge = high fetch
                break
            if not water_mask[ii, jj]:
                break  # Hit land
            fetch += 1

        # Normalize fetch to 0-1
        fetch_energy = min(fetch / 30.0, 1.0)

        # Add random variation
        random_factor = 0.5 + 0.5 * rng.random()

        energy.append(fetch_energy * random_factor)

    return energy


def determine_inlet_positions(
    segment: list[tuple[int, int]],
    energy: list[float],
    config: BarrierIslandConfig,
    seed: int,
) -> list[int]:
    """Determine positions along segment where inlets should form.

    Inlets form at high-energy points with semi-regular spacing.

    Args:
        segment: Coastline coordinates
        energy: Wave energy values
        config: Island configuration
        seed: Random seed

    Returns:
        List of indices in segment where inlets occur
    """
    if len(segment) < config.inlet_spacing_min:
        return []

    rng = np.random.default_rng(seed)
    inlets = []

    # Sort potential inlet locations by energy (highest first)
    candidates = sorted(
        range(len(segment)),
        key=lambda x: energy[x],
        reverse=True,
    )

    for idx in candidates:
        # Check spacing from previous inlets
        min_dist = min(abs(idx - other) for other in inlets) if inlets else float("inf")

        if min_dist >= config.inlet_spacing_min:
            # Random chance based on energy
            if rng.random() < energy[idx] * 0.7:
                inlets.append(idx)

            # Stop if we have enough inlets
            if len(inlets) >= len(segment) / config.inlet_spacing_min:
                break

    return sorted(inlets)


def generate_island_chain(
    segment: list[tuple[int, int]],
    normals: list[tuple[float, float]],
    inlet_positions: list[int],
    config: BarrierIslandConfig,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    resolution: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Generate barrier island polygons along a coastline segment.

    Args:
        segment: Coastline cell coordinates
        normals: Normal vectors
        inlet_positions: Indices where inlets break up the chain
        config: Island configuration
        tile_x, tile_y: Tile coordinates
        tile_size: Size of tile in world units
        resolution: Grid resolution
        seed: Random seed

    Returns:
        List of island polygon dictionaries with geometry and properties
    """
    rng = np.random.default_rng(seed)
    cell_size = tile_size / resolution
    islands = []

    # Add boundary positions (start and end of segment)
    boundaries = [0] + inlet_positions + [len(segment) - 1]
    boundaries = sorted(set(boundaries))

    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1]

        # Skip if segment too short
        if end_idx - start_idx < config.island_length_min * 0.5:
            continue

        # Generate island polygon for this segment
        island_points = []

        # Offset varies slightly along the island
        base_offset = rng.uniform(config.island_offset_min, config.island_offset_max)

        # Ocean side (outer edge with dunes)
        for idx in range(start_idx, end_idx + 1):
            si, sj = segment[idx]
            ni, nj = normals[idx]

            # Add variation to offset
            offset = base_offset + rng.uniform(-1, 1)
            width = rng.uniform(config.island_width_min, config.island_width_max)

            # Ocean side point
            oi = si + ni * (offset + width)
            oj = sj + nj * (offset + width)

            # Convert to world coordinates
            world_x = tile_x * tile_size + oj * cell_size
            world_y = tile_y * tile_size + oi * cell_size

            island_points.append((world_x, world_y))

        # Lagoon side (inner edge) - reverse direction
        for idx in range(end_idx, start_idx - 1, -1):
            si, sj = segment[idx]
            ni, nj = normals[idx]

            offset = base_offset + rng.uniform(-1, 1)

            # Lagoon side point
            li = si + ni * offset
            lj = sj + nj * offset

            world_x = tile_x * tile_size + lj * cell_size
            world_y = tile_y * tile_size + li * cell_size

            island_points.append((world_x, world_y))

        # Close the polygon
        if len(island_points) >= 4:
            island_points.append(island_points[0])

            try:
                poly = Polygon(island_points)
                if poly.is_valid and poly.area > 0:
                    # Simplify for cleaner geometry
                    poly = poly.simplify(cell_size * 0.5, preserve_topology=True)
                    if poly.is_valid:
                        islands.append(
                            {
                                "geometry": poly,
                                "length": end_idx - start_idx,
                                "has_inlet_start": start_idx in inlet_positions,
                                "has_inlet_end": end_idx in inlet_positions,
                            }
                        )
            except (GEOSException, TopologicalError, ValueError) as e:
                logger.warning("Skipping invalid barrier island polygon: %s", e)

    return islands


def generate_lagoon(
    segment: list[tuple[int, int]],
    normals: list[tuple[float, float]],
    config: BarrierIslandConfig,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    resolution: int,
    seed: int,
) -> Polygon | None:
    """Generate lagoon/sound polygon between barrier islands and mainland.

    Args:
        segment: Coastline cell coordinates
        normals: Normal vectors
        config: Island configuration
        tile_x, tile_y: Tile coordinates
        tile_size: Tile size
        resolution: Grid resolution
        seed: Random seed

    Returns:
        Lagoon polygon or None if invalid
    """
    rng = np.random.default_rng(seed)
    cell_size = tile_size / resolution

    lagoon_points = []

    # Mainland side (coastline)
    for idx, (si, sj) in enumerate(segment):
        world_x = tile_x * tile_size + sj * cell_size
        world_y = tile_y * tile_size + si * cell_size
        lagoon_points.append((world_x, world_y))

    # Island side (offset from coastline)
    base_offset = rng.uniform(config.island_offset_min, config.island_offset_max)

    for idx in range(len(segment) - 1, -1, -1):
        si, sj = segment[idx]
        ni, nj = normals[idx]

        offset = base_offset + rng.uniform(-0.5, 0.5)

        li = si + ni * offset
        lj = sj + nj * offset

        world_x = tile_x * tile_size + lj * cell_size
        world_y = tile_y * tile_size + li * cell_size

        lagoon_points.append((world_x, world_y))

    if len(lagoon_points) >= 4:
        lagoon_points.append(lagoon_points[0])
        try:
            poly = Polygon(lagoon_points)
            if poly.is_valid and poly.area > 0:
                return poly.simplify(cell_size, preserve_topology=True)
        except (GEOSException, TopologicalError, ValueError) as e:
            logger.warning("Failed to create lagoon polygon: %s", e)

    return None


def generate_tidal_flats(
    islands: list[dict[str, Any]],
    lagoon: Polygon | None,
    config: BarrierIslandConfig,
    seed: int,
) -> list[Polygon]:
    """Generate tidal flat polygons on the lagoon side of barrier islands.

    Tidal flats are shallow, periodically exposed areas.

    Args:
        islands: List of island dictionaries with geometry
        lagoon: Lagoon polygon
        config: Island configuration
        seed: Random seed

    Returns:
        List of tidal flat polygons
    """
    flats = []

    for island_data in islands:
        island = island_data["geometry"]
        if not isinstance(island, Polygon):
            continue

        # Buffer the island slightly on the lagoon side
        # We create a thin strip along the inner edge
        try:
            # Create a small buffer and intersect with lagoon
            flat_buffer = island.buffer(island.length * config.tidal_flat_width_ratio * 0.1)
            if lagoon is not None and lagoon.is_valid:
                flat_area = flat_buffer.intersection(lagoon)
                if not flat_area.is_empty and flat_area.area > 0:
                    if isinstance(flat_area, Polygon):
                        flats.append(flat_area)
                    elif isinstance(flat_area, MultiPolygon):
                        flats.extend(flat_area.geoms)
        except (GEOSException, TopologicalError) as e:
            logger.warning("Failed to generate tidal flat for island: %s", e)

    return flats


def generate_dune_ridges(
    islands: list[dict[str, Any]],
    config: BarrierIslandConfig,
    seed: int,
) -> list[LineString]:
    """Generate dune ridge lines along the ocean side of barrier islands.

    Dune ridges represent the highest elevation on barrier islands.

    Args:
        islands: List of island dictionaries
        config: Island configuration
        seed: Random seed

    Returns:
        List of dune ridge LineStrings
    """
    rng = np.random.default_rng(seed)
    ridges = []

    for island_data in islands:
        island = island_data["geometry"]
        if not isinstance(island, Polygon):
            continue

        try:
            # Get the exterior ring
            exterior = island.exterior
            coords = list(exterior.coords)

            # The dune ridge is along the outer portion of the island
            # (first half of coordinates going one direction)
            half_len = len(coords) // 2
            if half_len >= 3:
                # Offset slightly inward for the ridge crest
                ridge_coords = []
                for i in range(min(half_len, len(coords) - 1)):
                    x, y = coords[i]
                    # Add slight variation
                    x += rng.uniform(-0.5, 0.5)
                    y += rng.uniform(-0.5, 0.5)
                    ridge_coords.append((x, y))

                if len(ridge_coords) >= 2:
                    ridge = LineString(ridge_coords)
                    if ridge.is_valid and ridge.length > 0:
                        ridges.append(ridge.simplify(1.0, preserve_topology=True))
        except (GEOSException, TopologicalError, ValueError) as e:
            logger.warning("Failed to generate dune ridge for island: %s", e)

    return ridges


def extract_barrier_islands(
    heightfield: NDArray[np.float64],
    water_level: float,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    seed: int,
    config: BarrierIslandConfig | None = None,
) -> list[TerrainFeature]:
    """Extract barrier island features from a heightfield.

    This is the main entry point for barrier island generation.

    Args:
        heightfield: 2D height array normalized to [0, 1]
        water_level: Water level threshold
        tile_x, tile_y: Tile coordinates
        tile_size: Tile size in world units
        seed: World seed for deterministic generation
        config: Optional configuration overrides

    Returns:
        List of terrain features (islands, lagoons, tidal flats, dunes)
    """
    if config is None:
        config = BarrierIslandConfig()

    h, w = heightfield.shape
    features = []

    # Create water mask
    water_mask = heightfield < water_level

    # Detect suitable coastline segments
    segments = detect_coastline_segments(
        heightfield=heightfield,
        water_level=water_level,
        max_slope=config.max_slope_threshold,
        min_segment_length=int(config.island_length_min),
    )

    if not segments:
        return features

    for seg_idx, segment in enumerate(segments):
        # Use different seed for each segment
        seg_seed = seed + seg_idx * 1000

        # Calculate normals for this segment
        normals = calculate_coastline_normal(segment, water_mask)

        # Compute wave energy
        energy = compute_wave_energy(segment, normals, water_mask, seg_seed)

        # Determine inlet positions
        inlets = determine_inlet_positions(segment, energy, config, seg_seed + 1)

        # Generate island chain
        islands = generate_island_chain(
            segment=segment,
            normals=normals,
            inlet_positions=inlets,
            config=config,
            tile_x=tile_x,
            tile_y=tile_y,
            tile_size=tile_size,
            resolution=w,
            seed=seg_seed + 2,
        )

        # Generate lagoon
        lagoon = generate_lagoon(
            segment=segment,
            normals=normals,
            config=config,
            tile_x=tile_x,
            tile_y=tile_y,
            tile_size=tile_size,
            resolution=w,
            seed=seg_seed + 3,
        )

        # Generate tidal flats
        tidal_flats = generate_tidal_flats(islands, lagoon, config, seg_seed + 4)

        # Generate dune ridges
        dune_ridges = generate_dune_ridges(islands, config, seg_seed + 5)

        # Convert to TerrainFeatures

        # Islands
        for i, island_data in enumerate(islands):
            island = island_data["geometry"]
            if isinstance(island, Polygon):
                features.append(
                    TerrainFeature(
                        type="barrier_island",
                        geometry={
                            "type": "Polygon",
                            "coordinates": [list(island.exterior.coords)],
                        },
                        properties={
                            "area": island.area,
                            "length": island_data["length"],
                            "has_inlet_start": island_data["has_inlet_start"],
                            "has_inlet_end": island_data["has_inlet_end"],
                            "island_index": i,
                            "segment_index": seg_idx,
                        },
                    )
                )

        # Lagoon
        if lagoon is not None and isinstance(lagoon, Polygon) and lagoon.is_valid:
            features.append(
                TerrainFeature(
                    type="lagoon",
                    geometry={
                        "type": "Polygon",
                        "coordinates": [list(lagoon.exterior.coords)],
                    },
                    properties={
                        "area": lagoon.area,
                        "depth": config.lagoon_depth,
                        "segment_index": seg_idx,
                    },
                )
            )

        # Tidal flats
        for flat in tidal_flats:
            if isinstance(flat, Polygon) and flat.is_valid and flat.area > 0:
                features.append(
                    TerrainFeature(
                        type="tidal_flat",
                        geometry={
                            "type": "Polygon",
                            "coordinates": [list(flat.exterior.coords)],
                        },
                        properties={
                            "area": flat.area,
                            "elevation": config.tidal_flat_height,
                            "segment_index": seg_idx,
                        },
                    )
                )

        # Dune ridges
        for ridge in dune_ridges:
            if ridge.is_valid and ridge.length > 0:
                features.append(
                    TerrainFeature(
                        type="dune_ridge",
                        geometry={
                            "type": "LineString",
                            "coordinates": list(ridge.coords),
                        },
                        properties={
                            "length": ridge.length,
                            "elevation": config.dune_height + water_level,
                            "segment_index": seg_idx,
                        },
                    )
                )

    # Create inlet features (gaps between islands)
    for seg_idx, segment in enumerate(segments):
        seg_seed = seed + seg_idx * 1000
        normals = calculate_coastline_normal(segment, water_mask)
        energy = compute_wave_energy(segment, normals, water_mask, seg_seed)
        inlets = determine_inlet_positions(segment, energy, config, seg_seed + 1)

        cell_size = tile_size / w
        for inlet_idx in inlets:
            if inlet_idx < len(segment) and inlet_idx < len(normals):
                si, sj = segment[inlet_idx]
                ni, nj = normals[inlet_idx]

                # Inlet center point
                offset = (config.island_offset_min + config.island_offset_max) / 2
                inlet_i = si + ni * offset
                inlet_j = sj + nj * offset

                world_x = tile_x * tile_size + inlet_j * cell_size
                world_y = tile_y * tile_size + inlet_i * cell_size

                features.append(
                    TerrainFeature(
                        type="inlet",
                        geometry={
                            "type": "Point",
                            "coordinates": [world_x, world_y],
                        },
                        properties={
                            "width": config.inlet_width_min
                            + (config.inlet_width_max - config.inlet_width_min) * energy[inlet_idx],
                            "energy": energy[inlet_idx],
                            "segment_index": seg_idx,
                        },
                    )
                )

    return features
