"""Stadium module - street grid impact and parking lot generation."""

from city_worker.stadium.grid_impact import (
    StreetGridImpactCalculator,
    calculate_impact_radius,
    compute_street_orientation,
)
from city_worker.stadium.parking import (
    ParkingLotGenerator,
    generate_parking_lots,
)
from city_worker.stadium.types import (
    ParkingLotResult,
    StadiumConfig,
    StadiumPlacement,
    StreetOrientationResult,
)

__all__ = [
    "StreetGridImpactCalculator",
    "compute_street_orientation",
    "calculate_impact_radius",
    "ParkingLotGenerator",
    "generate_parking_lots",
    "StadiumConfig",
    "StadiumPlacement",
    "ParkingLotResult",
    "StreetOrientationResult",
]
