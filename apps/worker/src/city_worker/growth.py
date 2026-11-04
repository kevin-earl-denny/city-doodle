"""City growth simulation module.

Simulates district expansion and density increases over time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Growth rates (per year) and max densities by district type
GROWTH_CONFIG: dict[str, dict[str, float]] = {
    "residential": {"expansion_rate": 0.03, "max_density": 8.0},
    "downtown": {"expansion_rate": 0.01, "max_density": 10.0},
    "commercial": {"expansion_rate": 0.02, "max_density": 8.0},
    "industrial": {"expansion_rate": 0.02, "max_density": 5.0},
    "hospital": {"expansion_rate": 0.0, "max_density": 4.0},
    "university": {"expansion_rate": 0.0, "max_density": 5.0},
    "k12": {"expansion_rate": 0.0, "max_density": 3.0},
    "park": {"expansion_rate": 0.0, "max_density": 0.5},
    "airport": {"expansion_rate": 0.0, "max_density": 2.0},
}

# Density growth rate per year (same scale as expansion for types that grow)
DENSITY_RATE = 0.3


@dataclass
class GrowthChange:
    """Describes a single district's growth change."""

    district_id: str
    old_geometry: dict[str, Any]
    new_geometry: dict[str, Any]
    old_density: float
    new_density: float


def _compute_centroid(coordinates: list[list[list[float]]]) -> tuple[float, float]:
    """Compute the centroid of a polygon's exterior ring."""
    ring = coordinates[0]
    # Exclude closing point if it duplicates the first
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if not points:
        return (0.0, 0.0)
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return (cx, cy)


def _scale_polygon(geometry: dict[str, Any], scale_factor: float) -> dict[str, Any]:
    """Scale a GeoJSON Polygon outward from its centroid.

    Each vertex is moved away from the centroid by scale_factor.
    """
    if geometry.get("type") != "Polygon":
        return geometry

    coordinates = geometry.get("coordinates", [])
    if not coordinates or not coordinates[0]:
        return geometry

    cx, cy = _compute_centroid(coordinates)

    new_coordinates = []
    for ring in coordinates:
        new_ring = []
        for point in ring:
            nx = cx + (point[0] - cx) * scale_factor
            ny = cy + (point[1] - cy) * scale_factor
            new_ring.append([nx, ny])
        new_coordinates.append(new_ring)

    return {**geometry, "coordinates": new_coordinates}


def simulate_growth(
    districts: list[dict[str, Any]],
    time_step: int = 1,
) -> list[GrowthChange]:
    """Simulate city growth for a list of districts.

    Args:
        districts: List of district dicts with keys: id, type, geometry, density, historic.
        time_step: Number of years to simulate (1, 5, or 10).

    Returns:
        List of GrowthChange objects describing what changed.
    """
    changes: list[GrowthChange] = []

    for district in districts:
        district_id = str(district["id"])
        district_type = district.get("type", "residential")
        is_historic = district.get("historic", False)
        geometry = district.get("geometry", {})
        density = float(district.get("density", 1.0))

        # Skip historic districts entirely
        if is_historic:
            continue

        config = GROWTH_CONFIG.get(district_type)
        if config is None:
            continue

        expansion_rate = config["expansion_rate"]
        max_density = config["max_density"]

        # Calculate new geometry (expand polygon)
        if expansion_rate > 0 and geometry.get("type") == "Polygon":
            scale_factor = 1.0 + expansion_rate * time_step
            new_geometry = _scale_polygon(geometry, scale_factor)
        else:
            new_geometry = geometry

        # Calculate new density
        if expansion_rate > 0:
            # Growing districts get density increases
            new_density = min(density + DENSITY_RATE * time_step, max_density)
        else:
            # Non-expanding districts get small density bumps (half rate)
            new_density = min(density + DENSITY_RATE * 0.5 * time_step, max_density)

        # Only record if something actually changed
        if new_geometry != geometry or new_density != density:
            changes.append(
                GrowthChange(
                    district_id=district_id,
                    old_geometry=geometry,
                    new_geometry=new_geometry,
                    old_density=density,
                    new_density=new_density,
                )
            )

    logger.info(
        "Growth simulation complete: %d districts changed (time_step=%d)",
        len(changes),
        time_step,
    )
    return changes
