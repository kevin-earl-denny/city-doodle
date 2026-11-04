FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/
COPY pyproject.toml .

# Install the application
RUN pip install --no-cache-dir -e .

# CITY-700: numba JIT-compiles opensimplex's noise kernel (~20x faster terrain).
# Compile it here, into a cache baked into the image, so no job pays the
# 20-60s first compile. NUMBA_CPU_NAME=generic makes that cache valid on Fly
# worker CPUs, which differ from the build machine's. The worker has 1 vCPU,
# so one numba thread. The worker re-runs the warm-up at startup (a cache hit
# takes about a second).
ENV NUMBA_CACHE_DIR=/app/.numba-cache \
    NUMBA_CPU_NAME=generic \
    NUMBA_NUM_THREADS=1
RUN python -c "from city_worker.terrain.noise import warm_noise_jit; print(f'numba warm-up {warm_noise_jit():.1f}s')"

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the worker
CMD ["python", "-m", "city_worker.main"]
