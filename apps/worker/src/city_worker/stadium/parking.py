"""Parking lot generation around stadiums.

Generates parking lots distributed around the stadium based on
capacity requirements and available space.
"""

import math
import random
from dataclasses import dataclass
from uuid import UUID, uuid4

from city_worker.stadium.types import (
    Point,
    ParkingLotResult,
    StadiumPlacement,
)


@dataclass
class ParkingConfig:
    """Configuration for parking lot generation."""

    lot_count: int = 4
    min_distance: float = 50.0  # Minimum distance from stadium edge (meters)
    max_distance: float = 300.0  # Maximum distance from stadium edge (meters)
    spaces_per_seat: float = 0.3  # Ratio of parking spaces to stadium capacity
    min_lot_width: float = 40.0
    max_lot_width: float = 120.0
    min_lot_height: float = 30.0
    max_lot_height: float = 80.0
    space_size: float = 15.0  # Square meters per parking space


def generate_parking_lots(
    stadium: StadiumPlacement,
    config: ParkingConfig | None = None,
    seed: int | None = None,
) -> list[ParkingLotResult]:
    """Generate parking lots around a stadium.

    Args:
        stadium: The stadium placement.
        config: Parking generation config. Uses defaults if None.
        seed: Random seed for reproducible generation.

    Returns:
        List of generated parking lots.
    """
    generator = ParkingLotGenerator(stadium, config, seed)
    return generator.generate()


class ParkingLotGenerator:
    """Generates parking lots distributed around a stadium."""

    def __init__(
        self,
        stadium: StadiumPlacement,
        config: ParkingConfig | None = None,
        seed: int | None = None,
    ):
        self.stadium = stadium
        self.config = config or ParkingConfig()
        self.rng = random.Random(seed)

    def generate(self) -> list[ParkingLotResult]:
        """Generate all parking lots for the stadium."""
        # Calculate total parking spaces needed
        total_spaces = int(self.stadium.config.capacity * self.config.spaces_per_seat)
        spaces_per_lot = total_spaces // self.config.lot_count

        lots = []
        used_positions: list[Point] = []

        # Distribute lots around the stadium
        angle_step = 360.0 / self.config.lot_count
        base_angle = self.rng.uniform(0, angle_step)  # Random starting angle

        for i in range(self.config.lot_count):
            angle = base_angle + i * angle_step
            # Add some randomness to angle
            angle += self.rng.uniform(-15, 15)

            lot = self._generate_lot(
                lot_index=i,
                angle=angle,
                target_spaces=spaces_per_lot,
                used_positions=used_positions,
            )

            if lot is not None:
                lots.append(lot)
                used_positions.append(lot.position)

        return lots

    def _generate_lot(
        self,
        lot_index: int,
        angle: float,
        target_spaces: int,
        used_positions: list[Point],
    ) -> ParkingLotResult | None:
        """Generate a single parking lot at the given angle from stadium."""
        stadium_center = self.stadium.center

        # Calculate distance from stadium center
        # Stadium edge distance
        edge_distance = max(self.stadium.config.width, self.stadium.config.height) / 2

        min_dist = edge_distance + self.config.min_distance
        max_dist = edge_distance + self.config.max_distance

        # Try to find a valid position
        for _ in range(10):  # Max attempts
            distance = self.rng.uniform(min_dist, max_dist)
            rad = math.radians(angle)

            position = Point(
                x=stadium_center.x + distance * math.cos(rad),
                y=stadium_center.y + distance * math.sin(rad),
            )

            # Check if too close to existing lots
            if self._is_position_valid(position, used_positions):
                break
        else:
            # Could not find valid position
            return None

        # Calculate lot dimensions based on target spaces
        area_needed = target_spaces * self.config.space_size

        # Randomize aspect ratio
        aspect = self.rng.uniform(0.5, 2.0)
        width = math.sqrt(area_needed * aspect)
        height = area_needed / width

        # Clamp to min/max sizes
        width = max(self.config.min_lot_width, min(self.config.max_lot_width, width))
        height = max(self.config.min_lot_height, min(self.config.max_lot_height, height))

        # Recalculate actual capacity
        actual_capacity = int((width * height) / self.config.space_size)

        # Orientation points toward stadium
        orientation = angle + 180  # Face toward stadium
        if orientation >= 360:
            orientation -= 360

        return ParkingLotResult(
            lot_id=uuid4(),
            stadium_id=self.stadium.stadium_id,
            position=position,
            width=width,
            height=height,
            capacity=actual_capacity,
            orientation=orientation,
        )

    def _is_position_valid(
        self,
        position: Point,
        used_positions: list[Point],
        min_separation: float = 100.0,
    ) -> bool:
        """Check if a position is far enough from existing lots."""
        for used in used_positions:
            dx = position.x - used.x
            dy = position.y - used.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < min_separation:
                return False
        return True

    def get_total_capacity(self, lots: list[ParkingLotResult]) -> int:
        """Calculate total parking capacity of generated lots."""
        return sum(lot.capacity for lot in lots)

    def get_coverage_area(self, lots: list[ParkingLotResult]) -> float:
        """Calculate total area covered by parking lots."""
        return sum(lot.width * lot.height for lot in lots)
