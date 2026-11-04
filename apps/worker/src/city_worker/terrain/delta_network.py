"""Seeded river-delta geometry for the delta preset (CITY-697).

A delta world has a sea on one side and a single trunk river entering from
the inland edge. Near the coast the trunk splits into a branching network of
meandering distributaries that reach the sea. Two real-world forms are
chosen by seed:

- ``fan`` (Nile-like): an arc-shaped lobe pushed out into the sea, with many
  distributaries spreading evenly across it.
- ``birds_foot`` (Mississippi-like): a few long passes whose levees extend as
  narrow fingers of land far into the sea.

Everything is defined in world coordinates and built once per seed, so the
heightfield shape, the channels and the tidal flats line up across all
tiles of the 3x3 world.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box

from city_worker.terrain.types import TerrainFeature

WORLD_TILES = 3

TRUNK_WIDTH = 4.5  # world units (px); ~1.4 km at ~314 m/px
MIN_CHANNEL_WIDTH = 1.2
LEVEE_MARGIN = 7.0  # land on each bank where a distributary runs out to sea
CHILD_WIDTH_RATIO = 0.75


@dataclass(frozen=True)
class Channel:
    """One river segment of the delta network, in world coordinates."""

    coords: NDArray[np.float64]  # (N, 2)
    widths: NDArray[np.float64]  # (N,)
    order: int  # 0 = trunk, 1+ = distributary depth


@dataclass(frozen=True)
class DeltaNetwork:
    form: str  # "fan" | "birds_foot"
    center: tuple[float, float]
    seaward: tuple[float, float]  # unit vector pointing out to sea
    world_size: float
    shore_base: float  # baseline shoreline, distance from center along seaward
    lobe_bulge: float  # how far the delta lobe pushes the shore out to sea
    lobe_half_width: float
    shore_wiggle: tuple[tuple[float, float, float], ...]  # (amplitude, freq, phase)
    channels: tuple[Channel, ...]

    def frame(
        self, x: NDArray[np.float64], y: NDArray[np.float64]
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """World (x, y) -> (s, lat): s is distance toward the sea, lat is lateral."""
        dx, dy = x - self.center[0], y - self.center[1]
        cs, sn = self.seaward
        return dx * cs + dy * sn, -dx * sn + dy * cs

    def to_world(self, s: NDArray[np.float64], lat: NDArray[np.float64]) -> NDArray[np.float64]:
        cs, sn = self.seaward
        x = self.center[0] + s * cs - lat * sn
        y = self.center[1] + s * sn + lat * cs
        return np.stack([x, y], axis=-1)

    def shore(self, lat: NDArray[np.float64]) -> NDArray[np.float64]:
        """Shoreline position (in s) as a function of lateral position."""
        lobe = np.clip(1.0 - (lat / self.lobe_half_width) ** 2, 0.0, None) ** 0.8
        wiggle = sum(
            a * np.sin(2 * math.pi * f * lat / self.world_size + p) for a, f, p in self.shore_wiggle
        )
        return self.shore_base + self.lobe_bulge * lobe + wiggle


def _meander(
    a: NDArray[np.float64],
    b: NDArray[np.float64],
    wavelength: float,
    rng: np.random.Generator,
    spacing: float = 3.0,
) -> NDArray[np.float64]:
    """Smooth meandering path from a to b that starts and ends exactly there.

    Amplitude is tied to the meander wavelength (about a fifth of it, as in
    real rivers), not to the path length, so long rivers don't zigzag.
    """
    vec = b - a
    length = float(np.hypot(*vec))
    n = max(8, int(length / spacing))
    t = np.linspace(0.0, 1.0, n)
    perp = np.array([-vec[1], vec[0]]) / max(length, 1e-9)
    waves = max(0.75, length / wavelength)
    offset = np.zeros_like(t)
    for k, weight in ((1.0, 1.0), (2.1, 0.3)):
        freq = waves * k * rng.uniform(0.85, 1.15)
        offset += weight * np.sin(2 * math.pi * freq * t + rng.uniform(0, 2 * math.pi))
    amplitude = min(0.2 * wavelength, 0.15 * length)
    # Envelope pins both ends so junctions stay connected
    offset *= amplitude / 1.3 * np.sin(math.pi * t) ** 0.8
    return a + t[:, None] * vec + offset[:, None] * perp


@lru_cache(maxsize=32)
def build_delta_network(seed: int, tile_size: float) -> DeltaNetwork:
    """Build the delta network for a world seed (deterministic, cached)."""
    rng = np.random.default_rng([abs(int(seed)) % (2**32), 697])
    world = WORLD_TILES * tile_size
    center = (world / 2.0, world / 2.0)
    theta = rng.uniform(0.0, 2.0 * math.pi)
    seaward = (math.cos(theta), math.sin(theta))
    form = "fan" if rng.random() < 0.5 else "birds_foot"

    shore_base = world * rng.uniform(0.10, 0.16)
    if form == "fan":
        lobe_bulge = world * rng.uniform(0.10, 0.14)
        lobe_half_width = world * rng.uniform(0.34, 0.42)
    else:
        lobe_bulge = world * 0.03
        lobe_half_width = world * 0.25
    shore_wiggle = tuple(
        (world * amp, freq * rng.uniform(0.85, 1.15), rng.uniform(0, 2 * math.pi))
        for amp, freq in ((0.012, 1.3), (0.006, 2.9), (0.003, 5.7))
    )
    net = DeltaNetwork(
        form=form,
        center=center,
        seaward=seaward,
        world_size=world,
        shore_base=shore_base,
        lobe_bulge=lobe_bulge,
        lobe_half_width=lobe_half_width,
        shore_wiggle=shore_wiggle,
        channels=(),
    )

    # Mouths (s, lat) where distributaries meet the sea, ordered left to right
    if form == "fan":
        n_mouths = int(rng.integers(6, 10))
        ls = np.linspace(-0.82, 0.82, n_mouths) * lobe_half_width
        ls += rng.uniform(-0.04, 0.04, n_mouths) * lobe_half_width
        mouth_s = net.shore(ls) + world * 0.012
        apex_s = shore_base - world * rng.uniform(0.20, 0.28)
        split_frac, wavelength = (0.30, 0.45), 70.0
    else:
        n_mouths = int(rng.integers(3, 5))
        ls = np.linspace(-0.17, 0.17, n_mouths) * world
        ls += rng.uniform(-0.025, 0.025, n_mouths) * world
        mouth_s = shore_base + world * rng.uniform(0.20, 0.30, n_mouths)
        apex_s = shore_base - world * 0.06
        split_frac, wavelength = (0.05, 0.12), 160.0
    mouths = [np.array(p) for p in zip(mouth_s, ls)]
    apex = np.array([apex_s, rng.uniform(-0.05, 0.05) * world])

    def world_pt(sl: NDArray[np.float64]) -> NDArray[np.float64]:
        return net.to_world(np.array(sl[0]), np.array(sl[1]))

    channels: list[Channel] = []

    def add(a_sl, b_sl, width: float, order: int, wl: float) -> None:
        coords = _meander(world_pt(a_sl), world_pt(b_sl), wl, rng)
        widths = np.linspace(width, width * 0.9, len(coords))
        channels.append(Channel(coords=coords, widths=widths, order=order))

    # Trunk: from beyond the inland edge to the apex
    trunk_start = np.array([-0.85 * world, apex[1] + rng.uniform(-0.1, 0.1) * world])
    add(trunk_start, apex, TRUNK_WIDTH, 0, rng.uniform(110.0, 150.0))

    def branch(node, group: list, width: float, order: int) -> None:
        if len(group) == 1:
            add(node, group[0], width, order, wavelength)
            return
        k = len(group) // 2
        if len(group) > 2:
            k += int(rng.integers(-1, 2))
        k = min(max(k, 1), len(group) - 1)
        for sub in (group[:k], group[k:]):
            target = np.mean(sub, axis=0)
            split = node + rng.uniform(*split_frac) * (target - node)
            if len(sub) == 1:
                add(node, sub[0], width, order, wavelength)
            else:
                add(node, split, width, order, wavelength)
                branch(split, sub, max(MIN_CHANNEL_WIDTH, width * CHILD_WIDTH_RATIO), order + 1)

    branch(apex, mouths, TRUNK_WIDTH * CHILD_WIDTH_RATIO, 1)
    return DeltaNetwork(**{**net.__dict__, "channels": tuple(channels)})


def _distance_to_channels(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    channels: list[Channel],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Distance from each point to the nearest channel, and that channel's width there."""
    best = np.full(x.shape, np.inf)
    best_w = np.zeros(x.shape)
    px, py = x.ravel(), y.ravel()
    for ch in channels:
        a, b = ch.coords[:-1], ch.coords[1:]
        wa = ch.widths[:-1]
        d = b - a
        len2 = np.maximum((d**2).sum(axis=1), 1e-12)
        # (points, segments) projections, chunked by segment to bound memory
        for start in range(0, len(a), 256):
            sl = slice(start, start + 256)
            t = ((px[:, None] - a[sl, 0]) * d[sl, 0] + (py[:, None] - a[sl, 1]) * d[sl, 1]) / len2[
                sl
            ]
            t = np.clip(t, 0.0, 1.0)
            qx = a[sl, 0] + t * d[sl, 0]
            qy = a[sl, 1] + t * d[sl, 1]
            dist = np.hypot(px[:, None] - qx, py[:, None] - qy)
            idx = dist.argmin(axis=1)
            dmin = dist[np.arange(len(px)), idx]
            closer = dmin < best.ravel()
            best.ravel()[closer] = dmin[closer]
            best_w.ravel()[closer] = wa[sl][idx][closer]
    return best, best_w


