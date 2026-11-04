"""River delta and estuary generation at river-ocean interfaces.

Detects where rivers terminate at the coastline and generates realistic
delta landforms:

- **Bird's foot delta**: 3-5 extending lobes into deep water (e.g. Mississippi)
- **Fan delta**: Arc of distributary channels into moderate-depth water (e.g. Nile)
- **Estuary**: Drowned river valley where coast drops steeply (e.g. Chesapeake)

Each delta produces distributary channels (feature_type: "delta_channel")
and, where appropriate, wetland polygons between the channels
(feature_type: "wetland").
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, Polygon

from city_worker.terrain.types import TerrainFeature

DeltaType = Literal["birds_foot", "fan", "estuary"]


@dataclass
class DeltaCandidate:
    """A river mouth identified as a delta candidate."""

    # Grid cell (row, col) of the river terminus
    terminus_cell: tuple[int, int]
    # World coordinates of the terminus
    terminus_xy: tuple[float, float]
    # Direction the river is flowing at the terminus (unit vector, world coords)
    flow_direction: tuple[float, float]
    # Flow magnitude at the terminus (from flow_accumulation)
    flow_magnitude: float
    # The last N cells of the river path (grid coords) used for branching
    tail_cells: list[tuple[int, int]]
    # Index into the river features list
    river_index: int


def detect_delta_candidates(
    rivers: list[TerrainFeature],
    heightfield: NDArray[np.float64],
    water_level: float,
    flow_accumulation: NDArray[np.float64],
    tile_x: int,
    tile_y: int,
    tile_size: float,
    min_flow: float = 50.0,
) -> list[DeltaCandidate]:
    """Find rivers that terminate at the coastline and are delta candidates.

    A river is a candidate if:
    1. Its last coordinate is near cells below water_level (coastal water)
    2. Its flow accumulation at the terminus exceeds min_flow

    Args:
        rivers: River features already extracted
        heightfield: 2D height array
        water_level: Sea level threshold
        flow_accumulation: Pre-computed flow grid
        tile_x, tile_y: Tile coordinates
        tile_size: Tile size in world units
        min_flow: Minimum flow at terminus to qualify as a delta

    Returns:
        List of DeltaCandidate objects
    """
    h, w = heightfield.shape
    cell_size = tile_size / w

    candidates: list[DeltaCandidate] = []

    for idx, river in enumerate(rivers):
        if river.type != "river":
            continue

        coords = river.geometry.get("coordinates", [])
        if len(coords) < 4:
            continue

        # Last coordinate is the terminus (downstream end)
        end_x, end_y = coords[-1][0], coords[-1][1]

        # Convert world coords to grid cell
        gj = int((end_x - tile_x * tile_size) / cell_size)
        gi = int((end_y - tile_y * tile_size) / cell_size)

        # Clamp to valid range
        gi = max(0, min(gi, h - 1))
        gj = max(0, min(gj, w - 1))

        # Check if terminus is near water (within 3 cells of a below-water cell)
        near_water = False
        for di in range(-3, 4):
            for dj in range(-3, 4):
                ni, nj = gi + di, gj + dj
                if 0 <= ni < h and 0 <= nj < w:
                    if heightfield[ni, nj] < water_level:
                        near_water = True
                        break
            if near_water:
                break

        if not near_water:
            continue

        # Check flow at terminus
        flow_val = float(flow_accumulation[gi, gj])
        if flow_val < min_flow:
            continue

        # Flow direction at the mouth. Prefer the tangent extract_rivers
        # recorded before simplifying the line (CITY-683); the last few
        # vertices of a simplified river can span most of its length.
        tail_n = min(6, len(coords))
        tail_coords = coords[-tail_n:]
        mouth_dir = river.properties.get("mouth_direction")
        if mouth_dir:
            flow_dir = (float(mouth_dir[0]), float(mouth_dir[1]))
        else:
            dx = tail_coords[-1][0] - tail_coords[0][0]
            dy = tail_coords[-1][1] - tail_coords[0][1]
            mag = math.hypot(dx, dy)
            if mag < 1e-10:
                continue
            flow_dir = (dx / mag, dy / mag)

        # Convert tail coordinates to grid cells
        tail_cells = []
        for cx, cy in tail_coords:
            tj = int((cx - tile_x * tile_size) / cell_size)
            ti = int((cy - tile_y * tile_size) / cell_size)
            ti = max(0, min(ti, h - 1))
            tj = max(0, min(tj, w - 1))
            tail_cells.append((ti, tj))

        candidates.append(
            DeltaCandidate(
                terminus_cell=(gi, gj),
                terminus_xy=(end_x, end_y),
                flow_direction=flow_dir,
                flow_magnitude=flow_val,
                tail_cells=tail_cells,
                river_index=idx,
            )
        )

    return candidates


def classify_delta_type(
    candidate: DeltaCandidate,
    heightfield: NDArray[np.float64],
    water_level: float,
) -> DeltaType:
    """Determine delta type from coastal depth profile at the terminus.

    - Steep coastal drop -> estuary (drowned valley, no distributaries)
    - Gradual depth + high flow -> bird's foot (extending lobes)
    - Moderate depth -> fan delta (arc of channels)

    Args:
        candidate: The delta candidate to classify
        heightfield: 2D height array
        water_level: Sea level threshold

    Returns:
        One of "birds_foot", "fan", or "estuary"
    """
    h, w = heightfield.shape
    gi, gj = candidate.terminus_cell
    dx, dy = candidate.flow_direction

    # Sample depth along the flow direction from the terminus
    depths: list[float] = []
    for step in range(1, 12):
        si = gi + int(round(dy * step))
        sj = gj + int(round(dx * step))
        if 0 <= si < h and 0 <= sj < w:
            depth_below = water_level - heightfield[si, sj]
            if depth_below > 0:
                depths.append(depth_below)

    if len(depths) < 3:
        # Not enough offshore data -- default to fan
        return "fan"

    # Calculate the gradient of depth (how fast it drops off per sample step).
    # Higher gradient = steeper offshore slope.
    depth_gradient = (depths[-1] - depths[0]) / len(depths) if len(depths) > 1 else 0

    # Also consider absolute depth at the furthest sample -- deep coastal
    # water favours estuaries.
    max_depth = depths[-1]

    if depth_gradient > 0.01 and max_depth > 0.15:
        # Steep drop into deep water -- estuary (drowned valley)
        return "estuary"
    elif candidate.flow_magnitude > 150 and depth_gradient < 0.006:
        # High flow, gentle offshore slope -- bird's foot delta
        return "birds_foot"
    elif candidate.flow_magnitude > 100 and depth_gradient < 0.008:
        # Moderate flow, moderate slope -- also bird's foot
        return "birds_foot"
    else:
        # Default -- fan delta (arc of channels)
        return "fan"


def _generate_distributary(
    origin_x: float,
    origin_y: float,
    base_dx: float,
    base_dy: float,
    angle_offset: float,
    length: float,
    cell_size: float,
    heightfield: NDArray[np.float64],
    water_level: float,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    seed: int,
) -> list[tuple[float, float]]:
    """Generate a single distributary channel from an origin point.

    The channel follows the base flow direction rotated by angle_offset,
    with small random perturbations for organic appearance.

    Args:
        origin_x, origin_y: Starting world coordinates
        base_dx, base_dy: Base flow direction (unit vector)
        angle_offset: Rotation in radians from the base direction
        length: Approximate channel length in world units
        cell_size: Grid cell size in world units
        heightfield: For terrain-following perturbation
        water_level: Sea level
        tile_x, tile_y, tile_size: Tile geometry
        seed: For deterministic randomness

    Returns:
        List of (x, y) coordinate tuples forming the channel
    """
    rng = np.random.default_rng(seed)

    # Rotate base direction by angle_offset
    cos_a = math.cos(angle_offset)
    sin_a = math.sin(angle_offset)
    dx = base_dx * cos_a - base_dy * sin_a
    dy = base_dx * sin_a + base_dy * cos_a

    h, w = heightfield.shape
    step_size = cell_size * 1.2
    num_steps = max(3, int(length / step_size))

    coords: list[tuple[float, float]] = [(origin_x, origin_y)]
    cx, cy = origin_x, origin_y

    for s in range(num_steps):
        # Add small random perturbation to direction
        perturb_angle = (rng.random() * 2 - 1) * 0.15
        cos_p = math.cos(perturb_angle)
        sin_p = math.sin(perturb_angle)
        pdx = dx * cos_p - dy * sin_p
        pdy = dx * sin_p + dy * cos_p

        cx += pdx * step_size
        cy += pdy * step_size
        coords.append((cx, cy))

        # Slightly curve outward from center as channel extends
        spread = 0.03 * (s / max(num_steps, 1))
        perp_dx = -dy
        perp_dy = dx
        sign = 1 if angle_offset >= 0 else -1
        cx += perp_dx * spread * step_size * sign
        cy += perp_dy * spread * step_size * sign

    return coords


def _smooth_coords(
    coords: list[tuple[float, float]], iterations: int = 2
) -> list[tuple[float, float]]:
    """Chaikin corner-cutting smoothing for natural-looking channels."""
    pts = list(coords)
    for _ in range(iterations):
        if len(pts) < 3:
            break
        new_pts = [pts[0]]
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            new_pts.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            new_pts.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        new_pts.append(pts[-1])
        pts = new_pts
    return pts


def _generate_wetland_polygon(
    channel_a: list[tuple[float, float]],
    channel_b: list[tuple[float, float]],
    heightfield: NDArray[np.float64],
    water_level: float,
    tile_x: int,
    tile_y: int,
    tile_size: float,
) -> Polygon | None:
    """Generate a wetland polygon between two adjacent distributary channels.

    The wetland fills the area between two channels, restricted to cells
    that are low-elevation (below water_level + 0.02).

    Args:
        channel_a, channel_b: Coordinate lists for two adjacent channels
        heightfield: 2D height array
        water_level: Sea level
        tile_x, tile_y, tile_size: Tile geometry

    Returns:
        A Shapely Polygon or None if the area is too small / invalid
    """
    # Build polygon from channel_a forward + channel_b reversed
    # This creates a region enclosed between the two channels
    if len(channel_a) < 2 or len(channel_b) < 2:
        return None

    ring = list(channel_a) + list(reversed(channel_b))
    # Close the ring
    if ring[0] != ring[-1]:
        ring.append(ring[0])

    if len(ring) < 4:
        return None

    try:
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not isinstance(poly, Polygon) or poly.is_empty or poly.area < 1e-6:
            return None

        # Verify the polygon overlaps low-elevation terrain
        h, w = heightfield.shape
        cell_size = tile_size / w
        wetland_threshold = water_level + 0.02

        # Sample a few points inside the polygon to confirm low elevation
        centroid = poly.centroid
        cx_grid = int((centroid.x - tile_x * tile_size) / cell_size)
        cy_grid = int((centroid.y - tile_y * tile_size) / cell_size)

        if 0 <= cy_grid < h and 0 <= cx_grid < w:
            if heightfield[cy_grid, cx_grid] > wetland_threshold:
                return None

        return poly

    except Exception:
        return None


def generate_delta_features(
    candidate: DeltaCandidate,
    delta_type: DeltaType,
    heightfield: NDArray[np.float64],
    water_level: float,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    seed: int,
) -> list[TerrainFeature]:
    """Generate delta channel and wetland features for a single delta.

    Args:
        candidate: The classified delta candidate
        delta_type: Type of delta to generate
        heightfield: 2D height array
        water_level: Sea level threshold
        tile_x, tile_y, tile_size: Tile geometry
        seed: Deterministic seed

    Returns:
        List of TerrainFeature for channels and wetlands
    """
    h, w = heightfield.shape
    cell_size = tile_size / w
    features: list[TerrainFeature] = []

    ox, oy = candidate.terminus_xy
    fdx, fdy = candidate.flow_direction

    if delta_type == "estuary":
        # Estuary: single widening channel, no distributaries
        # Generate a wide channel that flares outward
        length = cell_size * 8
        width_start = cell_size * 0.5
        width_end = cell_size * 2.5

        # Left bank
        perp_dx, perp_dy = -fdy, fdx
        left_coords = []
        right_coords = []
        num_pts = 8
        for i in range(num_pts):
            t = i / (num_pts - 1)
            px = ox + fdx * length * t
            py = oy + fdy * length * t
            w_half = (width_start + (width_end - width_start) * t) / 2
            left_coords.append((px + perp_dx * w_half, py + perp_dy * w_half))
            right_coords.append((px - perp_dx * w_half, py - perp_dy * w_half))

        # Smooth the banks
        left_coords = _smooth_coords(left_coords, iterations=2)
        right_coords = _smooth_coords(right_coords, iterations=2)

        # Create estuary polygon
        ring = left_coords + list(reversed(right_coords))
        if ring[0] != ring[-1]:
            ring.append(ring[0])

        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                features.append(
                    TerrainFeature(
                        type="estuary",
                        geometry={
                            "type": "Polygon",
                            "coordinates": [list(poly.exterior.coords)],
                        },
                        properties={
                            "delta_type": "estuary",
                            "area": poly.area,
                            "flow_magnitude": round(candidate.flow_magnitude, 1),
                        },
                    )
                )
        except Exception:
            pass

        # Wetlands along estuary banks
        wetland_offset = cell_size * 2
        for side_sign in [-1, 1]:
            bank_coords = left_coords if side_sign == 1 else right_coords
            if len(bank_coords) < 3:
                continue
            # Offset the bank outward to create wetland strip
            outer_coords = [
                (
                    x + perp_dx * wetland_offset * side_sign,
                    y + perp_dy * wetland_offset * side_sign,
                )
                for x, y in bank_coords
            ]
            wetland_ring = list(bank_coords) + list(reversed(outer_coords))
            if wetland_ring[0] != wetland_ring[-1]:
                wetland_ring.append(wetland_ring[0])
            try:
                wpoly = Polygon(wetland_ring)
                if not wpoly.is_valid:
                    wpoly = wpoly.buffer(0)
                if (
                    isinstance(wpoly, Polygon)
                    and wpoly.is_valid
                    and wpoly.area > cell_size * cell_size * 0.5
                ):
                    features.append(
                        TerrainFeature(
                            type="wetland",
                            geometry={
                                "type": "Polygon",
                                "coordinates": [list(wpoly.exterior.coords)],
                            },
                            properties={
                                "delta_type": "estuary",
                                "area": wpoly.area,
                            },
                        )
                    )
            except Exception:
                pass

        return features

    # For bird's foot and fan deltas, generate distributary channels
    rng = np.random.default_rng(seed)

    if delta_type == "birds_foot":
        # Bird's foot: 3-5 narrow, extending lobes
        num_channels = int(rng.integers(3, 6))
        # Spread angle: narrower than fan (channels extend outward)
        max_angle = math.radians(25)
        channel_length = cell_size * rng.uniform(10, 15)
    else:
        # Fan: 4-6 channels in an arc
        num_channels = int(rng.integers(4, 7))
        max_angle = math.radians(40)
        channel_length = cell_size * rng.uniform(6, 10)

    # Generate angles for each channel, evenly spaced
    if num_channels == 1:
        angles = [0.0]
    else:
        angles = [
            -max_angle + (2 * max_angle * i / (num_channels - 1)) for i in range(num_channels)
        ]
        # Add slight random jitter to each angle
        angles = [a + (rng.random() * 2 - 1) * math.radians(5) for a in angles]

    channels: list[list[tuple[float, float]]] = []

    for i, angle in enumerate(angles):
        # Vary channel length slightly
        cl = channel_length * rng.uniform(0.7, 1.3)

        raw_coords = _generate_distributary(
            origin_x=ox,
            origin_y=oy,
            base_dx=fdx,
            base_dy=fdy,
            angle_offset=angle,
            length=cl,
            cell_size=cell_size,
            heightfield=heightfield,
            water_level=water_level,
            tile_x=tile_x,
            tile_y=tile_y,
            tile_size=tile_size,
            seed=seed + i * 1013,
        )

        smoothed = _smooth_coords(raw_coords, iterations=3)
        channels.append(smoothed)

        # Width tapers from river width down to narrow tip
        width_base = cell_size * 0.4
        width_tip = cell_size * 0.1
        if delta_type == "birds_foot":
            width_base = cell_size * 0.3
            width_tip = cell_size * 0.08

        line = LineString(smoothed)
        if line.is_valid and line.length > cell_size:
            features.append(
                TerrainFeature(
                    type="delta_channel",
                    geometry={
                        "type": "LineString",
                        "coordinates": list(line.coords),
                    },
                    properties={
                        "delta_type": delta_type,
                        "channel_index": i,
                        "length": round(line.length, 2),
                        "width_base": round(width_base, 3),
                        "width_tip": round(width_tip, 3),
                        "flow_magnitude": round(candidate.flow_magnitude, 1),
                    },
                )
            )

    # Generate wetland polygons between adjacent channels
    for i in range(len(channels) - 1):
        wpoly = _generate_wetland_polygon(
            channels[i],
            channels[i + 1],
            heightfield,
            water_level,
            tile_x,
            tile_y,
            tile_size,
        )
        if wpoly is not None:
            features.append(
                TerrainFeature(
                    type="wetland",
                    geometry={
                        "type": "Polygon",
                        "coordinates": [list(wpoly.exterior.coords)],
                    },
                    properties={
                        "delta_type": delta_type,
                        "area": round(wpoly.area, 2),
                    },
                )
            )

    return features


def extract_deltas(
    rivers: list[TerrainFeature],
    heightfield: NDArray[np.float64],
    water_level: float,
    flow_accumulation: NDArray[np.float64],
    tile_x: int,
    tile_y: int,
    tile_size: float,
    seed: int,
    min_flow: float = 50.0,
) -> list[TerrainFeature]:
    """Top-level function: detect river deltas and generate features.

    This is the main entry point called from the terrain generator.

    Args:
        rivers: Already-extracted river features
        heightfield: 2D height array
        water_level: Sea level threshold
        flow_accumulation: Pre-computed flow grid
        tile_x, tile_y: Tile coordinates
        tile_size: Tile size in world units
        seed: Deterministic seed for generation
        min_flow: Minimum flow accumulation for delta candidacy

    Returns:
        List of TerrainFeature (delta_channel, wetland, estuary)
    """
    candidates = detect_delta_candidates(
        rivers=rivers,
        heightfield=heightfield,
        water_level=water_level,
        flow_accumulation=flow_accumulation,
        tile_x=tile_x,
        tile_y=tile_y,
        tile_size=tile_size,
        min_flow=min_flow,
    )

    features: list[TerrainFeature] = []

    for i, cand in enumerate(candidates):
        delta_type = classify_delta_type(cand, heightfield, water_level)

        delta_features = generate_delta_features(
            candidate=cand,
            delta_type=delta_type,
            heightfield=heightfield,
            water_level=water_level,
            tile_x=tile_x,
            tile_y=tile_y,
            tile_size=tile_size,
            seed=seed + i * 7717,
        )
        features.extend(delta_features)

    return features
