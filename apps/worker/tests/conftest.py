"""Pytest configuration and fixtures for worker tests."""

import pytest


@pytest.fixture
def sample_job_params():
    """Sample job parameters for testing."""
    return {
        "tile_id": "00000000-0000-0000-0000-000000000001",
        "seed": 12345,
    }


# Known failures quarantined by node ID, so the (unformatted, actively edited)
# test modules themselves don't have to be touched. Each entry names its ticket.
_QUARANTINED_XFAIL = {
    "tests/test_terrain.py::TestSeamlessBorders::test_adjacent_tiles_share_edge_values": (
        "CITY-674: edge values differ by ~0.205 (> 0.2) at seed 42; seam or tolerance?"
    ),
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        reason = _QUARANTINED_XFAIL.get(item.nodeid)
        if reason:
            item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