def delta_heightfield(
    heightfield: NDArray[np.float64],
    tx: int,
    ty: int,
    tile_size: float,
    seed: int,
    water_level: float,
) -> NDArray[np.float64]:
    """Reshape a tile's noise heightfield into the delta landscape.

    Land is a low plain rising gently inland; the sea is below water level.
    Channel levees extend into the sea (long fingers for bird's-foot, short
    mouth spits for fan). Noise only adds texture and never flips land/sea.
    """
    net = build_delta_network(seed, tile_size)
    res = heightfield.shape[0]
    step = tile_size / res
    xs = tx * tile_size + np.arange(res) * step
    ys = ty * tile_size + np.arange(res) * step
    xx, yy = np.meshgrid(xs, ys)
    s, lat = net.frame(xx, yy)
    inland = net.shore(lat) - s  # > 0 on land
    world = net.world_size
    noise = heightfield - 0.5

    rise = np.clip(inland / (0.9 * world), 0.0, 1.0) ** 0.8
    relief = 0.10 * np.clip(inland / (0.25 * world), 0.0, 1.0)
    land_h = np.maximum(water_level + 0.035 + 0.30 * rise + noise * relief, water_level + 0.015)

    depth = np.clip(-inland / (0.3 * world), 0.0, 1.0)
    sea_h = np.minimum(water_level - 0.04 - 0.2 * depth + noise * 0.02, water_level - 0.02)

    land = inland > 0
    # Levees: distributaries build land along their banks out into the sea
    margin = 0.4 * world
    x0, y0, x1, y1 = xs[0] - margin, ys[0] - margin, xs[-1] + margin, ys[-1] + margin
    near = [
        ch
        for ch in net.channels
        if ch.order > 0
        and ch.coords[:, 0].max() > x0
        and ch.coords[:, 0].min() < x1
        and ch.coords[:, 1].max() > y0
        and ch.coords[:, 1].min() < y1
    ]
    if near and not land.all():
        dist, width = _distance_to_channels(xx, yy, near)
        levee = dist < (width / 2.0 + LEVEE_MARGIN)
        land |= levee

    return np.where(land, land_h, sea_h)


