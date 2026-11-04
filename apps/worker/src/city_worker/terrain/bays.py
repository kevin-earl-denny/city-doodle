"""Bay detection for terrain - finding natural harbors in the water mask.

Inspired by real coastal cities: San Francisco Bay, Tokyo Bay, Sydney Harbour.

A bay is water that land partly wraps around.  It is found directly from
the land/water mask (CITY-682): morphologically closing the land mask
fills in water that sits inside a concave stretch of coast, and the
filled cells that are water in the real mask form the bays.  Bay
polygons are the exact outlines of those cells, so they never extend
over land, and bays do not modify the heightfield (the previous
synthetic-shape + erosion approach painted water over land and carved
cliffs at tile borders).
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from shapely.affinity import translate
from shapely.geometry import MultiPolygon, Polygon, box, mapping
from shapely.ops import unary_union

from city_worker.terrain.types import TerrainFeature
from city_worker.terrain.water import denoise_water_mask

logger = logging.getLogger(__name__)


@dataclass
class BayConfig:
    """Configuration for bay detection."""

    # Minimum land enclosure, expressed as an angle (degrees): a bay must
    # border land along at least min_concavity_angle / 180 of its edge.
    # 45 deg -> 25% of the bay's edge is coast.
    min_concavity_angle: float = 45.0

    # Minimum bay area in world units squared (pixel space; a 128-sample
    # tile of 256 units has 4 units^2 per cell).
    min_area: float = 40.0

    # Maximum depth / entrance-width ratio.  Narrower, longer inlets are
    # channels or fjords rather than bays.
    max_depth_ratio: float = 3.0

    # Size thresholds for bay classification (world units squared)
    cove_max_area: float = 600.0
    harbor_min_area: float = 6000.0

    # River mouths are prime bay sites: their minimum area is divided by
    # this factor so smaller estuarine bays are kept.
    river_mouth_factor: float = 2.0

    # Keep only the N largest bays per tile (CITY-647).
    max_bays: int = 5

    # Radius of the closing disk as a fraction of the tile edge.  Water
    # indentations narrower than ~2x this at the mouth become bays.  At the
    # default terrain scale (~2.6 noise cycles/tile) inlets are ~15-30% of
    # a tile wide.
    closing_radius_fraction: float = 1.0 / 6.0


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


def _disk(radius: int) -> NDArray[np.bool_]:
    """Boolean disk structuring element."""
    r = np.arange(-radius, radius + 1)
    return (r[:, None] ** 2 + r[None, :] ** 2) <= radius * radius


def _mask_to_polygon(
    mask: NDArray[np.bool_],
    tile_x: int,
    tile_y: int,
    tile_size: float,
    cell_size: float,
) -> Polygon | MultiPolygon | None:
    """Exact outline of the True cells in *mask*, in world coordinates.

    Merges horizontal runs per row into rectangles before unioning, so the
    union stays cheap even for large bays.
    """
    x0 = tile_x * tile_size
    y0 = tile_y * tile_size
    rects = []
    for i in np.flatnonzero(mask.any(axis=1)):
        row = np.concatenate(([False], mask[i], [False]))
        edges = np.flatnonzero(row[1:] != row[:-1])
        for start, end in zip(edges[::2], edges[1::2]):
            rects.append(
                box(
                    x0 + start * cell_size,
                    y0 + i * cell_size,
                    x0 + end * cell_size,
                    y0 + (i + 1) * cell_size,
                )
            )
    if not rects:
        return None
    return unary_union(rects)


def extract_bays(
    heightfield: NDArray[np.float64],
    water_level: float,
    tile_x: int,
    tile_y: int,
    tile_size: float,
    flow_accumulation: NDArray[np.float64] | None = None,
    config: BayConfig | None = None,
) -> list[TerrainFeature]:
    """Detect bays: water partially enclosed by a concave stretch of coast.

    Args:
        heightfield: 2D height array normalized to [0, 1]
        water_level: Threshold below which is water
        tile_x, tile_y: Tile coordinates for world positioning
        tile_size: Size of tile in world units
        flow_accumulation: Optional flow data for river mouth detection
        config: Bay detection configuration

    Returns:
        Bay polygon features, largest first, at most ``config.max_bays``.
    """
    if config is None:
        config = BayConfig()

    h, w = heightfield.shape
    cell_size = tile_size / w
    cell_area = cell_size * cell_size

    # Denoised so speckle puddles don't register as bays (CITY-647)
    water = denoise_water_mask(heightfield < water_level)
    land = ~water
    if not land.any() or not water.any():
        return []

    # Only sea water (connected to the tile edge) can form bays; lakes are
    # extracted separately and must not yield "bays" in their corners.
    water_labels, _ = ndimage.label(water)
    border_ids = np.unique(
        np.concatenate([water_labels[0], water_labels[-1], water_labels[:, 0], water_labels[:, -1]])
    )
    sea = np.isin(water_labels, border_ids[border_ids > 0])

    # Close the land mask.  Pad by replicating the edge so the coast is
    # assumed to continue straight past the tile border.
    radius = max(2, int(round(w * config.closing_radius_fraction)))
    padded = np.pad(land, radius, mode="edge")
    closed = ndimage.binary_closing(padded, structure=_disk(radius))
    closed = closed[radius:-radius, radius:-radius]

    enclosed = closed & sea
    open_water = sea & ~enclosed
    labels, count = ndimage.label(enclosed)
    if count == 0:
        return []

    four = ndimage.generate_binary_structure(2, 1)
    touches_open = ndimage.binary_dilation(open_water, structure=four)
    touches_land = ndimage.binary_dilation(land, structure=four)

    features: list[TerrainFeature] = []
    for idx, bbox in enumerate(ndimage.find_objects(labels), start=1):
        if bbox is None:
            continue
        # One-cell margin so the shore around the bay is inside the window
        region = tuple(
            slice(max(sl.start - 1, 0), min(sl.stop + 1, n)) for sl, n in zip(bbox, (h, w))
        )
        bay = labels[region] == idx

        mouth = bay & touches_open[region]
        if not mouth.any():
            continue  # fully enclosed water is a lake, not a bay

        is_river_mouth = False
        flow_at_mouth = 0.0
        if flow_accumulation is not None:
            # Rivers enter from the land side of the bay
            shore = ndimage.binary_dilation(bay, structure=four) & land[region]
            if shore.any():
                flow_at_mouth = float(flow_accumulation[region][shore].max())
                is_river_mouth = flow_at_mouth > w * 0.5

        area = float(bay.sum()) * cell_area
        min_area = config.min_area
        if is_river_mouth:
            min_area /= config.river_mouth_factor
        if area < min_area:
            continue

        # Enclosure: share of the bay's edge cells that border land
        edge = bay & ~ndimage.binary_erosion(bay, structure=four, border_value=1)
        enclosure = float((edge & touches_land[region]).sum()) / max(int(edge.sum()), 1)
        if enclosure * 180.0 < config.min_concavity_angle:
            continue

        entrance_width = float(mouth.sum()) * cell_size
        # Depth: farthest a bay cell sits from the open-water mouth
        depth_cells = ndimage.distance_transform_edt(~mouth)
        depth = float(depth_cells[bay].max()) * cell_size
        depth_ratio = depth / entrance_width if entrance_width > 0 else 0.0
        if depth_ratio > config.max_depth_ratio:
            continue

        poly = _mask_to_polygon(bay, tile_x, tile_y, tile_size, cell_size)
        if poly is None or poly.is_empty:
            continue
        # Offset the region-local polygon to the region's position in the tile
        poly = translate(poly, region[1].start * cell_size, region[0].start * cell_size)
        if isinstance(poly, MultiPolygon):
            # Diagonal-only connections split a component; keep the largest
            poly = max(poly.geoms, key=lambda p: p.area)

        water_depth = water_level - heightfield[region][bay]
        properties: dict[str, Any] = {
            "area": area,
            "bay_size": _classify_bay_size(area, config),
            "entrance_width": entrance_width,
            "depth": depth,
            "depth_ratio": depth_ratio,
            "avg_water_depth": float(water_depth.mean()),
            "max_water_depth": float(water_depth.max()),
            # Enclosure expressed on the same 0-180 scale as the config
            "concavity_angle": enclosure * 180.0,
            "is_river_mouth": is_river_mouth,
        }
        if is_river_mouth:
            properties["flow_accumulation"] = flow_at_mouth

        features.append(
            TerrainFeature(type="bay", geometry=mapping(poly), properties=properties)
        )

    # Stable sort keeps label order among equal areas (determinism)
    features.sort(key=lambda f: f.properties["area"], reverse=True)
    return features[: config.max_bays]
