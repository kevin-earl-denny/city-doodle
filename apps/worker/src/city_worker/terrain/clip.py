"""Tile boundary clipping for terrain features (CITY-530).

Water features (coastlines, beaches, bays, barrier islands, lakes) and
linear features (rivers, contours, dune ridges) can extend beyond their
tile's grid boundaries after generation.  This module provides a utility
to clip any TerrainFeature geometry to the tile bounding box so that
downstream rendering never sees out-of-bounds geometry.
"""

import logging
from typing import Any

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Polygon,
    box,
    shape,
)
from shapely.geometry.base import BaseGeometry

from city_worker.terrain.types import TerrainFeature

logger = logging.getLogger(__name__)

# Minimum ratio of clipped area to original area.  Features whose
# clipped area falls below this fraction are dropped entirely to avoid
# tiny sliver fragments at tile edges.
_MIN_AREA_RATIO = 0.01


def _geojson_to_shapely(geometry: dict[str, Any]) -> BaseGeometry | None:
    """Convert a GeoJSON-like geometry dict to a Shapely geometry.

    Returns None if the geometry type is not supported for clipping
    (e.g. Point).
    """
    geom_type = geometry.get("type")
    if geom_type == "Point":
        # Points are trivially inside or outside; we handle them
        # separately in clip_feature_to_tile.
        return None
    try:
        return shape(geometry)
    except (GEOSException, TopologicalError, ValueError) as e:
        logger.warning("Failed to parse geometry type=%s: %s", geometry.get("type"), e)
        return None


def _shapely_to_geojson(geom: BaseGeometry) -> dict[str, Any] | None:
    """Convert a Shapely geometry back to a GeoJSON-like dict.

    Returns None if the geometry is empty or degenerate.
    """
    if geom.is_empty:
        return None

    if isinstance(geom, Polygon):
        coords = [list(geom.exterior.coords)]
        for ring in geom.interiors:
            coords.append(list(ring.coords))
        return {"type": "Polygon", "coordinates": coords}

    if isinstance(geom, MultiPolygon):
        # Keep the largest polygon to avoid fragmented slivers.
        largest = max(geom.geoms, key=lambda p: p.area)
        return _shapely_to_geojson(largest)

    if isinstance(geom, LineString):
        return {"type": "LineString", "coordinates": list(geom.coords)}

    if isinstance(geom, MultiLineString):
        # Keep the longest linestring.
        longest = max(geom.geoms, key=lambda line: line.length)
        return _shapely_to_geojson(longest)

    if isinstance(geom, GeometryCollection):
        # Extract the first usable geometry from the collection.
        for child in geom.geoms:
            result = _shapely_to_geojson(child)
            if result is not None:
                return result
        return None

    # Unsupported geometry type.
    return None


def clip_feature_to_tile(
    feature: TerrainFeature,
    tile_x: int,
    tile_y: int,
    tile_size: float,
) -> TerrainFeature | None:
    """Clip a terrain feature's geometry to the tile bounding box.

    Args:
        feature: The terrain feature to clip.
        tile_x: Tile x-coordinate in the world grid.
        tile_y: Tile y-coordinate in the world grid.
        tile_size: Size of a tile in world units.

    Returns:
        A new TerrainFeature with clipped geometry, or ``None`` if the
        feature falls entirely outside the tile or is reduced to a
        negligible fragment (< 1% of original area for areal features).
    """
    geom_dict = feature.geometry
    geom_type = geom_dict.get("type")

    # --- Handle Point geometry (inlets) with simple bounds check ---
    if geom_type == "Point":
        coords = geom_dict.get("coordinates", [])
        if len(coords) < 2:
            return None
        x, y = coords[0], coords[1]
        x_min = tile_x * tile_size
        y_min = tile_y * tile_size
        x_max = (tile_x + 1) * tile_size
        y_max = (tile_y + 1) * tile_size
        if x_min <= x <= x_max and y_min <= y <= y_max:
            return feature
        return None

    # --- Convert to Shapely for intersection ---
    geom = _geojson_to_shapely(geom_dict)
    if geom is None or geom.is_empty:
        return None

    tile_box = box(
        tile_x * tile_size,
        tile_y * tile_size,
        (tile_x + 1) * tile_size,
        (tile_y + 1) * tile_size,
    )

    # Fast check: if the feature is entirely within the tile, return as-is.
    if tile_box.contains(geom):
        return feature

    # Perform the intersection.
    try:
        clipped = geom.intersection(tile_box)
    except (GEOSException, TopologicalError) as e:
        logger.warning("Intersection failed for %s feature: %s", feature.type, e)
        return None

    if clipped.is_empty:
        return None

    # --- Area-based fragment filter (polygonal features only) ---
    if isinstance(geom, (Polygon, MultiPolygon)):
        original_area = geom.area
        if original_area > 0:
            clipped_area = clipped.area if hasattr(clipped, "area") else 0
            if clipped_area / original_area < _MIN_AREA_RATIO:
                return None

    # --- Length-based fragment filter (linear features) ---
    if isinstance(geom, (LineString, MultiLineString)):
        original_length = geom.length
        if original_length > 0:
            clipped_length = clipped.length if hasattr(clipped, "length") else 0
            if clipped_length / original_length < _MIN_AREA_RATIO:
                return None

    # Convert back to GeoJSON dict.
    clipped_geojson = _shapely_to_geojson(clipped)
    if clipped_geojson is None:
        return None

    # Build updated properties.  If the feature had an "area" property,
    # update it to reflect the clipped geometry.
    properties = dict(feature.properties)
    if "area" in properties and isinstance(clipped, (Polygon, MultiPolygon)):
        if isinstance(clipped, MultiPolygon):
            largest = max(clipped.geoms, key=lambda p: p.area)
            properties["area"] = largest.area
        else:
            properties["area"] = clipped.area

    # Update length property for linear features.
    if "length" in properties and isinstance(clipped, (LineString, MultiLineString)):
        if isinstance(clipped, MultiLineString):
            longest = max(clipped.geoms, key=lambda line: line.length)
            properties["length"] = longest.length
        else:
            properties["length"] = clipped.length

    return TerrainFeature(
        type=feature.type,
        geometry=clipped_geojson,
        properties=properties,
    )


def clip_features_to_tile(
    features: list[TerrainFeature],
    tile_x: int,
    tile_y: int,
    tile_size: float,
) -> list[TerrainFeature]:
    """Clip a list of terrain features to the tile bounding box.

    Convenience wrapper around :func:`clip_feature_to_tile` that filters
    out ``None`` results.

    Args:
        features: List of terrain features to clip.
        tile_x: Tile x-coordinate.
        tile_y: Tile y-coordinate.
        tile_size: Tile size in world units.

    Returns:
        List of clipped features (features that are entirely outside the
        tile or reduced to negligible fragments are excluded).
    """
    clipped: list[TerrainFeature] = []
    for f in features:
        result = clip_feature_to_tile(f, tile_x, tile_y, tile_size)
        if result is not None:
            clipped.append(result)
    return clipped
