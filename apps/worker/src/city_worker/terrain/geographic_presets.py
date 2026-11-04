"""Geographic setting presets for terrain generation (CITY-321).

Maps each GeographicSetting value to TerrainConfig parameter overrides
so different world types produce distinctly different terrain.
"""

from __future__ import annotations

from typing import Any

# Each preset is a dict of TerrainConfig field overrides.
# Omitted fields keep the TerrainConfig defaults.

GEOGRAPHIC_PRESETS: dict[str, dict[str, Any]] = {
    # ── Coastal ─────────────────────────────────────────────────
    # Default balanced coastal city.  Moderate water, beaches,
    # barrier islands possible on gentle slopes.
    "coastal": {
        "water_level": 0.35,
        "beach_enabled": True,
        "bay_enabled": True,
        "barrier_islands_enabled": True,
    },
    # ── Bay / Harbor ────────────────────────────────────────────
    # Protected natural harbor with prominent bay (shaped by
    # bay_harbor_mask).  Lower enclosure and area thresholds so more
    # of the harbor's coves are detected as bays.
    "bay_harbor": {
        "water_level": 0.38,
        "beach_enabled": True,
        "beach_height_band": 0.02,
        "bay_enabled": True,
        "bay_min_concavity_angle": 25.0,
        "bay_min_area": 16.0,
        "bay_max_depth_ratio": 5.0,
        "bay_harbor_min_area": 2400.0,
        "barrier_islands_enabled": False,
    },
    # ── River Valley ────────────────────────────────────────────
    # City built along a major river.  Lower water level exposes
    # more land, but rivers form more readily with a lower flow
    # threshold and longer minimum length.
    "river_valley": {
        "water_level": 0.28,
        "min_river_length": 6,
        "beach_enabled": False,
        "bay_enabled": False,
        "barrier_islands_enabled": False,
        "height_scale": 0.012,
        "coastline_smoothing": 2,
    },
    # ── Lakefront ───────────────────────────────────────────────
    # City on the shore of a large inland lake.  Moderate water
    # level, no ocean-style features (barrier islands, bays).
    "lakefront": {
        "water_level": 0.34,
        "beach_enabled": True,
        "beach_height_band": 0.015,
        "beach_slope_max": 0.10,
        "bay_enabled": False,
        "barrier_islands_enabled": False,
        "min_river_length": 8,
        "max_lakes": 8,  # CITY-490: lakefront cities should have more lakes
    },
    # ── Inland ──────────────────────────────────────────────────
    # No coastline.  Very low water level so almost all terrain is
    # above water.  Water features (rivers/lakes) are suppressed
    # because water_level < WATER_LEVEL_SUPPRESS_THRESHOLD (CITY-551).
    "inland": {
        "water_level": 0.15,
        "beach_enabled": False,
        "bay_enabled": False,
        "barrier_islands_enabled": False,
        "min_river_length": 12,
        "height_scale": 0.008,
    },
    # ── Island ──────────────────────────────────────────────────
    # City on an island surrounded by water.  Higher water level
    # so more of the terrain is submerged, creating an island feel.
    "island": {
        "water_level": 0.42,
        "beach_enabled": True,
        "beach_height_band": 0.03,
        "beach_width_multiplier": 1.3,
        "bay_enabled": True,
        "bay_min_concavity_angle": 35.0,
        "barrier_islands_enabled": True,
        "barrier_island_offset_min": 6.0,
        "barrier_island_offset_max": 12.0,
        "coastline_smoothing": 4,
    },
    # ── Peninsula ───────────────────────────────────────────────
    # Land mass jutting into water.  Water level between coastal
    # and island — enough to create water on multiple sides.
    "peninsula": {
        "water_level": 0.40,
        "beach_enabled": True,
        "beach_height_band": 0.02,
        "bay_enabled": True,
        "bay_min_concavity_angle": 40.0,
        "barrier_islands_enabled": False,
        "coastline_smoothing": 4,
    },
    # ── Delta ───────────────────────────────────────────────────
    # River delta / wetlands.  Low-lying terrain with many river
    # channels.  Water level is moderate but the land is very flat
    # (smaller height scale) so rivers spread out.
    "delta": {
        "water_level": 0.33,
        "height_scale": 0.006,
        "height_persistence": 0.45,
        "min_river_length": 4,
        "beach_enabled": True,
        "beach_height_band": 0.03,
        "beach_slope_max": 0.15,
        "bay_enabled": True,
        "bay_min_concavity_angle": 35.0,
        "bay_river_mouth_factor": 3.0,
        "barrier_islands_enabled": True,
        "coastline_smoothing": 2,
    },
}


def get_preset_overrides(geographic_setting: str) -> dict[str, Any]:
    """Return TerrainConfig overrides for the given geographic setting.

    Falls back to "coastal" if the setting is unrecognised.
    """
    return dict(GEOGRAPHIC_PRESETS.get(geographic_setting, GEOGRAPHIC_PRESETS["coastal"]))


# ── Seed-based variation (CITY-325) ────────────────────────────

# Each key maps to (min_value, max_value, jitter_fraction).
# jitter_fraction is the ± proportion of the base value that the seed
# can shift. E.g. 0.15 means the final value can be base ± 15%.
_VARIATION_RANGES: dict[str, tuple[float, float, float]] = {
    "water_level": (0.05, 0.65, 0.12),
    "height_scale": (0.003, 0.02, 0.20),  # CITY-650: ~0.8-5 cycles/tile
    "height_persistence": (0.35, 0.60, 0.10),
    "height_lacunarity": (1.8, 2.3, 0.08),
    "coastline_smoothing": (1, 6, 0.30),
    "beach_height_band": (0.01, 0.04, 0.15),
    "beach_slope_max": (0.06, 0.18, 0.15),
    "bay_min_concavity_angle": (20.0, 60.0, 0.15),
    "bay_min_area": (12.0, 80.0, 0.20),  # CITY-682: 3-20 cells
    "min_river_length": (3, 15, 0.25),
}


def _seeded_uniform(seed: int, index: int) -> float:
    """Deterministic pseudo-random float in [0, 1) from seed + index.

    Uses a simple LCG-style hash so we stay dependency-free.
    """
    h = ((seed * 2654435761) ^ (index * 340573321)) & 0xFFFFFFFF
    h = ((h >> 16) ^ h) * 0x45D9F3B & 0xFFFFFFFF
    h = ((h >> 16) ^ h) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def apply_seed_variation(geographic_setting: str, seed: int) -> dict[str, Any]:
    """Apply deterministic seed-based jitter to a geographic preset.

    This ensures that two worlds with the same geographic setting but
    different seeds still produce noticeably different terrain while
    staying within the archetype's character.
    """
    base = get_preset_overrides(geographic_setting)

    for i, (key, (lo, hi, jitter)) in enumerate(_VARIATION_RANGES.items()):
        if key not in base:
            continue
        base_val = float(base[key])
        # Jitter: shift ± jitter * base_val
        rand = _seeded_uniform(seed, i)  # [0, 1)
        offset = (rand * 2 - 1) * jitter * base_val  # ±jitter%
        varied = base_val + offset
        # Clamp to allowed range
        varied = max(lo, min(hi, varied))
        # Preserve int types where applicable
        if isinstance(base[key], int):
            base[key] = int(round(varied))
        else:
            base[key] = round(varied, 6)

    return base
