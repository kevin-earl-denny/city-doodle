"""Type definitions for growth simulation."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class GrowthConfig:
    """Configuration for a growth simulation run."""

    world_id: UUID
    years: int = 1

    # Growth rate multipliers per district type (annual %)
    infill_rates: dict[str, float] = field(
        default_factory=lambda: {
            "residential": 0.03,
            "downtown": 0.05,
            "commercial": 0.04,
            "industrial": 0.02,
            "hospital": 0.01,
            "university": 0.02,
            "k12": 0.01,
            "park": 0.005,
            "airport": 0.005,
        }
    )

    # Expansion rate: fraction of current area added per year
    expansion_rate: float = 0.02

    # POI generation thresholds (density above which new POIs spawn)
    poi_density_threshold: float = 4.0

    # Maximum density cap by district type
    max_density: dict[str, float] = field(
        default_factory=lambda: {
            "residential": 8.0,
            "downtown": 10.0,
            "commercial": 8.0,
            "industrial": 4.0,
            "hospital": 4.0,
            "university": 5.0,
            "k12": 3.0,
            "park": 0.5,
            "airport": 1.0,
        }
    )


@dataclass
class ChangeEntry:
    """A single change in the growth changelog."""

    action: str  # "infill", "expand", "new_road", "new_poi"
    entity_type: str  # "district", "road_node", "road_edge", "poi"
    entity_id: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class GrowthChangelog:
    """Structured changelog from a growth simulation run."""

    world_id: UUID
    years_simulated: int
    entries: list[ChangeEntry] = field(default_factory=list)

    # Summary counters
    districts_infilled: int = 0
    districts_expanded: int = 0
    roads_added: int = 0
    pois_added: int = 0
    districts_skipped_historic: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "world_id": str(self.world_id),
            "years_simulated": self.years_simulated,
            "summary": {
                "districts_infilled": self.districts_infilled,
                "districts_expanded": self.districts_expanded,
                "roads_added": self.roads_added,
                "pois_added": self.pois_added,
                "districts_skipped_historic": self.districts_skipped_historic,
            },
            "entries": [
                {
                    "action": e.action,
                    "entity_type": e.entity_type,
                    "entity_id": e.entity_id,
                    "details": e.details,
                }
                for e in self.entries
            ],
        }
