"""Noise utilities for terrain generation using OpenSimplex."""

import logging

import numpy as np
from numpy.typing import NDArray
from opensimplex import OpenSimplex

logger = logging.getLogger(__name__)


class SeededNoise:
    """Deterministic noise generator with a fixed seed."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._simplex = OpenSimplex(seed=seed)

    def sample_2d(self, x: float, y: float) -> float:
        """Sample 2D noise at the given coordinates. Returns value in [-1, 1]."""
        return self._simplex.noise2(x, y)

    def octave_noise_2d(
        self,
        x: float,
        y: float,
        octaves: int = 6,
        persistence: float = 0.5,
        lacunarity: float = 2.0,
        scale: float = 1.0,
    ) -> float:
        """Generate fractal Brownian motion (fBm) noise.

        Args:
            x, y: World coordinates
            octaves: Number of noise layers to combine
            persistence: Amplitude multiplier per octave (typically 0.5)
            lacunarity: Frequency multiplier per octave (typically 2.0)
            scale: Base frequency scale

        Returns:
            Noise value approximately in [-1, 1]
        """
        total = 0.0
        amplitude = 1.0
        frequency = scale
        max_amplitude = 0.0

        for _ in range(octaves):
            total += amplitude * self.sample_2d(x * frequency, y * frequency)
            max_amplitude += amplitude
            amplitude *= persistence
            frequency *= lacunarity

        return total / max_amplitude


def generate_heightfield(
    seed: int,
    tx: int,
    ty: int,
    tile_size: float,
    resolution: int,
    octaves: int = 6,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
    scale: float = 0.01,
) -> NDArray[np.float64]:
    """Generate a heightfield for a single tile.

    Uses vectorized noise2array for each octave instead of per-pixel
    Python loops. The opensimplex noise2array accepts 1-D x and y
    coordinate arrays and returns a 2-D grid (shape [len(y), len(x)]),
    matching the previous [i, j] = [row, col] indexing exactly.

    Args:
        seed: World seed for deterministic generation
        tx, ty: Tile coordinates
        tile_size: Size of tile in pixel-space world units
        resolution: Number of samples per edge
        octaves: Noise octaves
        persistence: Amplitude decay
        lacunarity: Frequency growth
        scale: Base frequency in cycles per world unit (CITY-650: 0.01 = ~2.6 cycles per 256-unit tile)

    Returns:
        2D numpy array of heights normalized to [0, 1]

    Raises:
        ValueError: If tile_size or resolution is not positive.
    """
    if tile_size <= 0 or resolution <= 0:
        raise ValueError(
            f"tile_size and resolution must be positive (got {tile_size}, {resolution})"
        )
    simplex = OpenSimplex(seed=seed)

    # Build 1-D coordinate arrays in world space.
    # x varies along columns (j), y varies along rows (i).
    x_offset = tx * tile_size
    y_offset = ty * tile_size
    step = tile_size / resolution

    xs = x_offset + np.arange(resolution, dtype=np.float64) * step
    ys = y_offset + np.arange(resolution, dtype=np.float64) * step

    # Accumulate fBm octaves using vectorized noise2array.
    total = np.zeros((resolution, resolution), dtype=np.float64)
    amplitude = 1.0
    max_amplitude = 0.0

    # CITY-650: skip octaves finer than the sample grid can represent.
    # Above half the Nyquist rate (resolution / 4 cycles per tile) an
    # octave aliases into per-sample speckle that shows up as puddles.
    max_frequency = resolution / (4.0 * tile_size)
    if scale > max_frequency:
        logger.warning(
            "height_scale %.4f exceeds the %.4f limit for tile_size=%s "
            "resolution=%s; clamping to avoid aliased terrain",
            scale,
            max_frequency,
            tile_size,
            resolution,
        )
    frequency = min(scale, max_frequency)

    for octave in range(octaves):
        if octave > 0 and frequency > max_frequency:
            break
        # noise2array(x_scaled, y_scaled) returns shape (len(y), len(x))
        total += amplitude * simplex.noise2array(xs * frequency, ys * frequency)
        max_amplitude += amplitude
        amplitude *= persistence
        frequency *= lacunarity

    # Normalize from [-1, 1] to [0, 1]
    heightfield = (total / max_amplitude + 1.0) / 2.0

    return heightfield


def apply_erosion(
    heightfield: NDArray[np.float64],
    seed: int,
    iterations: int = 50,
    rain_amount: float = 0.01,
    evaporation: float = 0.5,
    sediment_capacity: float = 0.1,
) -> NDArray[np.float64]:
    """Apply simple hydraulic erosion to a heightfield.

    This simulates raindrops carrying sediment downhill.  The outer loop
    over rain drops is inherently sequential (each drop modifies the
    heightfield for subsequent drops), but the inner loop is optimised
    by using a flat (1-D) view of the array for fast scalar access and
    direct offset arithmetic for neighbour lookups instead of Python
    for-loops or numpy fancy indexing.

    Starting positions are pre-generated in a single vectorized RNG
    call, preserving the original interleaved (x, y, x, y, ...) draw
    order so the result is deterministically identical.

    Args:
        heightfield: 2D height array
        seed: Random seed for deterministic erosion
        iterations: Number of rain drops to simulate
        rain_amount: Amount of water per drop
        evaporation: Rate of water loss
        sediment_capacity: How much sediment water can carry

    Returns:
        Eroded heightfield
    """
    result = heightfield.copy()
    h, w = result.shape
    rng = np.random.default_rng(seed)

    num_drops = iterations * w

    # Pre-generate all starting positions in interleaved order to
    # match the original per-drop RNG consumption (x, y, x, y, ...).
    starts_interleaved = rng.integers(1, max(w, h) - 1, size=num_drops * 2)
    start_x = starts_interleaved[0::2]
    start_y = starts_interleaved[1::2]

    evap_factor = 1.0 - evaporation

    # Work on a flat (1-D) view for faster scalar element access.
    # Neighbour offsets in the flat layout: left (-1), right (+1),
    # up (-w), down (+w).
    flat = result.ravel()

    for drop_idx in range(num_drops):
        x = int(start_x[drop_idx])
        y = int(start_y[drop_idx])
        water = rain_amount
        sediment = 0.0

        for _ in range(100):  # Max steps per drop
            if x <= 0 or x >= w - 1 or y <= 0 or y >= h - 1:
                break

            idx = y * w + x
            current_height = flat[idx]

            # Direct neighbour access via flat offsets — avoids
            # numpy fancy indexing overhead on tiny (4-element) arrays.
            h_left = flat[idx - 1]
            h_right = flat[idx + 1]
            h_up = flat[idx - w]
            h_down = flat[idx + w]

            # Find steepest descent among 4 neighbours
            min_height = h_left
            dx, dy = -1, 0
            if h_right < min_height:
                min_height = h_right
                dx, dy = 1, 0
            if h_up < min_height:
                min_height = h_up
                dx, dy = 0, -1
            if h_down < min_height:
                min_height = h_down
                dx, dy = 0, 1

            if min_height >= current_height:
                # Flat area — deposit sediment
                flat[idx] += sediment
                break

            # Calculate erosion/deposition
            height_diff = current_height - min_height
            capacity = height_diff * water * sediment_capacity

            if sediment > capacity:
                deposit = (sediment - capacity) * 0.3
                flat[idx] += deposit
                sediment -= deposit
            else:
                erosion = min((capacity - sediment) * 0.3, height_diff * 0.5)
                flat[idx] -= erosion
                sediment += erosion

            # Move to lower cell
            x, y = x + dx, y + dy
            water *= evap_factor

            if water < 0.001:
                break

    return result
