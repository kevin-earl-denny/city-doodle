"""Compile a WorldBrief into WorldSettings.

This is the single mapping from Claude's semantic brief to engine-facing
settings. It also repairs inconsistencies the model can produce (an island
with water on one side, out-of-range sliders), so the API never stores an
invalid world. Each repair is reported as a warning.
"""

from city_api.brief.schema import WorldBrief
from city_api.schemas.world import WorldSettings

# Engine mask convention: angle 0 = east, 90 = south (screen +y is south).
_COMPASS_DEG: dict[str, float] = {
    "east": 0.0,
    "south_east": 45.0,
    "south": 90.0,
    "south_west": 135.0,
    "west": 180.0,
    "north_west": 225.0,
    "north": 270.0,
    "north_east": 315.0,
}

# River axes are undirected, so they live in [0, 180).
_AXIS_DEG: dict[str, float] = {
    "east_west": 0.0,
    "northwest_southeast": 45.0,
    "north_south": 90.0,
    "northeast_southwest": 135.0,
}

_LANDLOCKED = {"inland", "river_valley"}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compile_brief(brief: WorldBrief) -> tuple[WorldBrief, WorldSettings, list[str]]:
    """Return (repaired brief, settings, warnings)."""
    warnings: list[str] = []
    brief = brief.model_copy(deep=True)

    # ── Water side must agree with the archetype ──
    if brief.archetype == "island" and brief.water_side != "all_around":
        brief.water_side = "all_around"
        warnings.append("Islands have water all around; ignored the single water side.")
    elif brief.archetype in _LANDLOCKED and brief.water_side != "none":
        brief.water_side = "none"
        warnings.append("This land has no sea, so the water side was dropped.")
    elif brief.archetype not in _LANDLOCKED and brief.archetype != "island" and brief.water_side in (
        "none",
        "all_around",
    ):
        # The model gave no usable direction; let the seed choose.
        warnings.append("No clear water direction; the seed will choose one.")

    # ── River consistency ──
    if brief.river.count <= 0 or brief.river.course == "none":
        brief.river.count = 0
        brief.river.course = "none"
        brief.river.axis = None
    brief.river.count = int(_clamp(brief.river.count, 0, 3))

    # ── Sliders ──
    s = brief.sliders
    s.grid_organic = round(_clamp(s.grid_organic, 0.0, 1.0), 3)
    s.sprawl_compact = round(_clamp(s.sprawl_compact, 0.0, 1.0), 3)
    s.transit_car = round(_clamp(s.transit_car, 0.0, 1.0), 3)
    s.historic_modern = round(_clamp(s.historic_modern, 0.0, 1.0), 3)
    s.block_size_meters = int(_clamp(s.block_size_meters, 50, 300))
    s.district_size_meters = int(_clamp(s.district_size_meters, 1000, 6000))

    # ── Names ──
    brief.name = brief.name.strip()[:100] or "Unnamed Harbor"
    brief.name_suggestions = [n.strip()[:100] for n in brief.name_suggestions if n.strip()][:4]

    water_deg = _COMPASS_DEG.get(brief.water_side)
    river_deg = (
        _AXIS_DEG.get(brief.river.axis)
        if brief.archetype == "river_valley" and brief.river.axis
        else None
    )

    settings = WorldSettings(
        geographic_setting=brief.archetype,
        grid_organic=s.grid_organic,
        sprawl_compact=s.sprawl_compact,
        transit_car=s.transit_car,
        historic_modern=s.historic_modern,
        block_size_meters=s.block_size_meters,
        district_size_meters=s.district_size_meters,
        water_direction_deg=water_deg,
        river_axis_deg=river_deg,
        relief=brief.relief,
    )
    return brief, settings, warnings
