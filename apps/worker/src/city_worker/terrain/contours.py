"""Contour line extraction (CITY-678).

Marching squares that emits connected polylines instead of per-cell
2-point segments.  Every grid edge's level crossing is computed exactly
once, and cells refer to crossings by edge id, so neighbouring cells
share the identical endpoint and segments can be chained by id instead of
by (inexact) coordinate matching.
"""

from __future__ import annotations

import numpy as np
import shapely
from numpy.typing import NDArray

from city_worker.terrain.types import TerrainFeature

# Corner bits for the cell case index
_TL, _TR, _BR, _BL = 1, 2, 4, 8


def pad_heightfield_for_contours(
    heightfield: NDArray[np.float64],
    right: NDArray[np.float64] | None = None,
    bottom: NDArray[np.float64] | None = None,
    diagonal: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """Close a tile's sample grid with its neighbours' first row/column.

    A tile's samples sit at ``x0 + j * cell`` for ``j < w``, so the last
    cell-wide strip before the next tile is covered by neither tile.
    Appending the right neighbour's first column, the bottom neighbour's
    first row and the diagonal neighbour's first sample makes the grid
    span the full tile, and both tiles then compute the crossings on the
    shared border from the same samples, so contours meet exactly.
    Missing neighbours (edge of the generated world) are replaced by
    repeating this tile's last row/column.
    """
    h, w = heightfield.shape
    grid = np.empty((h + 1, w + 1), dtype=np.float64)
    grid[:h, :w] = heightfield
    grid[:h, w] = right[:, 0] if right is not None else heightfield[:, -1]
    grid[h, :w] = bottom[0, :] if bottom is not None else heightfield[-1, :]
    # The corner must match what the right and bottom neighbours use for
    # the same world point when they pad their own grids.
    if diagonal is not None:
        grid[h, w] = diagonal[0, 0]
    elif right is not None:
        grid[h, w] = right[-1, 0]
    elif bottom is not None:
        grid[h, w] = bottom[0, -1]
    else:
        grid[h, w] = heightfield[-1, -1]
    return grid


def _trace_level(
    grid: NDArray[np.float64], level: float
) -> tuple[list[list[int]], NDArray[np.float64], NDArray[np.float64]]:
    """Trace one level. Returns polylines as lists of edge ids plus the
    per-edge crossing coordinates in grid units (column, row)."""
    rows, cols = grid.shape
    above = grid >= level

    # Edge ids: horizontal edge (i, j) joins (i, j)-(i, j+1);
    # vertical edge (i, j) joins (i, j)-(i+1, j).
    n_h = rows * (cols - 1)

    def lerp(va: NDArray[np.float64], vb: NDArray[np.float64]) -> NDArray[np.float64]:
        diff = vb - va
        flat = np.abs(diff) < 1e-12
        return np.where(flat, 0.5, (level - va) / np.where(flat, 1.0, diff))

    # Crossing positions for every edge (only crossed edges are used)
    ih, jh = np.mgrid[0:rows, 0 : cols - 1]
    th = lerp(grid[:, :-1], grid[:, 1:])
    iv, jv = np.mgrid[0 : rows - 1, 0:cols]
    tv = lerp(grid[:-1, :], grid[1:, :])
    edge_col = np.concatenate([(jh + th).ravel(), jv.ravel().astype(np.float64)])
    edge_row = np.concatenate([ih.ravel().astype(np.float64), (iv + tv).ravel()])

    # Cell case index and the ids of each cell's four edges
    tl, tr = above[:-1, :-1], above[:-1, 1:]
    bl, br = above[1:, :-1], above[1:, 1:]
    case = tl * _TL + tr * _TR + br * _BR + bl * _BL
    ci, cj = np.nonzero((case != 0) & (case != 15))
    if ci.size == 0:
        return [], edge_col, edge_row
    case = case[ci, cj]
    top = ci * (cols - 1) + cj
    bottom = (ci + 1) * (cols - 1) + cj
    left = n_h + ci * cols + cj
    right = n_h + ci * cols + cj + 1

    # Which edges each cell crosses (a cell edge is crossed when its two
    # corners disagree), in the fixed order top, right, bottom, left
    t_tl = (case & _TL) > 0
    t_tr = (case & _TR) > 0
    t_br = (case & _BR) > 0
    t_bl = (case & _BL) > 0
    crossed = np.stack([t_tl != t_tr, t_tr != t_br, t_br != t_bl, t_bl != t_tl], axis=1)
    ids = np.stack([top, right, bottom, left], axis=1)

    saddle = crossed.all(axis=1)
    pairs: list[NDArray[np.int64]] = []

    # Regular cells cross exactly two edges: connect them
    reg = ~saddle
    reg_ids = ids[reg][crossed[reg]].reshape(-1, 2)
    pairs.append(reg_ids)

    # Saddles: resolve with the cell-centre average. If the centre is on
    # the same side as the top-left corner, TL and BR connect through the
    # middle, so the contour cuts off TR (top-right) and BL (bottom-left).
    if saddle.any():
        s_ids = ids[saddle]
        si, sj = ci[saddle], cj[saddle]
        centre = (grid[si, sj] + grid[si, sj + 1] + grid[si + 1, sj] + grid[si + 1, sj + 1]) / 4.0
        joined = (centre >= level) == t_tl[saddle]
        t, r, b, lft = s_ids[:, 0], s_ids[:, 1], s_ids[:, 2], s_ids[:, 3]
        first = np.where(joined[:, None], np.stack([t, r], 1), np.stack([t, lft], 1))
        second = np.where(joined[:, None], np.stack([b, lft], 1), np.stack([b, r], 1))
        pairs.extend([first, second])

    seg = np.concatenate(pairs)

    # Each crossed edge belongs to at most two cells, so every node has
    # degree 1 (on the grid boundary) or 2: chains and closed loops only.
    adj: dict[int, list[int]] = {}
    for a, b in seg.tolist():
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    visited: set[int] = set()
    lines: list[list[int]] = []

    def walk(start: int) -> list[int]:
        path = [start]
        visited.add(start)
        prev, cur = -1, start
        while True:
            nxt = next((n for n in adj[cur] if n != prev and n not in visited), None)
            if nxt is None:
                # Close the loop if we came back round to the start
                if len(path) > 2 and start in adj[cur] and prev != start:
                    path.append(start)
                return path
            visited.add(nxt)
            path.append(nxt)
            prev, cur = cur, nxt

    # Open chains start and end on the grid boundary; trace them first so
    # loop tracing never starts in the middle of a chain.
    for node, nbrs in adj.items():
        if len(nbrs) == 1 and node not in visited:
            lines.append(walk(node))
    for node in adj:
        if node not in visited:
            lines.append(walk(node))

    return lines, edge_col, edge_row


def extract_contours(
    grid: NDArray[np.float64],
    x0: float,
    y0: float,
    cell_size: float,
    levels: list[float],
    simplify_tolerance: float | None = None,
    min_loop_length: float = 0.0,
    precision: int = 3,
) -> list[TerrainFeature]:
    """Extract connected contour polylines from a closed sample grid.

    Args:
        grid: Heights with sample (i, j) at (x0 + j*cell_size, y0 + i*cell_size).
            Use :func:`pad_heightfield_for_contours` so it spans the tile.
        x0, y0: World coordinates of sample (0, 0).
        cell_size: Distance between samples.
        levels: Heights to contour.
        simplify_tolerance: Douglas-Peucker tolerance (world units). Endpoints
            are kept, so lines still meet the neighbouring tile exactly.
        min_loop_length: Drop closed loops shorter than this (rings around
            single-cell noise bumps). Open lines are always kept: they end on
            the tile border, and dropping one would leave its continuation in
            the neighbouring tile dangling.
        precision: Decimal places to round coordinates to.

    Returns:
        One ``contour`` LineString feature per polyline, with ``elevation``.
    """
    features: list[TerrainFeature] = []
    for level in levels:
        lines, edge_col, edge_row = _trace_level(grid, level)
        if not lines:
            continue
        geoms = [
            shapely.linestrings(x0 + edge_col[ids] * cell_size, y0 + edge_row[ids] * cell_size)
            for ids in lines
            if len(ids) >= 2
        ]
        if not geoms:
            continue
        arr = np.array(geoms, dtype=object)
        if simplify_tolerance:
            arr = shapely.simplify(arr, simplify_tolerance, preserve_topology=False)
        if min_loop_length > 0:
            tiny_loop = shapely.is_closed(arr) & (shapely.length(arr) < min_loop_length)
            arr = arr[~tiny_loop]
        for geom in arr:
            coords = np.round(shapely.get_coordinates(geom), precision)
            if len(coords) < 2:
                continue
            features.append(
                TerrainFeature(
                    type="contour",
                    geometry={"type": "LineString", "coordinates": coords.tolist()},
                    properties={"elevation": level},
                )
            )
    return features
