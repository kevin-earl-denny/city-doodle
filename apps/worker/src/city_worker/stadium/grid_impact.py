"""Street grid impact calculation for stadiums.

When a stadium is placed, surrounding streets should orient toward it.
This module calculates which streets are affected and how their geometry
should be adjusted to create natural access routes to the stadium.
"""

import math
from dataclasses import dataclass
from uuid import UUID

from city_worker.stadium.types import (
    Point,
    StadiumPlacement,
    StreetOrientationResult,
    StreetGridImpactResult,
)


def calculate_impact_radius(stadium: StadiumPlacement) -> float:
    """Calculate the effective impact radius for a stadium.

    The impact radius determines how far from the stadium center
    the street grid is affected.
    """
    return stadium.config.impact_radius


def distance(p1: Point, p2: Point) -> float:
    """Calculate Euclidean distance between two points."""
    return math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2)


def angle_to_point(from_point: Point, to_point: Point) -> float:
    """Calculate angle in degrees from from_point to to_point."""
    dx = to_point.x - from_point.x
    dy = to_point.y - from_point.y
    return math.degrees(math.atan2(dy, dx))


def point_along_segment(p1: Point, p2: Point, t: float) -> Point:
    """Get a point along the segment from p1 to p2 at parameter t (0-1)."""
    return Point(
        x=p1.x + t * (p2.x - p1.x),
        y=p1.y + t * (p2.y - p1.y),
    )


def closest_point_on_segment(p: Point, seg_start: Point, seg_end: Point) -> Point:
    """Find the closest point on a line segment to a given point."""
    dx = seg_end.x - seg_start.x
    dy = seg_end.y - seg_start.y
    length_sq = dx * dx + dy * dy

    if length_sq == 0:
        return seg_start

    # Project point onto the line
    t = max(0, min(1, ((p.x - seg_start.x) * dx + (p.y - seg_start.y) * dy) / length_sq))
    return Point(
        x=seg_start.x + t * dx,
        y=seg_start.y + t * dy,
    )


def compute_street_orientation(
    road_geometry: list[Point],
    stadium: StadiumPlacement,
    orientation_strength: float = 0.8,
) -> list[Point]:
    """Compute adjusted road geometry that orients toward the stadium.

    Args:
        road_geometry: Original road geometry as list of points.
        stadium: The stadium placement.
        orientation_strength: How strongly to pull points toward stadium (0-1).

    Returns:
        Adjusted geometry with points pulled toward stadium based on distance.
    """
    if len(road_geometry) < 2:
        return road_geometry

    impact_radius = stadium.config.impact_radius
    stadium_center = stadium.center
    adjusted = []

    for point in road_geometry:
        dist = distance(point, stadium_center)

        if dist > impact_radius or dist < 1.0:
            # Outside impact radius or at stadium center - no adjustment
            adjusted.append(point)
            continue

        # Calculate influence based on distance (closer = stronger pull)
        # Use inverse square for natural falloff
        influence = (1 - (dist / impact_radius) ** 2) * orientation_strength

        # Direction toward stadium
        dx = stadium_center.x - point.x
        dy = stadium_center.y - point.y

        # Normalize
        if dist > 0:
            dx /= dist
            dy /= dist

        # Pull the point toward the stadium
        # The pull amount increases as we get closer
        pull_distance = influence * min(dist * 0.3, 50)  # Cap at 50 meters

        new_point = Point(
            x=point.x + dx * pull_distance,
            y=point.y + dy * pull_distance,
        )
        adjusted.append(new_point)

    return adjusted


@dataclass
class RoadSegment:
    """A road segment with its geometry."""

    road_id: UUID
    geometry: list[Point]


class StreetGridImpactCalculator:
    """Calculates and applies stadium impact to street grid."""

    def __init__(self, stadium: StadiumPlacement):
        self.stadium = stadium
        self.impact_radius = calculate_impact_radius(stadium)

    def is_road_affected(self, road_geometry: list[Point]) -> bool:
        """Check if a road is within the stadium's impact zone."""
        if not road_geometry:
            return False

        stadium_center = self.stadium.center

        # Check if any point is within impact radius
        for point in road_geometry:
            if distance(point, stadium_center) <= self.impact_radius:
                return True

        # Also check midpoints of segments for longer roads
        for i in range(len(road_geometry) - 1):
            midpoint = point_along_segment(road_geometry[i], road_geometry[i + 1], 0.5)
            if distance(midpoint, stadium_center) <= self.impact_radius:
                return True

        return False

    def adjust_road(
        self,
        road_id: UUID,
        road_geometry: list[Point],
        orientation_strength: float = 0.8,
    ) -> StreetOrientationResult | None:
        """Adjust a road's geometry to orient toward the stadium.

        Returns None if the road is not affected.
        """
        if not self.is_road_affected(road_geometry):
            return None

        adjusted = compute_street_orientation(road_geometry, self.stadium, orientation_strength)

        return StreetOrientationResult(
            road_id=road_id,
            original_geometry=road_geometry,
            adjusted_geometry=adjusted,
            orientation_strength=orientation_strength,
        )

    def compute_impact(
        self,
        roads: list[RoadSegment],
        orientation_strength: float = 0.8,
    ) -> StreetGridImpactResult:
        """Compute the full street grid impact for a set of roads.

        Args:
            roads: List of road segments to evaluate.
            orientation_strength: How strongly roads orient toward stadium.

        Returns:
            Complete impact result with affected roads.
        """
        affected_roads = []

        for road in roads:
            result = self.adjust_road(road.road_id, road.geometry, orientation_strength)
            if result is not None:
                affected_roads.append(result)

        return StreetGridImpactResult(
            stadium_id=self.stadium.stadium_id,
            impact_radius=self.impact_radius,
            affected_roads=affected_roads,
        )

    def generate_access_roads(self, cardinal_only: bool = True) -> list[dict]:
        """Generate new access roads leading to the stadium.

        Args:
            cardinal_only: If True, only generate roads in 4 cardinal directions.
                          If False, also add diagonal access.

        Returns:
            List of new road definitions to create.
        """
        new_roads = []
        stadium_center = self.stadium.center

        # Define access directions (angle in degrees)
        if cardinal_only:
            directions = [0, 90, 180, 270]  # E, N, W, S
        else:
            directions = [0, 45, 90, 135, 180, 225, 270, 315]

        for angle in directions:
            rad = math.radians(angle)
            # Start from edge of stadium
            start_distance = max(self.stadium.config.width, self.stadium.config.height) / 2 + 20
            end_distance = self.impact_radius

            start = Point(
                x=stadium_center.x + start_distance * math.cos(rad),
                y=stadium_center.y + start_distance * math.sin(rad),
            )
            end = Point(
                x=stadium_center.x + end_distance * math.cos(rad),
                y=stadium_center.y + end_distance * math.sin(rad),
            )

            new_roads.append(
                {
                    "geometry": [start, end],
                    "road_class": "collector",  # Access roads are typically collectors
                    "name": f"Stadium Access {angle}°",
                }
            )

        return new_roads
