"""Bay generation for terrain - detecting and creating natural harbor formations.

Inspired by real coastal cities: San Francisco Bay, Tokyo Bay, Sydney Harbour.
Bay detection identifies concave coastline formations and generates organic
bay shapes with varied depths and sizes.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

from city_worker.terrain.types import TerrainFeature
from city_worker.terrain.water import denoise_water_mask

logger = logging.getLogger(__name__)


@dataclass
class BayConfig:
    """Configuration for bay generation."""

    # Minimum coastline concavity angle (degrees) to be considered a bay
    min_concavity_angle: float = 45.0

    # CITY-624: Area thresholds in pixel-space world units squared.
    # Scaled from meter-space by (256/80467.2)^2 ≈ 1.012e-5.
    min_area: float = 0.01

    # Maximum depth ratio (bay depth / entrance width)
    max_depth_ratio: float = 3.0

    # Size thresholds for bay classification (pixel-space)
    cove_max_area: float = 0.506  # Small cove
    harbor_min_area: float = 2.025  # Large harbor

    # River mouth bay bonus (how much river flow increases bay likelihood)
    river_mouth_factor: float = 2.0

    # Keep only the N largest bays per tile (CITY-647). Noisy coastlines can
    # yield hundreds of candidates, which render as overlapping blue triangles.
    max_bays: int = 5


@dataclass
class BayCandidate:
    """A potential bay detected in the coastline."""

    # Entrance points (where bay opens to sea)
    entrance_start: tuple[float, float]
    entrance_end: tuple[float, float]

    # Deepest point of the bay
    apex: tuple[float, float]

    # Concavity angle in degrees
    concavity_angle: float

    # Whether this is at a river mouth
    is_river_mouth: bool = False

    # Flow accumulation at this point (for river mouth detection)
    flow_accumulation: float = 0.0

    @property
    def entrance_width(self) -> float:
        """Calculate the width of the bay entrance."""
        dx = self.entrance_end[0] - self.entrance_start[0]
        dy = self.entrance_end[1] - self.entrance_start[1]
        return np.sqrt(dx * dx + dy * dy)

    @property
    def depth(self) -> float:
        """Calculate the depth (inland penetration) of the bay."""
        # Distance from entrance midpoint to apex
        mid_x = (self.entrance_start[0] + self.entrance_end[0]) / 2
        mid_y = (self.entrance_start[1] + self.entrance_end[1]) / 2
        dx = self.apex[0] - mid_x
        dy = self.apex[1] - mid_y
        return np.sqrt(dx * dx + dy * dy)


def _calculate_curvature(
    points: list[tuple[float, float]],
    window_size: int = 5,
) -> list[float]:
    """Calculate local curvature along a sequence of points.

    Positive curvature = concave (potential bay)
    Negative curvature = convex (headland)

    Args:
        points: Sequence of (x, y) coordinates forming the coastline
        window_size: Number of points to consider for curvature calculation

    Returns:
        List of curvature values (one per point, edges padded with 0)
    """
    n = len(points)
    if n < window_size:
        return [0.0] * n

    curvatures = []
    half_window = window_size // 2

    for i in range(n):
        if i < half_window or i >= n - half_window:
            curvatures.append(0.0)
            continue

        # Get points in window
        p_before = points[i - half_window]
        p_current = points[i]
        p_after = points[i + half_window]

        # Calculate vectors
        v1 = (p_current[0] - p_before[0], p_current[1] - p_before[1])
        v2 = (p_after[0] - p_current[0], p_after[1] - p_current[1])

        # Normalize vectors
        len1 = np.sqrt(v1[0] ** 2 + v1[1] ** 2)
        len2 = np.sqrt(v2[0] ** 2 + v2[1] ** 2)

        if len1 < 1e-10 or len2 < 1e-10:
            curvatures.append(0.0)
            continue

        v1 = (v1[0] / len1, v1[1] / len1)
        v2 = (v2[0] / len2, v2[1] / len2)

        # Cross product gives signed curvature
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        curvatures.append(cross)

    return curvatures


def _find_concave_regions(
    coastline_points: list[tuple[float, float]],
    curvatures: list[float],
    min_curvature: float = 0.1,
) -> list[tuple[int, int, int]]:
    """Find contiguous concave regions in the coastline.

    Returns:
        List of (start_idx, apex_idx, end_idx) tuples for each concave region
    """
    n = len(coastline_points)
    regions = []
    i = 0

    while i < n:
        # Skip until we find positive curvature (concave)
        if curvatures[i] < min_curvature:
            i += 1
            continue

        # Found start of concave region
        start_idx = i

        # Find the peak curvature (apex) and end of region
        max_curv = curvatures[i]
        apex_idx = i

        while i < n and curvatures[i] >= min_curvature * 0.5:
            if curvatures[i] > max_curv:
                max_curv = curvatures[i]
                apex_idx = i
            i += 1

        end_idx = i - 1 if i > start_idx else start_idx

        # Only consider if region spans enough points
        if end_idx - start_idx >= 3:
            regions.append((start_idx, apex_idx, end_idx))

    return regions


def _calculate_concavity_angle(
    p_start: tuple[float, float],
    p_apex: tuple[float, float],
    p_end: tuple[float, float],
) -> float:
    """Calculate the concavity angle at the apex point.

    Returns angle in degrees (0-180). Larger angle = deeper bay.
    """
    # Vectors from apex to start and end
    v1 = (p_start[0] - p_apex[0], p_start[1] - p_apex[1])
    v2 = (p_end[0] - p_apex[0], p_end[1] - p_apex[1])

    # Calculate angle using dot product
    len1 = np.sqrt(v1[0] ** 2 + v1[1] ** 2)
    len2 = np.sqrt(v2[0] ** 2 + v2[1] ** 2)

    if len1 < 1e-10 or len2 < 1e-10:
        return 0.0

    dot = (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)
    dot = max(-1.0, min(1.0, dot))  # Clamp for numerical stability

    angle = np.degrees(np.arccos(dot))
    return 180.0 - angle  # Convert to concavity angle


def detect_bay_candidates(
    coastline_coords: list[tuple[float, float]],
    flow_accumulation: NDArray[np.float64] | None = None,
    heightfield: NDArray[np.float64] | None = None,
    tile_x: int = 0,
    tile_y: int = 0,
    tile_size: float = 1000.0,
    min_concavity_angle: float = 45.0,
) -> list[BayCandidate]:
    """Detect potential bay locations along a coastline.

    Uses curvature analysis to find concave regions that could form natural bays.
    Also considers river mouths as prime bay locations.

    Args:
        coastline_coords: List of (x, y) coordinates forming the coastline
        flow_accumulation: Optional flow accumulation grid for river detection
        heightfield: Optional heightfield for depth analysis
        tile_x, tile_y: Tile coordinates for world positioning
        tile_size: Size of tile in world units
        min_concavity_angle: Minimum angle (degrees) to consider as a bay

    Returns:
        List of BayCandidate objects
    """
    if len(coastline_coords) < 10:
        return []

    # Calculate curvature along coastline
    curvatures = _calculate_curvature(coastline_coords, window_size=7)

    # Find concave regions
    concave_regions = _find_concave_regions(coastline_coords, curvatures)

    candidates = []

    for start_idx, apex_idx, end_idx in concave_regions:
        p_start = coastline_coords[start_idx]
        p_apex = coastline_coords[apex_idx]
        p_end = coastline_coords[end_idx]

        # Calculate concavity angle
        angle = _calculate_concavity_angle(p_start, p_apex, p_end)

        if angle < min_concavity_angle:
            continue

        # Check for river mouth
        is_river_mouth = False
        flow_at_apex = 0.0

        if flow_accumulation is not None and heightfield is not None:
            h, w = heightfield.shape
            cell_size = tile_size / w

            # Convert apex to grid coordinates
            apex_grid_x = int((p_apex[0] - tile_x * tile_size) / cell_size)
            apex_grid_y = int((p_apex[1] - tile_y * tile_size) / cell_size)

            if 0 <= apex_grid_x < w and 0 <= apex_grid_y < h:
                flow_at_apex = flow_accumulation[apex_grid_y, apex_grid_x]
                # High flow indicates river mouth
                if flow_at_apex > w * 0.5:  # Significant flow accumulation
                    is_river_mouth = True

        candidates.append(
            BayCandidate(
                entrance_start=p_start,
                entrance_end=p_end,
                apex=p_apex,
                concavity_angle=angle,
                is_river_mouth=is_river_mouth,
                flow_accumulation=flow_at_apex,
            )
        )

    return candidates


def _generate_bay_shape(
    candidate: BayCandidate,
    rng: np.random.Generator,
    detail_level: int = 12,
) -> list[tuple[float, float]]:
    """Generate an organic bay shape from a candidate.

    Creates a smooth, natural-looking bay outline using
    bezier-like interpolation with random perturbations.

    Args:
        candidate: Bay candidate with entrance and apex points
        rng: Random number generator for reproducibility
        detail_level: Number of points to generate along each side

    Returns:
        List of (x, y) coordinates forming the bay polygon
    """
    start = candidate.entrance_start
    apex = candidate.apex
    end = candidate.entrance_end

    points = []

    # Generate points along start -> apex path with organic curves
    for i in range(detail_level + 1):
        t = i / detail_level

        # Quadratic bezier-like interpolation
        # Control point offset creates natural curve
        ctrl_offset = candidate.entrance_width * 0.4 * (1 + rng.random() * 0.3)

        # Direction perpendicular to start-apex line
        dx = apex[0] - start[0]
        dy = apex[1] - start[1]
        perp = (-dy, dx)
        perp_len = np.sqrt(perp[0] ** 2 + perp[1] ** 2)
        if perp_len > 1e-10:
            perp = (perp[0] / perp_len, perp[1] / perp_len)
        else:
            perp = (0, 1)

        # Add controlled randomness for organic feel
        noise = (rng.random() - 0.5) * candidate.entrance_width * 0.1 * np.sin(t * np.pi)

        # Bezier interpolation with noise
        x = (1 - t) * start[0] + t * apex[0] + perp[0] * ctrl_offset * np.sin(t * np.pi) + noise
        y = (1 - t) * start[1] + t * apex[1] + perp[1] * ctrl_offset * np.sin(t * np.pi) + noise

        points.append((x, y))

    # Generate points along apex -> end path
    for i in range(1, detail_level + 1):  # Skip first point (apex already added)
        t = i / detail_level

        # Similar bezier curve on the other side
        ctrl_offset = candidate.entrance_width * 0.4 * (1 + rng.random() * 0.3)

        dx = end[0] - apex[0]
        dy = end[1] - apex[1]
        perp = (-dy, dx)
        perp_len = np.sqrt(perp[0] ** 2 + perp[1] ** 2)
        if perp_len > 1e-10:
            perp = (perp[0] / perp_len, perp[1] / perp_len)
        else:
            perp = (0, 1)

        noise = (rng.random() - 0.5) * candidate.entrance_width * 0.1 * np.sin(t * np.pi)

        x = (1 - t) * apex[0] + t * end[0] - perp[0] * ctrl_offset * np.sin(t * np.pi) + noise
        y = (1 - t) * apex[1] + t * end[1] - perp[1] * ctrl_offset * np.sin(t * np.pi) + noise

        points.append((x, y))

    return points


def _calculate_bay_depth_profile(
    bay_points: list[tuple[float, float]],
    entrance_start: tuple[float, float],
    entrance_end: tuple[float, float],
    apex: tuple[float, float],
    max_depth: float,
    rng: np.random.Generator,
) -> list[float]:
    """Calculate realistic depth values for each point in the bay.

    Depth increases from entrance to apex, with natural variation.
    Simulates how real bays tend to be deeper toward the inner harbor.

    Args:
        bay_points: Points forming the bay outline
        entrance_start, entrance_end: Bay entrance points
        apex: Deepest point of bay
        max_depth: Maximum depth at apex
        rng: Random generator for natural variation

    Returns:
        List of depth values corresponding to each bay point
    """
    depths = []
    entrance_mid = (
        (entrance_start[0] + entrance_end[0]) / 2,
        (entrance_start[1] + entrance_end[1]) / 2,
    )

    for point in bay_points:
        # Distance from entrance to point
        dx_entrance = point[0] - entrance_mid[0]
        dy_entrance = point[1] - entrance_mid[1]
        dist_from_entrance = np.sqrt(dx_entrance**2 + dy_entrance**2)

        # Distance from entrance to apex (total bay depth)
        dx_apex = apex[0] - entrance_mid[0]
        dy_apex = apex[1] - entrance_mid[1]
        total_depth = np.sqrt(dx_apex**2 + dy_apex**2)

        if total_depth < 1e-10:
            depths.append(0.0)
            continue

        # Normalized position along bay (0 = entrance, 1 = apex)
        t = min(1.0, dist_from_entrance / total_depth)

        # Depth increases with distance from entrance
        # Using smooth curve (faster increase near entrance, gradual near apex)
        base_depth = max_depth * (1 - (1 - t) ** 2)

        # Add natural variation (deeper channels, shallower edges)
        variation = rng.normal(0, max_depth * 0.1)
        depth = max(0.0, base_depth + variation)

        depths.append(depth)

    return depths


def _classify_bay_size(area: float, config: BayConfig) -> str:
    """Classify bay size based on area.

    Returns:
        "cove" for small bays, "bay" for medium, "harbor" for large
    """
    if area < config.cove_max_area:
        return "cove"
    elif area >= config.harbor_min_area:
        return "harbor"
    else:
        return "bay"


def extract_bays(
    heightfield: NDArray[np.float64],
    water_level: float,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    seed: int,
    flow_accumulation: NDArray[np.float64] | None = None,
    config: BayConfig | None = None,
) -> list[TerrainFeature]:
    """Extract bay features from terrain.

    Identifies concave coastline formations and generates natural bay shapes
    with varied depths and sizes. Considers river mouths as prime bay locations.

    Inspired by real-world bays:
    - San Francisco Bay: Large, deep bay with narrow entrance (Golden Gate)
    - Tokyo Bay: Wide entrance, moderate depth, multiple inner harbors
    - Sydney Harbour: Highly irregular coastline with many small coves

    Args:
        heightfield: 2D height array normalized to [0, 1]
        water_level: Threshold below which is water
        tile_x, tile_y: Tile coordinates for world positioning
        tile_size: Size of tile in world units
        seed: Random seed for reproducible generation
        flow_accumulation: Optional flow data for river mouth detection
        config: Bay generation configuration

    Returns:
        List of bay polygon features with properties
    """
    if config is None:
        config = BayConfig()

    # Ensure seed is non-negative for numpy's RNG
    rng = np.random.default_rng(abs(seed) % (2**31))
    h, w = heightfield.shape
    cell_size = tile_size / w

    # Create land/water mask, denoised so speckle puddles don't register as
    # hundreds of tiny coastline concavities (CITY-647)
    land_mask = ~denoise_water_mask(heightfield < water_level)

    # Coastline cells: interior land cells with at least one 4-neighbor water cell
    inner = land_mask[1:-1, 1:-1]
    touches_water = (
        ~land_mask[:-2, 1:-1] | ~land_mask[2:, 1:-1] | ~land_mask[1:-1, :-2] | ~land_mask[1:-1, 2:]
    )
    ii, jj = np.nonzero(inner & touches_water)
    coastline_points: list[tuple[float, float]] = [
        (tile_x * tile_size + (j + 1.5) * cell_size, tile_y * tile_size + (i + 1.5) * cell_size)
        for i, j in zip(ii.tolist(), jj.tolist())
    ]

    if len(coastline_points) < 20:
        return []

    # Sort coastline points to form a continuous line
    # Use nearest-neighbor ordering
    sorted_points = [coastline_points[0]]
    remaining = set(range(1, len(coastline_points)))

    while remaining:
        last = sorted_points[-1]
        nearest_idx = None
        nearest_dist = float("inf")

        for idx in remaining:
            p = coastline_points[idx]
            dist = (p[0] - last[0]) ** 2 + (p[1] - last[1]) ** 2
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = idx

        if nearest_idx is None or nearest_dist > (cell_size * 5) ** 2:
            # Gap in coastline, start new segment
            if remaining:
                next_idx = min(remaining)
                remaining.remove(next_idx)
                sorted_points.append(coastline_points[next_idx])
        else:
            remaining.remove(nearest_idx)
            sorted_points.append(coastline_points[nearest_idx])

    # Detect bay candidates
    candidates = detect_bay_candidates(
        coastline_coords=sorted_points,
        flow_accumulation=flow_accumulation,
        heightfield=heightfield,
        tile_x=tile_x,
        tile_y=tile_y,
        tile_size=tile_size,
        min_concavity_angle=config.min_concavity_angle,
    )

    features = []

    # Minimum entrance width for harbor-classified bays (world units).
    # Bays with large area but narrow entrances are unrealistic harbors.
    # CITY-624: Scaled from 30.0 meters to pixel-space (30 * 256/80467.2).
    harbor_min_entrance_width = 0.0954

    for candidate in candidates:
        # Skip bays that are too shallow (low depth ratio)
        depth_ratio = candidate.depth / candidate.entrance_width if candidate.entrance_width > 0 else 0
        if depth_ratio < 0.3 or depth_ratio > config.max_depth_ratio:
            continue

        # Enforce minimum entrance width for harbor-scale bays.
        # If the candidate's area estimate suggests a harbor but the
        # entrance is too narrow, widen it to the minimum threshold.
        estimated_area = candidate.entrance_width * candidate.depth
        if estimated_area >= config.harbor_min_area and candidate.entrance_width < harbor_min_entrance_width:
            # Shift entrance points outward to meet the minimum width
            mid_x = (candidate.entrance_start[0] + candidate.entrance_end[0]) / 2
            mid_y = (candidate.entrance_start[1] + candidate.entrance_end[1]) / 2
            dx = candidate.entrance_end[0] - candidate.entrance_start[0]
            dy = candidate.entrance_end[1] - candidate.entrance_start[1]
            cur_w = candidate.entrance_width
            if cur_w > 1e-10:
                scale = harbor_min_entrance_width / cur_w
                candidate.entrance_start = (
                    mid_x - dx / 2 * scale,
                    mid_y - dy / 2 * scale,
                )
                candidate.entrance_end = (
                    mid_x + dx / 2 * scale,
                    mid_y + dy / 2 * scale,
                )

        # Generate organic bay shape
        bay_points = _generate_bay_shape(candidate, rng)

        if len(bay_points) < 3:
            continue

        # Create polygon and check validity
        try:
            bay_poly = Polygon(bay_points)
            if not bay_poly.is_valid:
                bay_poly = bay_poly.buffer(0)  # Fix self-intersections

            # Handle case where buffer() returns MultiPolygon
            if hasattr(bay_poly, 'geoms'):
                # It's a MultiPolygon, take the largest polygon
                from shapely.geometry import MultiPolygon as ShapelyMultiPolygon
                if isinstance(bay_poly, ShapelyMultiPolygon):
                    bay_poly = max(bay_poly.geoms, key=lambda p: p.area)

            if not bay_poly.is_valid or bay_poly.is_empty:
                continue
            if not isinstance(bay_poly, Polygon):
                continue
        except (GEOSException, TopologicalError, ValueError) as e:
            logger.warning("Failed to create bay polygon: %s", e)
            continue

        area = bay_poly.area
        if area < config.min_area:
            continue

        # Classify bay size
        bay_size = _classify_bay_size(area, config)

        # Calculate depth profile
        max_depth = water_level * 1.2  # Max depth relative to water level
        if candidate.is_river_mouth:
            max_depth *= 1.2  # River mouths tend to be deeper (erosion)

        depths = _calculate_bay_depth_profile(
            bay_points,
            candidate.entrance_start,
            candidate.entrance_end,
            candidate.apex,
            max_depth,
            rng,
        )
        avg_depth = np.mean(depths)
        max_depth_actual = max(depths) if depths else 0.0

        # Build feature properties
        properties: dict[str, Any] = {
            "area": area,
            "bay_size": bay_size,
            "entrance_width": candidate.entrance_width,
            "depth": candidate.depth,
            "depth_ratio": depth_ratio,
            "avg_water_depth": avg_depth,
            "max_water_depth": max_depth_actual,
            "concavity_angle": candidate.concavity_angle,
            "is_river_mouth": candidate.is_river_mouth,
        }

        if candidate.is_river_mouth:
            properties["flow_accumulation"] = candidate.flow_accumulation

        features.append(
            TerrainFeature(
                type="bay",
                geometry={
                    "type": "Polygon",
                    "coordinates": [list(bay_poly.exterior.coords)],
                },
                properties=properties,
            )
        )

    # Stable sort keeps generation order among equal areas (determinism)
    features.sort(key=lambda f: f.properties["area"], reverse=True)
    return features[: config.max_bays]


def apply_bay_erosion(
    heightfield: NDArray[np.float64],
    bay_features: list[TerrainFeature],
    water_level: float,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    erosion_strength: float = 0.5,
) -> NDArray[np.float64]:
    """Apply erosion effects within bay regions.

    Deepens the bay area and creates natural depth gradients,
    simulating the erosion that creates real-world bays.

    Args:
        heightfield: 2D height array
        bay_features: List of detected bay features
        water_level: Water level threshold
        tile_x, tile_y: Tile coordinates
        tile_size: Tile size in world units
        erosion_strength: How much to erode (0-1)

    Returns:
        Modified heightfield with bay erosion applied
    """
    result = heightfield.copy()
    h, w = heightfield.shape
    cell_size = tile_size / w

    for feature in bay_features:
        if feature.type != "bay":
            continue

        coords = feature.geometry.get("coordinates", [[]])
        if not coords or not coords[0]:
            continue

        try:
            bay_poly = Polygon(coords[0])
            if not bay_poly.is_valid:
                continue
        except (GEOSException, TopologicalError, ValueError) as e:
            logger.warning("Failed to parse bay polygon for erosion: %s", e)
            continue

        # Get bay properties
        max_depth = feature.properties.get("max_water_depth", 0.1)
        is_river_mouth = feature.properties.get("is_river_mouth", False)

        # Apply erosion to cells within bay bounds
        minx, miny, maxx, maxy = bay_poly.bounds

        for i in range(h):
            for j in range(w):
                world_x = tile_x * tile_size + (j + 0.5) * cell_size
                world_y = tile_y * tile_size + (i + 0.5) * cell_size

                if not (minx <= world_x <= maxx and miny <= world_y <= maxy):
                    continue

                point = Point(world_x, world_y)
                if bay_poly.contains(point):
                    current_height = result[i, j]

                    # Calculate erosion based on distance from bay center
                    centroid = bay_poly.centroid
                    dist_to_center = point.distance(centroid)
                    max_dist = np.sqrt(bay_poly.area / np.pi)

                    # More erosion toward center (deeper)
                    normalized_dist = min(1.0, dist_to_center / max_dist) if max_dist > 0 else 0
                    erosion = erosion_strength * max_depth * (1 - normalized_dist ** 2)

                    # River mouths erode more
                    if is_river_mouth:
                        erosion *= 1.3

                    # Apply erosion (lower height = deeper water)
                    new_height = current_height - erosion
                    result[i, j] = max(0.0, new_height)

    return result
