"""Tests for connected contour extraction (CITY-678)."""

import numpy as np
from scipy.ndimage import gaussian_filter

from city_worker.terrain.contours import extract_contours, pad_heightfield_for_contours
from city_worker.terrain.generator import TerrainGenerator
from city_worker.terrain.types import TerrainConfig


def _smooth_field(n: int, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    field = gaussian_filter(rng.random((n, n)), 3)
    return (field - field.min()) / (field.max() - field.min())


def _on_grid_border(point, size: float) -> bool:
    x, y = point
    return min(x, y) <= 1e-9 or max(x, y) >= size - 1e-9


class TestExtractContours:
    def test_bump_gives_one_closed_ring(self):
        y, x = np.mgrid[0:33, 0:33]
        grid = np.exp(-((x - 16) ** 2 + (y - 16) ** 2) / 60.0)
        features = extract_contours(grid, 0.0, 0.0, 1.0, [0.5])
        assert len(features) == 1
        coords = features[0].geometry["coordinates"]
        assert coords[0] == coords[-1]
        assert len(coords) > 20

    def test_ramp_simplifies_to_one_straight_line(self):
        grid = np.tile(np.linspace(0.0, 1.0, 33), (33, 1))
        features = extract_contours(grid, 0.0, 0.0, 1.0, [0.5], simplify_tolerance=0.5)
        assert len(features) == 1
        assert features[0].geometry["coordinates"] == [[16.0, 0.0], [16.0, 32.0]]

    def test_lines_are_closed_or_end_on_the_border(self):
        """No dashes: every polyline is a loop or runs border to border."""
        grid = _smooth_field(129)
        features = extract_contours(grid, 0.0, 0.0, 1.0, [0.3, 0.5, 0.7])
        assert len(features) > 10
        for f in features:
            coords = f.geometry["coordinates"]
            assert f.geometry["type"] == "LineString"
            if coords[0] == coords[-1]:
                continue
            assert _on_grid_border(coords[0], 128)
            assert _on_grid_border(coords[-1], 128)

    def test_no_per_level_cap(self):
        """Dense contours are not truncated (the old code kept 100 cells/level)."""
        # 20 periods across the grid: 40 full-height lines, ~5,000 active
        # cells (the old cap allowed 100, less than one line).
        wave = np.sin(np.linspace(0.1, 0.1 + 40 * np.pi, 129)) * 0.5 + 0.5
        grid = np.tile(wave, (129, 1))
        features = extract_contours(grid, 0.0, 0.0, 1.0, [0.5])
        assert len(features) == 40
        for f in features:
            ys = [p[1] for p in f.geometry["coordinates"]]
            assert min(ys) == 0.0 and max(ys) == 128.0

    def test_tiny_loops_dropped_but_border_stubs_kept(self):
        grid = np.zeros((33, 33))
        grid[16, 16] = 1.0  # single-sample bump: a tiny diamond loop
        grid[0, 0] = 1.0  # corner bump: a short open stub on the border
        features = extract_contours(grid, 0.0, 0.0, 1.0, [0.5], min_loop_length=4.0)
        assert len(features) == 1
        coords = features[0].geometry["coordinates"]
        assert coords[0] != coords[-1]


class TestTileSeams:
    def test_adjacent_tiles_share_border_endpoints(self):
        """Contours crossing a tile border end at identical points on both sides."""
        world = _smooth_field(129, seed=7)[:, :128]  # one field, two 64-wide tiles
        left, right = world[:64, :64], world[:64, 64:]
        levels = [0.4, 0.5, 0.6]
        left_f = extract_contours(
            pad_heightfield_for_contours(left, right=right),
            0.0,
            0.0,
            1.0,
            levels,
            simplify_tolerance=0.5,
        )
        right_f = extract_contours(
            pad_heightfield_for_contours(right),
            64.0,
            0.0,
            1.0,
            levels,
            simplify_tolerance=0.5,
        )

        def border_points(features):
            pts = set()
            for f in features:
                for p in (f.geometry["coordinates"][0], f.geometry["coordinates"][-1]):
                    if p[0] == 64.0:
                        pts.add((f.properties["elevation"], p[1]))
            return pts

        shared = border_points(left_f)
        assert shared, "test field should have contours crossing x=64"
        assert shared == border_points(right_f)

    def test_pad_corner_matches_neighbours(self):
        hf = np.zeros((4, 4))
        right = np.full((4, 4), 1.0)
        bottom = np.full((4, 4), 2.0)
        diagonal = np.full((4, 4), 3.0)
        grid = pad_heightfield_for_contours(hf, right, bottom, diagonal)
        assert grid.shape == (5, 5)
        assert grid[4, 4] == 3.0
        assert (grid[:4, 4] == 1.0).all() and (grid[4, :4] == 2.0).all()
        # Bottom-row tile without a bottom neighbour uses its right
        # neighbour's last value, matching what that neighbour pads with.
        assert pad_heightfield_for_contours(hf, right=right)[4, 4] == 1.0


class TestPipelineContours:
    def test_generate_3x3_contours_are_connected(self):
        config = TerrainConfig(world_seed=42, geographic_setting="river_valley")
        result = TerrainGenerator(config).generate_3x3(1, 1)
        ts = config.tile_size
        total = 0
        ends: dict[tuple, int] = {}
        for tile in result.all_tiles():
            x0, y0 = tile.tx * ts, tile.ty * ts
            for f in tile.features:
                if f.type != "contour":
                    continue
                total += 1
                assert f.geometry["type"] == "LineString"
                assert "elevation" in f.properties
                coords = f.geometry["coordinates"]
                if coords[0] == coords[-1]:
                    continue
                for x, y in (coords[0], coords[-1]):
                    on_border = x in (x0, x0 + ts) or y in (y0, y0 + ts)
                    assert on_border, (
                        f"dangling contour end at {(x, y)} in tile {tile.tx},{tile.ty}"
                    )
                    if 0 < x < 3 * ts and 0 < y < 3 * ts:
                        key = (f.properties["elevation"], x, y)
                        ends[key] = ends.get(key, 0) + 1
        assert total > 0
        # Every endpoint on an inner tile border is shared by exactly two tiles
        assert ends and all(n == 2 for n in ends.values())
