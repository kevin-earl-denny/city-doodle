"""Tests for the seeded delta network used by the delta preset (CITY-697)."""

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from city_worker.terrain import TerrainConfig, TerrainGenerator, apply_seed_variation
from city_worker.terrain.delta_network import (
    build_delta_network,
    delta_front_features,
    delta_heightfield,
    delta_river_features,
)

TILE = 256.0


def _world(seed: int):
    kw = apply_seed_variation("delta", seed=seed)
    kw.update(world_seed=seed, geographic_setting="delta")
    return TerrainGenerator(TerrainConfig(**kw)).generate_3x3(1, 1)


class TestDeltaNetwork:
    def test_deterministic_per_seed(self):
        a = build_delta_network(123, TILE)
        build_delta_network.cache_clear()
        b = build_delta_network(123, TILE)
        assert a.form == b.form
        assert len(a.channels) == len(b.channels)
        for ca, cb in zip(a.channels, b.channels):
            np.testing.assert_array_equal(ca.coords, cb.coords)

    def test_both_forms_occur(self):
        forms = {build_delta_network(seed, TILE).form for seed in range(30)}
        assert forms == {"fan", "birds_foot"}

    @pytest.mark.parametrize("seed", [3, 7, 42, 12345])
    def test_network_is_one_connected_tree(self, seed):
        """Every channel starts where another channel ends (or is the trunk)."""
        net = build_delta_network(seed, TILE)
        trunks = [c for c in net.channels if c.order == 0]
        assert len(trunks) == 1
        ends = [tuple(c.coords[-1]) for c in net.channels]
        for ch in net.channels:
            if ch.order == 0:
                continue
            start = ch.coords[0]
            assert min(np.hypot(*(start - np.array(e))) for e in ends) < 1e-6

    @pytest.mark.parametrize("seed", [3, 7, 42, 12345])
    def test_every_mouth_reaches_the_sea(self, seed):
        net = build_delta_network(seed, TILE)
        starts = {tuple(np.round(c.coords[0], 6)) for c in net.channels}
        mouths = [
            c.coords[-1] for c in net.channels if tuple(np.round(c.coords[-1], 6)) not in starts
        ]
        assert mouths
        for m in mouths:
            s, lat = net.frame(np.array(m[0]), np.array(m[1]))
            assert s > net.shore(lat)  # seaward of the shoreline

    def test_widths_taper_downstream(self):
        net = build_delta_network(7, TILE)
        trunk = next(c for c in net.channels if c.order == 0)
        assert all(c.widths.max() <= trunk.widths.max() for c in net.channels)


class TestDeltaHeightfield:
    @pytest.mark.parametrize("seed", [3, 12345])
    def test_sea_takes_one_side(self, seed):
        wl = 0.33
        land = np.vstack(
            [
                np.hstack(
                    [
                        delta_heightfield(np.full((64, 64), 0.5), tx, ty, TILE, seed, wl) >= wl
                        for tx in range(3)
                    ]
                )
                for ty in range(3)
            ]
        )
        # Corner (diagonal) seas plus a fan lobe give the low end of the range
        assert 0.2 < 1 - land.mean() < 0.5
        # Noise texture never flips land to sea: a noisy field gives the same mask
        noisy = np.random.default_rng(0).random((64, 64))
        assert (
            (delta_heightfield(noisy, 1, 1, TILE, seed, wl) >= wl)
            == (delta_heightfield(np.full((64, 64), 0.5), 1, 1, TILE, seed, wl) >= wl)
        ).all()

    def test_trunk_runs_over_land(self):
        seed, wl = 7, 0.33
        net = build_delta_network(seed, TILE)
        trunk = next(c for c in net.channels if c.order == 0)
        for x, y in trunk.coords[::10]:
            tx, ty = int(x // TILE), int(y // TILE)
            if not (0 <= tx < 3 and 0 <= ty < 3):
                continue
            hf = delta_heightfield(np.full((128, 128), 0.5), tx, ty, TILE, seed, wl)
            i = min(int((y - ty * TILE) / (TILE / 128)), 127)
            j = min(int((x - tx * TILE) / (TILE / 128)), 127)
            assert hf[i, j] >= wl


class TestDeltaFeatures:
    def test_river_pieces_are_continuous_across_tiles(self):
        seed = 42
        ends = []
        for ty in range(3):
            for tx in range(3):
                for f in delta_river_features(seed, tx, ty, TILE):
                    coords = f.geometry["coordinates"]
                    assert len(f.properties["widths"]) == len(coords)
                    ends += [coords[0], coords[-1]]
        # Every piece end on an interior tile border meets another piece end
        for x, y in ends:
            on_border = any(abs(v - b) < 1e-6 for v in (x, y) for b in (TILE, 2 * TILE))
            if on_border:
                assert sum(1 for e in ends if Point(e).distance(Point(x, y)) < 1e-3) >= 2

    def test_tidal_flats_sit_on_the_sea_side(self):
        net = build_delta_network(7, TILE)
        (flat,) = delta_front_features(7, TILE)
        # A crescent's centroid falls on its concave side; use an interior point
        p = Polygon(flat.geometry["coordinates"][0]).representative_point()
        s, lat = net.frame(np.array(p.x), np.array(p.y))
        assert s > net.shore(lat)

    @pytest.mark.parametrize("seed", [7, 12345])
    def test_world_has_network_rivers_only(self, seed):
        res = _world(seed)
        feats = [f for t in res.all_tiles() for f in t.features]
        rivers = [f for f in feats if f.type == "river"]
        assert rivers and all("channel_order" in f.properties for f in rivers)
        assert not any(f.type in ("delta_channel", "bay") for f in feats)
        assert any(f.type == "coastline" for f in feats)
