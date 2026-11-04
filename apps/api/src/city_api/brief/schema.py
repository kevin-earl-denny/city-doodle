"""World Brief schema: the structured output Claude returns for a terrain prompt.

The brief is deliberately *semantic* (compass directions, relief classes,
growth-story ids) rather than raw TerrainConfig numbers. Terrain internals
such as height_scale are being retuned, and the compiler in
``city_api.brief.compiler`` is the only place that maps brief → settings.

Numeric bounds are not expressed in the schema: structured outputs don't
enforce min/max, so the compiler clamps instead.
"""

from typing import Literal

from pydantic import BaseModel, Field

from city_api.schemas.world import GeographicSetting, WorldSettings

Compass = Literal[
    "north",
    "north_east",
    "east",
    "south_east",
    "south",
    "south_west",
    "west",
    "north_west",
]
WaterSide = Literal[
    "north",
    "north_east",
    "east",
    "south_east",
    "south",
    "south_west",
    "west",
    "north_west",
    "all_around",
    "none",
]
RiverCourse = Literal["none", "straight", "meandering", "braided"]
RiverAxis = Literal["north_south", "east_west", "northeast_southwest", "northwest_southeast"]
Relief = Literal["flat", "rolling", "hilly", "mountainous"]
Coast = Literal["smooth", "varied", "rugged", "none"]
GrowthStory = Literal[
    "medieval_tangle",
    "boomtown_grid",
    "grand_boulevards",
    "hill_town",
    "streetcar_suburb",
    "motor_sprawl",
]


class RiverSpec(BaseModel):
    count: int = Field(description="Number of notable rivers, 0-3")
    course: RiverCourse
    axis: RiverAxis | None = Field(
        description="Undirected line the main river follows across the map; null if no river"
    )


class CitySliders(BaseModel):
    grid_organic: float = Field(description="0 = strict grid, 1 = fully organic")
    sprawl_compact: float = Field(description="0 = sprawling suburbs, 1 = dense core")
    transit_car: float = Field(description="0 = transit-oriented, 1 = car-dependent")
    historic_modern: float = Field(description="0 = historic fabric kept, 1 = modern rebuild")
    block_size_meters: int = Field(description="Typical block edge, 50-300")
    district_size_meters: int = Field(description="Typical district edge, 1000-6000")


class LegendLines(BaseModel):
    """Short human phrases shown as the map legend. Each one is 3–8 words."""

    water: str = Field(description='e.g. "Bay opens to the south-east"')
    river: str = Field(description='e.g. "One river, winding in from the north"')
    ground: str = Field(description='e.g. "Hilly west bank, flat east bank"')
    streets: str = Field(description='e.g. "Hill Town, then Boomtown Grid"')


class WorldBrief(BaseModel):
    archetype: GeographicSetting
    water_side: WaterSide
    river: RiverSpec
    relief: Relief
    coast: Coast
    growth_story: GrowthStory
    sliders: CitySliders
    name: str = Field(description="An original, evocative city name; never a real city's name")
    name_suggestions: list[str] = Field(description="Exactly 4 alternative original names")
    founding_year: int | None = Field(description="Plausible founding year, or null")
    founding_story: str = Field(description="2-3 sentences in a warm surveyor's voice, under 320 chars")
    feels_like: list[str] = Field(description="1-3 real cities this evokes")
    legend: LegendLines
    unsupported: list[str] = Field(
        description="Things the user asked for that the engine can't draw yet; empty if none"
    )


# ── API request / response ──────────────────────────────────────────────


class BriefRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=600)
    previous: WorldBrief | None = Field(
        default=None, description="The brief being refined, if any"
    )
    refinement: str | None = Field(
        default=None,
        max_length=300,
        description='A follow-up change request, such as "put the river on the east side"',
    )


class BriefResponse(BaseModel):
    brief: WorldBrief
    settings: WorldSettings
    warnings: list[str] = Field(default_factory=list)
