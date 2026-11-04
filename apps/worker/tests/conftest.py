"""Pytest configuration and fixtures for worker tests."""

import pytest


@pytest.fixture
def sample_job_params():
    """Sample job parameters for testing."""
    return {
        "tile_id": "00000000-0000-0000-0000-000000000001",
        "seed": 12345,
    }
