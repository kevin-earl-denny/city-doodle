"""Geographic masks for terrain generation (CITY-386).

Each geographic setting can define a mask function that modifies the
heightfield after noise generation but before erosion and feature
extraction.  This allows different world types to have fundamentally
different landform shapes rather than just parameter tweaks.

Mask functions receive the raw heightfield (normalized to [0, 1]) and
a MaskContext with tile position and generation parameters.  They return
a modified heightfield, also in [0, 1].

Individual mask implementations are added by follow-up tickets:
  CITY-387  island      – radial falloff
  CITY-388  inland      – minimal water
  CITY-390  peninsula   – directional falloff
  CITY-391  river_valley – deliberate channel
  CITY-392  bay_harbor  – deliberate indentation
  CITY-393  delta       – fan-shaped river mouth
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from opensimplex import OpenSimplex

# ── Helpers ──────────────────────────────────────────────────────


def _seeded_hash(seed: int, index: int) -> float:
    """Deterministic float in [0, 1) from *seed* + *index*."""
    h = ((seed * 2654435761) ^ (index * 340573321)) & 0xFFFFFFFF
    h = ((h >> 16) ^ h) * 0x45D9F3B & 0xFFFFFFFF
    h = ((h >> 16) ^ h) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def _smoothstep(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Hermite smoothstep: 3t^2 - 2t^3, clamped to [0, 1]."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _angle_noise(angles: NDArray[np.float64], seed: int, octaves: int = 4) -> NDArray[np.float64]:
    """Deterministic noise keyed on angle for organic boundary perturbation.

    Returns values roughly in [-1, 1].
    """
    result = np.zeros_like(angles)
    amplitude = 1.0
    total_amp = 0.0
    for i in range(octaves):
        phase = _seeded_hash(seed, i + 100) * 2.0 * math.pi
        freq = float(i + 2)
        result += amplitude * np.sin(angles * freq + phase)
        total_amp += amplitude
        amplitude *= 0.5
    return result / total_amp


@dataclass(frozen=True)
class MaskContext:
    """Context passed to geographic mask functions.

    Attributes:
        tx: Tile x coordinate (1 = world center column).
        ty: Tile y coordinate (1 = world center row).
        tile_size: Tile size in world units.
        resolution: Number of height samples per tile edge.
        seed: World seed for deterministic randomness.
        water_level: The world's (seed-varied) water level, for masks that
            place land and sea explicitly. None when the caller doesn't know it.
    """

    tx: int
    ty: int
    tile_size: float
    resolution: int
    seed: int
    water_level: float | None = None


# Type alias for mask functions.
MaskFn = Callable[[NDArray[np.float64], MaskContext], NDArray[np.float64]]


# ── Built-in masks ───────────────────────────────────────────────


def identity_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """No-op mask — returns the heightfield unchanged.

    Used as the default for geographic settings that don't need
    deliberate shaping (e.g. "coastal") or as a placeholder until
    a dedicated mask is implemented.
    """
    return heightfield


def inland_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """Height-floor mask for inland worlds (CITY-388, CITY-551).

    Compresses the height range upward so all terrain sits above
    the water level.  With the inland preset's water_level of ~0.15,
    the floor of 0.22 ensures no standing water or rivers form.

    Mapping: h -> floor + h * (1 - floor)
      [0, 1] -> [0.22, 1.0]
    """
    floor = 0.22
    return floor + heightfield * (1.0 - floor)


def island_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """Organic island mask for island worlds (CITY-387, CITY-545, CITY-648).

    Real islands are rarely round: they're elongated along a volcanic or
    tectonic spine, lobed where several peaks merge, and have fractal
    coastlines with peninsulas and coves.  The shape here is built from:

      1. A curved spine of 2-4 elliptical lobes (seed-driven count,
         orientation, elongation and sizes) combined with a soft union.
      2. Domain warping of the lobe field by low-frequency 2D noise, so
         the outline bends into headlands and bays instead of staying
         star-shaped around the center.
      3. Additive 2D fBm along the shoreline for fine coastal detail.

    Everything is evaluated in world coordinates, so the shape is
    seamless across the 3x3 tiles.

    Inside the island the heightfield is lifted above the island preset's
    water level (~0.42), so interior noise dips no longer turn into
    puddles; terrain height rises toward the spine like a real island.
    """
    res = ctx.resolution
    ts = ctx.tile_size
    seed = ctx.seed

    step = ts / res
    xs = ctx.tx * ts + np.arange(res, dtype=np.float64) * step
    ys = ctx.ty * ts + np.arange(res, dtype=np.float64) * step
    xx, yy = np.meshgrid(xs, ys)

    # ── Domain warp: bend the whole outline ──
    warp_freq = 1.0 / (ts * 1.1)
    warp_amp = ts * 0.40
    warp_x = _fbm_grid(xs, ys, seed + 1, warp_freq, octaves=2)
    warp_y = _fbm_grid(xs, ys, seed + 2, warp_freq, octaves=2)
    wx = xx + warp_x * warp_amp
    wy = yy + warp_y * warp_amp

    # ── Spine of lobes ──
    cx = cy = ts * 1.5  # world center (middle of tile 1, 1)
    spine_angle = _seeded_hash(seed, 1) * math.pi
    spine_len = ts * (1.0 + _seeded_hash(seed, 2) * 0.7)  # 1.0 - 1.7 tiles
    spine_bend = (_seeded_hash(seed, 3) - 0.5) * ts * 0.8
    num_lobes = 2 + int(_seeded_hash(seed, 4) * 3)  # 2 - 4
    ax_x, ax_y = math.cos(spine_angle), math.sin(spine_angle)
    perp_x, perp_y = -ax_y, ax_x

    shape = np.zeros_like(xx)
    for i in range(num_lobes):
        # Position along the spine in [-0.5, 0.5] with jitter
        u = (i / max(num_lobes - 1, 1)) - 0.5
        u += (_seeded_hash(seed, 40 + i) - 0.5) * 0.25
        bend = spine_bend * 4.0 * u * u  # arc through the world center
        lx = cx + ax_x * u * spine_len + perp_x * bend
        ly = cy + ax_y * u * spine_len + perp_y * bend
        # Lobes are ellipses stretched along the spine
        r_long = ts * (0.58 + _seeded_hash(seed, 50 + i) * 0.36)
        r_short = r_long * (0.70 + _seeded_hash(seed, 60 + i) * 0.30)
        dx = wx - lx
        dy = wy - ly
        along = (dx * ax_x + dy * ax_y) / r_long
        across = (dx * perp_x + dy * perp_y) / r_short
        lobe = np.exp(-(along * along + across * across))
        # Soft union: 1 - prod(1 - lobe) keeps overlaps from spiking
        shape = 1.0 - (1.0 - shape) * (1.0 - lobe)

    # Unwarped core lobe guarantees the world center (where the city
    # starts) is always land, even if warping pulls the spine aside.
    core_r = ts * 0.30
    core = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (core_r * core_r))
    shape = 1.0 - (1.0 - shape) * (1.0 - core)

    # ── Satellite islets (~35% of worlds) ──
    if _seeded_hash(seed, 5) > 0.65:
        for i in range(1 + int(_seeded_hash(seed, 6) * 3)):  # 1 - 3
            ang = _seeded_hash(seed, 10 + i) * 2.0 * math.pi
            dist = ts * (1.05 + _seeded_hash(seed, 20 + i) * 0.25)
            sx = cx + dist * math.cos(ang)
            sy = cy + dist * math.sin(ang)
            sr = ts * (0.07 + _seeded_hash(seed, 30 + i) * 0.08)
            d2 = ((wx - sx) ** 2 + (wy - sy) ** 2) / (sr * sr)
            shape = 1.0 - (1.0 - shape) * (1.0 - np.exp(-d2))

    # ── Coastline detail ──
    # Mid-frequency fBm carves coves and headlands; the terrain
    # heightfield adds fine fractal roughness to the shoreline.
    coast_noise = _fbm_grid(xs, ys, seed + 3, 1.0 / (ts * 0.30), octaves=3)
    field = shape + coast_noise * 0.28 + (heightfield - 0.5) * 0.20

    # Fade the field out near the 3x3 world boundary so the island is
    # always surrounded by open water, however far a lobe reaches.
    margin = ts * 0.35
    edge_dist = np.minimum.reduce([xx, yy, 3.0 * ts - xx, 3.0 * ts - yy])
    field = field * _smoothstep(edge_dist / margin)

    # Land where field > threshold; narrow band so the coast is crisp
    threshold = 0.42
    band = 0.10
    land = _smoothstep((field - (threshold - band)) / (2.0 * band))

    # ── Interior elevation ──
    # Lift land above water (floor 0.5 > preset water_level ~0.42 +
    # jitter).  Keep a low coastal plain where the city can grow and
    # raise the terrain toward the spine so the high ground sits inland.
    floor = 0.5
    inland = np.clip((field - threshold) / 0.5, 0.0, 1.0)
    relief = 0.35 + 0.65 * inland
    land_height = floor + (1.0 - floor) * (0.5 * heightfield * relief + 0.5 * inland**1.5)

    # Ocean floor keeps a little noise but always stays below the
    # minimum island water level (~0.37), so no stray islets appear.
    sea_height = heightfield * 0.3
    return sea_height + (land_height - sea_height) * land


def _fbm_grid(
    xs: NDArray[np.float64],
    ys: NDArray[np.float64],
    seed: int,
    frequency: float,
    octaves: int = 4,
) -> NDArray[np.float64]:
    """2D fBm over the world-coordinate grid, roughly in [-1, 1].

    opensimplex's noise2array costs ~0.1s per 128x128 call, so the noise
    is sampled on a coarse grid (4 samples per cycle of the finest
    octave) and bilinearly upsampled.  The fields used here are smooth,
    so this is visually identical at a fraction of the cost.
    """
    span = max(xs[-1] - xs[0], ys[-1] - ys[0])
    finest_cycles = frequency * (2 ** (octaves - 1)) * span
    n = int(min(max(len(xs), len(ys)), math.ceil(finest_cycles * 4) + 2))
    cxs = np.linspace(xs[0], xs[-1], n)
    cys = np.linspace(ys[0], ys[-1], n)

    simplex = OpenSimplex(seed=seed & 0x7FFFFFFF)
    total = np.zeros((n, n), dtype=np.float64)
    amp = 1.0
    norm = 0.0
    f = frequency
    for _ in range(octaves):
        total += amp * simplex.noise2array(cxs * f, cys * f)
        norm += amp
        amp *= 0.5
        f *= 2.0
    coarse = total / norm
    if n == len(xs) and n == len(ys):
        return coarse
    rows = np.stack([np.interp(xs, cxs, row) for row in coarse])
    return np.stack([np.interp(ys, cys, col) for col in rows.T], axis=1)


def peninsula_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """Directional land-protrusion mask for peninsula worlds (CITY-390).

    Creates a finger of land jutting into water.  The peninsula axis
    direction is seed-deterministic.  The landmass is wide at the
    "mainland" end and tapers toward the tip, with water on both sides
    and at the tip.
    """
    res = ctx.resolution
    ts = ctx.tile_size

    # World center (middle of tile 1,1)
    cx = ts * 1.5
    cy = ts * 1.5

    # Seed-based direction the peninsula points toward
    direction = _seeded_hash(ctx.seed, 10) * 2.0 * math.pi

    # Peninsula geometry (in rotated coordinates along the axis)
    mainland_u = -ts * 0.8  # Where the mainland starts (behind center)
    tip_u = ts * 1.0  # Where the tip ends (past center)
    base_half_w = ts * 0.9  # Half-width at mainland
    tip_half_w = ts * 0.12  # Half-width at tip
    tip_falloff = ts * 0.25  # Falloff distance beyond the tip

    # Build world-coordinate grids
    step = ts / res
    xs = ctx.tx * ts + np.arange(res, dtype=np.float64) * step
    ys = ctx.ty * ts + np.arange(res, dtype=np.float64) * step
    xx, yy = np.meshgrid(xs, ys)

    dx = xx - cx
    dy = yy - cy

    # Rotate into peninsula-aligned coordinate system
    cos_d, sin_d = math.cos(direction), math.sin(direction)
    u = dx * cos_d + dy * sin_d  # Along axis (mainland -> tip)
    v = -dx * sin_d + dy * cos_d  # Perpendicular

    # Interpolate half-width along the axis
    t_along = np.clip((u - mainland_u) / (tip_u - mainland_u), 0.0, 1.0)
    half_width = base_half_w + (tip_half_w - base_half_w) * t_along

    # Perpendicular falloff: 1.0 on axis, drops to 0 at edges
    v_norm = np.abs(v) / np.maximum(half_width, 1e-10)
    perp_mask = 1.0 - _smoothstep(v_norm)

    # Along-axis falloff: land from mainland to tip, then fall off
    along_mask = np.ones_like(u)
    # Beyond the tip: smooth falloff
    beyond_tip = u > tip_u
    along_mask[beyond_tip] = 1.0 - _smoothstep((u[beyond_tip] - tip_u) / tip_falloff).astype(
        np.float64
    )
    # Behind mainland: always land (continent continues)
    # (along_mask already 1.0 there -- no change needed)

    # Combine
    mask = perp_mask * along_mask

    # Noise perturbation for organic coastline
    angles = np.arctan2(dy, dx)
    noise = _angle_noise(angles, ctx.seed + 500)
    mask = mask + noise * 0.04
    mask = np.clip(mask, 0.0, 1.0)

    return heightfield * mask


def river_valley_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """Meandering valley channel mask for river-valley worlds (CITY-391).

    Carves a deliberate river valley through the terrain.  The valley
    has a meandering centerline, a narrow deep river channel, and
    wider valley slopes on either side.  Direction and meander phase
    are seed-deterministic.

    The mask *subtracts* height near the river rather than multiplying,
    so terrain far from the river keeps its full noise-derived variation
    while the valley itself is depressed below the water level.
    """
    res = ctx.resolution
    ts = ctx.tile_size

    # World center (middle of tile 1,1)
    cx = ts * 1.5
    cy = ts * 1.5

    # Seed-based river direction (0 to pi -- half circle is sufficient)
    direction = _seeded_hash(ctx.seed, 20) * math.pi

    # Meander parameters
    meander_amp = ts * 0.15
    meander_freq = 2.0 * math.pi / (ts * 2.0)
    meander_phase = _seeded_hash(ctx.seed, 21) * 2.0 * math.pi
    # Second harmonic for more natural meanders
    meander_amp2 = ts * 0.06
    meander_freq2 = meander_freq * 2.3
    meander_phase2 = _seeded_hash(ctx.seed, 22) * 2.0 * math.pi

    # Valley geometry (CITY-646). The channel and the valley walls are
    # carved separately: only the channel drops below water_level (~0.28
    # against land heights near 0.5), while the walls get a shallow
    # depression that reads as low ground but stays dry. A single deep
    # profile flooded the whole inner valley into a ~75px band.
    river_half_w = ts * 0.03  # River channel half-width
    bank_w = ts * 0.015  # Width of the steep channel bank
    valley_half_w = ts * 0.25  # Full valley half-width
    channel_depression = 0.4  # Height reduction at the river bottom
    wall_depression = 0.1  # Height reduction across the valley floor

    # Build world-coordinate grids
    step = ts / res
    xs = ctx.tx * ts + np.arange(res, dtype=np.float64) * step
    ys = ctx.ty * ts + np.arange(res, dtype=np.float64) * step
    xx, yy = np.meshgrid(xs, ys)

    dx = xx - cx
    dy = yy - cy

    # Rotate to river-aligned coordinates
    cos_d, sin_d = math.cos(direction), math.sin(direction)
    u = dx * cos_d + dy * sin_d  # Along river
    v = -dx * sin_d + dy * cos_d  # Perpendicular

    # Meandering centerline offset
    meander = meander_amp * np.sin(u * meander_freq + meander_phase) + meander_amp2 * np.sin(
        u * meander_freq2 + meander_phase2
    )

    # Perpendicular distance from the meandering centerline
    dist = np.abs(v - meander)

    # Valley profile: sum of two smoothstep falloffs
    #   1. Channel: full depression inside river_half_w, gone by river_half_w + bank_w
    #   2. Valley walls: shallow depression easing out to valley_half_w
    channel_t = np.clip((dist - river_half_w) / bank_w, 0.0, 1.0)
    wall_t = np.clip(dist / valley_half_w, 0.0, 1.0)
    depression = channel_depression * (1.0 - _smoothstep(channel_t)) + wall_depression * (
        1.0 - _smoothstep(wall_t)
    )

    return heightfield - depression


def bay_harbor_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """Concave bay indentation mask for bay/harbor worlds (CITY-392).

    Creates a protected natural harbor by:
      1. Applying a directional gradient so one side is ocean, the
         other is land (the coastline).
      2. Carving a U-shaped bay depression into the land side so
         water wraps around three sides of the city center.

    The ocean direction is seed-deterministic.
    """
    res = ctx.resolution
    ts = ctx.tile_size
    cx, cy = ts * 1.5, ts * 1.5

    # Seed-based ocean direction
    ocean_dir = _seeded_hash(ctx.seed, 30) * 2.0 * math.pi
    cos_d, sin_d = math.cos(ocean_dir), math.sin(ocean_dir)

    # Build world-coordinate grids
    step = ts / res
    xs = ctx.tx * ts + np.arange(res, dtype=np.float64) * step
    ys = ctx.ty * ts + np.arange(res, dtype=np.float64) * step
    xx, yy = np.meshgrid(xs, ys)
    dx, dy = xx - cx, yy - cy

    # Rotated coordinates: u = toward ocean, v = along coast
    u = dx * cos_d + dy * sin_d
    v = -dx * sin_d + dy * cos_d

    # ── Step 1: Directional gradient ──
    # Bias heights so the ocean side is lower and land side is higher.
    # This creates a clear coastline running roughly through the center.
    grad_scale = ts * 1.5
    gradient = np.clip(0.5 - u / grad_scale * 0.4, 0.3, 1.0)
    result = heightfield * gradient

    # ── Step 2: Bay carve ──
    # Semi-elliptical depression opening toward the ocean.
    bay_depth = ts * 0.40  # How far the bay extends into the land
    bay_half_w = ts * 0.30  # Half-width of the bay opening
    bay_max_dep = 0.30  # Maximum height depression inside the bay

    # Width narrows linearly from opening (u ≈ 0) to back (u = -bay_depth)
    t_bay = np.clip((u + bay_depth) / bay_depth, 0.0, 1.0)
    width_at_u = bay_half_w * t_bay

    # Inside the bay region?
    in_bay_u = (u > -bay_depth) & (u < ts * 0.05)
    in_bay_v = np.abs(v) < width_at_u
    in_bay = in_bay_u & in_bay_v

    # Smooth depression: strongest at center of bay, fading at walls
    safe_width = np.maximum(width_at_u, 1e-10)
    v_norm = np.where(
        width_at_u > 1e-10,
        np.abs(v) / safe_width,
        np.ones_like(v),
    )
    depression = np.where(
        in_bay,
        bay_max_dep * (1.0 - _smoothstep(v_norm)) * t_bay,
        0.0,
    )

    return result - depression


def coastal_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """Directional gradient mask for coastal worlds (CITY-575).

    Creates an organic coastline by applying a directional gradient
    (ocean on one side, land on the other) with multi-octave noise
    perturbation for natural-looking bays and headlands.

    The ocean direction is seed-deterministic, producing visually
    distinct coastline shapes for different seeds.
    """
    res = ctx.resolution
    ts = ctx.tile_size
    cx, cy = ts * 1.5, ts * 1.5

    # Seed-based ocean direction (one of 4 cardinal-ish directions
    # with some randomness so it isn't always perfectly axis-aligned)
    base_dir = int(_seeded_hash(ctx.seed, 60) * 4)  # 0-3
    dir_offsets = [0.0, math.pi * 0.5, math.pi, math.pi * 1.5]
    ocean_dir = dir_offsets[base_dir] + (_seeded_hash(ctx.seed, 61) - 0.5) * 0.4
    cos_d, sin_d = math.cos(ocean_dir), math.sin(ocean_dir)

    # Build world-coordinate grids
    step = ts / res
    xs = ctx.tx * ts + np.arange(res, dtype=np.float64) * step
    ys = ctx.ty * ts + np.arange(res, dtype=np.float64) * step
    xx, yy = np.meshgrid(xs, ys)
    dx, dy = xx - cx, yy - cy

    # Project onto ocean direction: u = toward ocean
    u = dx * cos_d + dy * sin_d

    # ── Step 1: Directional gradient ──
    # Smoothly transitions from low (ocean) to high (land).
    # The coastline sits roughly at u=0 (world center).
    grad_scale = ts * 1.4
    gradient = np.clip(0.5 - u / grad_scale * 0.5, 0.15, 1.0)

    # ── Step 2: Coastline noise for organic shape ──
    # Use angle-based noise along the coast direction to create
    # bays and headlands rather than a straight line.
    v = -dx * sin_d + dy * cos_d  # Along-coast coordinate
    coast_angles = np.arctan2(v, np.full_like(v, ts))  # Pseudo-angle along coast

    # Multi-frequency noise for varied coastline features
    noise = _angle_noise(coast_angles, ctx.seed + 700, octaves=5)

    # Additional low-frequency noise for major bay features
    bay_phase = _seeded_hash(ctx.seed, 62) * 2.0 * math.pi
    bay_noise = 0.4 * np.sin(v / ts * 2.5 * math.pi + bay_phase)
    bay_noise += 0.2 * np.sin(v / ts * 4.0 * math.pi + bay_phase * 1.7)

    # Combine: perturb the gradient transition zone
    perturbation = noise * 0.12 + bay_noise * 0.08
    gradient = gradient + perturbation
    gradient = np.clip(gradient, 0.0, 1.0)

    return heightfield * gradient


def lakefront_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """Glacial-lake shore mask for lakefront worlds (CITY-447).

    Creates a large freshwater lake on one edge of the world by
    depressing terrain in a smooth elliptical bowl.  The lake edge
    direction is seed-deterministic, and the shoreline is perturbed
    with angle-dependent noise for an organic, glacial-lake feel.

    The lake covers roughly 20-30% of the world area and sits
    below the lakefront preset's water_level (0.34), so lake
    extraction will fill it with water.
    """
    res = ctx.resolution
    ts = ctx.tile_size
    cx, cy = ts * 1.5, ts * 1.5

    # Seed-based lake direction: which edge the lake is on.
    # Pick one of 4 cardinal-ish directions with some randomness.
    base_dir = int(_seeded_hash(ctx.seed, 70) * 4)  # 0-3
    dir_offsets = [0.0, math.pi * 0.5, math.pi, math.pi * 1.5]
    lake_dir = dir_offsets[base_dir] + (_seeded_hash(ctx.seed, 71) - 0.5) * 0.3
    cos_d, sin_d = math.cos(lake_dir), math.sin(lake_dir)

    # Build world-coordinate grids
    step = ts / res
    xs = ctx.tx * ts + np.arange(res, dtype=np.float64) * step
    ys = ctx.ty * ts + np.arange(res, dtype=np.float64) * step
    xx, yy = np.meshgrid(xs, ys)
    dx, dy = xx - cx, yy - cy

    # Rotated coordinates: u = toward lake center, v = along shore
    u = dx * cos_d + dy * sin_d
    v = -dx * sin_d + dy * cos_d

    # Lake geometry: an elliptical depression centered beyond the
    # tile edge.  The lake center sits outside the world so only
    # one edge has the lake shore.
    lake_center_u = ts * 1.1  # Lake center past the world edge
    lake_radius_u = ts * 1.2  # Radial extent along u (into the world)
    lake_radius_v = ts * (0.9 + _seeded_hash(ctx.seed, 72) * 0.4)  # 0.9-1.3

    # Elliptical distance from lake center
    du = u - lake_center_u
    safe_ru = max(lake_radius_u, 1e-10)
    safe_rv = max(lake_radius_v, 1e-10)
    ellipse_dist = np.sqrt((du / safe_ru) ** 2 + (v / safe_rv) ** 2)

    # Shoreline noise for organic boundary
    shore_angles = np.arctan2(v, du)
    noise = _angle_noise(shore_angles, ctx.seed + 800, octaves=5)

    # Perturb the ellipse boundary
    perturbed_dist = ellipse_dist + noise * 0.08

    # Transition band: smooth falloff from lake floor to highlands
    shore_inner = 0.75  # Inside this = full lake depth
    shore_outer = 1.05  # Outside this = no depression
    t = np.clip(
        (perturbed_dist - shore_inner) / max(shore_outer - shore_inner, 1e-10),
        0.0,
        1.0,
    )
    # depression_strength: 1.0 at lake floor, 0.0 at highlands
    depression_strength = 1.0 - _smoothstep(t)

    # Maximum depth of the depression — enough to push terrain
    # well below the lakefront water_level of 0.34
    max_depression = 0.45

    return heightfield - max_depression * depression_strength


def delta_mask(heightfield: NDArray[np.float64], ctx: MaskContext) -> NDArray[np.float64]:
    """River-delta landscape for delta worlds (CITY-697).

    The shape comes from the seeded delta network in
    :mod:`city_worker.terrain.delta_network`: a sea on one side, a low
    plain inland, and a fan lobe or bird's-foot levee fingers built along the
    distributaries. Replaces the old straight-spoke channel mask (CITY-393).
    """
    from city_worker.terrain.delta_network import delta_heightfield

    water_level = ctx.water_level if ctx.water_level is not None else 0.33
    return delta_heightfield(heightfield, ctx.tx, ctx.ty, ctx.tile_size, ctx.seed, water_level)


# ── Mask registry ────────────────────────────────────────────────

_MASK_REGISTRY: dict[str, MaskFn] = {
    "coastal": coastal_mask,
    "bay_harbor": bay_harbor_mask,
    "river_valley": river_valley_mask,
    "lakefront": lakefront_mask,
    "inland": inland_mask,
    "island": island_mask,
    "peninsula": peninsula_mask,
    "delta": delta_mask,
}


def register_mask(geographic_setting: str, mask_fn: MaskFn) -> None:
    """Register (or replace) a mask function for a geographic setting."""
    _MASK_REGISTRY[geographic_setting] = mask_fn


def get_mask(geographic_setting: str) -> MaskFn:
    """Return the mask function for *geographic_setting*.

    Falls back to :func:`identity_mask` if no dedicated mask is registered.
    """
    return _MASK_REGISTRY.get(geographic_setting, identity_mask)


def apply_geographic_mask(
    heightfield: NDArray[np.float64],
    geographic_setting: str,
    tx: int,
    ty: int,
    tile_size: float,
    resolution: int,
    seed: int,
    water_level: float | None = None,
) -> NDArray[np.float64]:
    """Apply the geographic mask for *geographic_setting* to *heightfield*.

    This is the main entry point called by the terrain generator.
    It looks up the registered mask function, builds a
    :class:`MaskContext`, invokes the mask, and clamps the result
    to [0, 1].

    Args:
        heightfield: 2D numpy array of heights in [0, 1].
        geographic_setting: World type (e.g. ``"island"``, ``"inland"``).
        tx, ty: Tile coordinates.
        tile_size: Tile size in world units.
        resolution: Heightfield resolution (samples per edge).
        seed: World seed.
        water_level: World water level, passed through to masks that need it.

    Returns:
        Modified heightfield, clamped to [0, 1].
    """
    mask_fn = get_mask(geographic_setting)
    ctx = MaskContext(
        tx=tx,
        ty=ty,
        tile_size=tile_size,
        resolution=resolution,
        seed=seed,
        water_level=water_level,
    )
    result = mask_fn(heightfield, ctx)
    return np.clip(result, 0.0, 1.0)