def _clip_channel(
    ch: Channel, x0: float, y0: float, x1: float, y1: float
) -> list[tuple[list[tuple[float, float]], list[float]]]:
    """Clip a channel to a box, re-sampling widths onto the clipped vertices."""
    line = LineString(ch.coords)
    clipped = line.intersection(box(x0, y0, x1, y1))
    if clipped.is_empty:
        return []
    parts = clipped.geoms if isinstance(clipped, MultiLineString) else [clipped]
    seg = np.hypot(*np.diff(ch.coords, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    pieces = []
    for part in parts:
        if not isinstance(part, LineString) or len(part.coords) < 2:
            continue
        pts = np.array(part.coords)
        pts[:, 0] = np.clip(pts[:, 0], x0, x1)
        pts[:, 1] = np.clip(pts[:, 1], y0, y1)
        along = np.array([line.project(Point(p)) for p in pts])
        widths = np.interp(along, cum, ch.widths)
        pieces.append(
            ([(float(x), float(y)) for x, y in pts], [round(float(w), 2) for w in widths])
        )
    return pieces


def delta_river_features(seed: int, tx: int, ty: int, tile_size: float) -> list[TerrainFeature]:
    """The delta's trunk and distributaries, clipped to one tile."""
    net = build_delta_network(seed, tile_size)
    x0, y0 = tx * tile_size, ty * tile_size
    features = []
    for ch in net.channels:
        for coords, widths in _clip_channel(ch, x0, y0, x0 + tile_size, y0 + tile_size):
            features.append(
                TerrainFeature(
                    type="river",
                    geometry={"type": "LineString", "coordinates": coords},
                    properties={
                        "length": LineString(coords).length,
                        "width": max(widths),
                        "widths": widths,
                        "channel_order": ch.order,
                        "delta_form": net.form,
                    },
                )
            )
    return features


def delta_front_features(seed: int, tile_size: float) -> list[TerrainFeature]:
    """Tidal flats fringing the seaward edge of the delta lobe (unclipped)."""
    net = build_delta_network(seed, tile_size)
    half = net.lobe_half_width * (0.9 if net.form == "fan" else 0.6)
    ls = np.linspace(-half, half, 120)
    taper = np.sqrt(np.clip(1.0 - (ls / half) ** 2, 0.0, None))
    width = net.world_size * (0.018 if net.form == "fan" else 0.012) * taper
    inner = net.to_world(net.shore(ls) + 1.0, ls)
    outer = net.to_world(net.shore(ls) + 1.0 + width, ls)
    poly = Polygon(np.concatenate([inner, outer[::-1]]))
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or not isinstance(poly, Polygon):
        return []
    return [
        TerrainFeature(
            type="tidal_flat",
            geometry={"type": "Polygon", "coordinates": [list(poly.exterior.coords)]},
            properties={"area": poly.area, "delta_form": net.form},
        )
    ]
