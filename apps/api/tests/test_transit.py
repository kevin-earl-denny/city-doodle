"""Tests for transit CRUD endpoints - stations, lines, and segments."""

import pytest
from httpx import AsyncClient

# Test user IDs for the X-User-Id header
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"

# The test world created by conftest.py
TEST_WORLD_ID = "00000000-0000-0000-0000-000000000010"

# Sample GeoJSON polygon for district boundaries
SAMPLE_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]],
}


async def create_test_district(client: AsyncClient) -> str:
    """Helper to create a test district and return its ID."""
    response = await client.post(
        f"/worlds/{TEST_WORLD_ID}/districts",
        json={
            "world_id": TEST_WORLD_ID,
            "type": "airport",
            "name": "Test Airport District",
            "geometry": SAMPLE_GEOMETRY,
        },
        headers={"X-User-Id": TEST_USER_ID},
    )
    assert response.status_code == 201
    return response.json()["id"]


# ============================================================================
# Transit Station Tests
# ============================================================================


class TestCreateStation:
    """Tests for POST /worlds/{world_id}/transit/stations endpoint."""

    @pytest.mark.asyncio
    async def test_create_station_success(self, client: AsyncClient):
        """Create station should return 201 with station data."""
        district_id = await create_test_district(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Central Station",
                "position_x": 50.0,
                "position_y": 50.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Central Station"
        assert data["station_type"] == "subway"
        assert data["position_x"] == 50.0
        assert data["position_y"] == 50.0
        assert data["is_terminus"] is False
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_station_with_terminus(self, client: AsyncClient):
        """Create station with is_terminus flag."""
        district_id = await create_test_district(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "rail",
                "name": "Terminal Station",
                "position_x": 0.0,
                "position_y": 0.0,
                "is_terminus": True,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["station_type"] == "rail"
        assert data["is_terminus"] is True

    @pytest.mark.asyncio
    async def test_create_station_requires_district(self, client: AsyncClient):
        """Create station without district_id should fail."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "station_type": "subway",
                "name": "No District Station",
                "position_x": 50.0,
                "position_y": 50.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_station_invalid_district(self, client: AsyncClient):
        """Create station with non-existent district should fail."""
        fake_district_id = "00000000-0000-0000-0000-000000000000"

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": fake_district_id,
                "station_type": "subway",
                "name": "Bad District Station",
                "position_x": 50.0,
                "position_y": 50.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_station_forbidden_for_other_user(self, client: AsyncClient):
        """Create station should return 403 for another user's world."""
        district_id = await create_test_district(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Unauthorized Station",
                "position_x": 50.0,
                "position_y": 50.0,
            },
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403


class TestListStations:
    """Tests for GET /worlds/{world_id}/transit/stations endpoint."""

    @pytest.mark.asyncio
    async def test_list_stations_empty(self, client: AsyncClient):
        """List stations should return empty list for world with no stations."""
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_stations_returns_created(self, client: AsyncClient):
        """List stations should return all created stations."""
        district_id = await create_test_district(client)

        # Create stations
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Station 1",
                "position_x": 10.0,
                "position_y": 10.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "rail",
                "name": "Station 2",
                "position_x": 20.0,
                "position_y": 20.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_stations_filter_by_type(self, client: AsyncClient):
        """List stations with type filter."""
        district_id = await create_test_district(client)

        # Create subway and rail stations
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Subway Station",
                "position_x": 10.0,
                "position_y": 10.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "rail",
                "name": "Rail Station",
                "position_x": 20.0,
                "position_y": 20.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # Filter by subway
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/stations?station_type=subway",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["station_type"] == "subway"


class TestDeleteStation:
    """Tests for DELETE /transit/stations/{station_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_station_success(self, client: AsyncClient):
        """Delete station should return 204."""
        district_id = await create_test_district(client)

        # Create a station
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "To Delete",
                "position_x": 50.0,
                "position_y": 50.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        station_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/transit/stations/{station_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/transit/stations/{station_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_station_not_found(self, client: AsyncClient):
        """Delete station should return 404 for non-existent station."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/transit/stations/{fake_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 404


# ============================================================================
# Transit Line Tests
# ============================================================================


class TestCreateLine:
    """Tests for POST /worlds/{world_id}/transit/lines endpoint."""

    @pytest.mark.asyncio
    async def test_create_line_success(self, client: AsyncClient):
        """Create line should return 201 with line data."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Red Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Red Line"
        assert data["line_type"] == "subway"
        assert data["color"] == "#FF0000"
        assert data["is_auto_generated"] is False
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_line_with_auto_generated(self, client: AsyncClient):
        """Create auto-generated line."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "rail",
                "name": "Auto Line",
                "color": "#00FF00",
                "is_auto_generated": True,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_auto_generated"] is True

    @pytest.mark.asyncio
    async def test_create_line_invalid_color(self, client: AsyncClient):
        """Create line with invalid color should fail."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Bad Color Line",
                "color": "red",  # Invalid - should be hex
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_line_forbidden_for_other_user(self, client: AsyncClient):
        """Create line should return 403 for another user's world."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Unauthorized Line",
                "color": "#0000FF",
            },
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403


class TestListLines:
    """Tests for GET /worlds/{world_id}/transit/lines endpoint."""

    @pytest.mark.asyncio
    async def test_list_lines_empty(self, client: AsyncClient):
        """List lines should return empty list for world with no lines."""
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_lines_returns_created(self, client: AsyncClient):
        """List lines should return all created lines."""
        # Create lines
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Line 1",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "rail",
                "name": "Line 2",
                "color": "#00FF00",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestDeleteLine:
    """Tests for DELETE /transit/lines/{line_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_line_success(self, client: AsyncClient):
        """Delete line should return 204."""
        # Create a line
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "To Delete",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        line_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/transit/lines/{line_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/transit/lines/{line_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert get_response.status_code == 404


# ============================================================================
# Transit Line Segment Tests
# ============================================================================


class TestCreateSegment:
    """Tests for POST /transit/lines/{line_id}/segments endpoint."""

    @pytest.mark.asyncio
    async def test_create_segment_success(self, client: AsyncClient):
        """Create segment should return 201 with segment data."""
        district_id = await create_test_district(client)

        # Create stations
        station1_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Station A",
                "position_x": 0.0,
                "position_y": 0.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        station1_id = station1_response.json()["id"]

        station2_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Station B",
                "position_x": 100.0,
                "position_y": 100.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        station2_id = station2_response.json()["id"]

        # Create line
        line_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Test Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        line_id = line_response.json()["id"]

        # Create segment
        response = await client.post(
            f"/transit/lines/{line_id}/segments",
            json={
                "line_id": line_id,
                "from_station_id": station1_id,
                "to_station_id": station2_id,
                "geometry": [{"x": 50.0, "y": 50.0}],
                "is_underground": True,
                "order_in_line": 0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["from_station_id"] == station1_id
        assert data["to_station_id"] == station2_id
        assert data["order_in_line"] == 0
        assert data["is_underground"] is True
        assert len(data["geometry"]) == 1

    @pytest.mark.asyncio
    async def test_create_segment_invalid_stations(self, client: AsyncClient):
        """Create segment with non-existent stations should fail."""
        # Create line
        line_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Test Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        line_id = line_response.json()["id"]

        # Two distinct nonexistent stations: identical IDs are rejected earlier by
        # schema validation (422), which would not exercise the existence check.
        response = await client.post(
            f"/transit/lines/{line_id}/segments",
            json={
                "line_id": line_id,
                "from_station_id": "00000000-0000-0000-0000-0000000000a1",
                "to_station_id": "00000000-0000-0000-0000-0000000000a2",
                "order_in_line": 0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 400


class TestListSegments:
    """Tests for GET /transit/lines/{line_id}/segments endpoint."""

    @pytest.mark.asyncio
    async def test_list_segments_returns_ordered(self, client: AsyncClient):
        """List segments should return segments in order."""
        district_id = await create_test_district(client)

        # Create three stations
        stations = []
        for i in range(3):
            station_response = await client.post(
                f"/worlds/{TEST_WORLD_ID}/transit/stations",
                json={
                    "world_id": TEST_WORLD_ID,
                    "district_id": district_id,
                    "station_type": "subway",
                    "name": f"Station {i}",
                    "position_x": float(i * 50),
                    "position_y": float(i * 50),
                },
                headers={"X-User-Id": TEST_USER_ID},
            )
            stations.append(station_response.json()["id"])

        # Create line
        line_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Test Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        line_id = line_response.json()["id"]

        # Create segments (out of order to test ordering)
        await client.post(
            f"/transit/lines/{line_id}/segments",
            json={
                "line_id": line_id,
                "from_station_id": stations[1],
                "to_station_id": stations[2],
                "order_in_line": 1,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/transit/lines/{line_id}/segments",
            json={
                "line_id": line_id,
                "from_station_id": stations[0],
                "to_station_id": stations[1],
                "order_in_line": 0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # List segments
        response = await client.get(
            f"/transit/lines/{line_id}/segments",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Should be ordered by order_in_line
        assert data[0]["order_in_line"] == 0
        assert data[1]["order_in_line"] == 1


# ============================================================================
# Transit Network Tests
# ============================================================================


class TestTransitNetwork:
    """Tests for GET /worlds/{world_id}/transit endpoint."""

    @pytest.mark.asyncio
    async def test_get_transit_network(self, client: AsyncClient):
        """Get transit network should return complete data."""
        district_id = await create_test_district(client)

        # Create a station
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Station A",
                "position_x": 0.0,
                "position_y": 0.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # Create a line
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Red Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["world_id"] == TEST_WORLD_ID
        assert len(data["stations"]) == 1
        assert len(data["lines"]) == 1


class TestTransitNetworkStats:
    """Tests for GET /worlds/{world_id}/transit/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_transit_stats(self, client: AsyncClient):
        """Get transit stats should return statistics."""
        district_id = await create_test_district(client)

        # Create stations of different types
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Subway Station",
                "position_x": 0.0,
                "position_y": 0.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "rail",
                "name": "Rail Station",
                "position_x": 100.0,
                "position_y": 100.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # Create a line
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Test Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/stats",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_stations"] == 2
        assert data["total_lines"] == 1
        assert data["total_segments"] == 0
        assert data["stations_by_type"]["subway"] == 1
        assert data["stations_by_type"]["rail"] == 1


class TestClearTransitNetwork:
    """Tests for DELETE /worlds/{world_id}/transit endpoint."""

    @pytest.mark.asyncio
    async def test_clear_transit_network(self, client: AsyncClient):
        """Clear transit network should delete all transit data."""
        district_id = await create_test_district(client)

        # Create some transit data
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "subway",
                "name": "Station",
                "position_x": 0.0,
                "position_y": 0.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "subway",
                "name": "Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # Clear
        response = await client.delete(
            f"/worlds/{TEST_WORLD_ID}/transit",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify everything is gone
        stations_response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert stations_response.json() == []

        lines_response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert lines_response.json() == []


# ============================================================================
# Bulk Operation Tests
# ============================================================================


class TestBulkCreateStations:
    """Tests for POST /worlds/{world_id}/transit/stations/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_create_stations_success(self, client: AsyncClient):
        """Bulk create should return 201 with multiple stations."""
        district_id = await create_test_district(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations/bulk",
            json={
                "stations": [
                    {
                        "world_id": TEST_WORLD_ID,
                        "district_id": district_id,
                        "station_type": "subway",
                        "name": "Station 1",
                        "position_x": 0.0,
                        "position_y": 0.0,
                    },
                    {
                        "world_id": TEST_WORLD_ID,
                        "district_id": district_id,
                        "station_type": "subway",
                        "name": "Station 2",
                        "position_x": 50.0,
                        "position_y": 50.0,
                    },
                    {
                        "world_id": TEST_WORLD_ID,
                        "district_id": district_id,
                        "station_type": "rail",
                        "name": "Station 3",
                        "position_x": 100.0,
                        "position_y": 100.0,
                    },
                ]
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 3


class TestBulkCreateLines:
    """Tests for POST /worlds/{world_id}/transit/lines/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_create_lines_success(self, client: AsyncClient):
        """Bulk create should return 201 with multiple lines."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines/bulk",
            json={
                "lines": [
                    {
                        "world_id": TEST_WORLD_ID,
                        "line_type": "subway",
                        "name": "Red Line",
                        "color": "#FF0000",
                    },
                    {
                        "world_id": TEST_WORLD_ID,
                        "line_type": "subway",
                        "name": "Blue Line",
                        "color": "#0000FF",
                    },
                ]
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2


# ============================================================================
# Station Type and Line Type Tests
# ============================================================================


class TestStationTypes:
    """Tests for different station types."""

    @pytest.mark.asyncio
    async def test_all_station_types_valid(self, client: AsyncClient):
        """All station types should be valid."""
        district_id = await create_test_district(client)

        for station_type in ["subway", "rail"]:
            response = await client.post(
                f"/worlds/{TEST_WORLD_ID}/transit/stations",
                json={
                    "world_id": TEST_WORLD_ID,
                    "district_id": district_id,
                    "station_type": station_type,
                    "name": f"{station_type.title()} Station",
                    "position_x": 0.0,
                    "position_y": 0.0,
                },
                headers={"X-User-Id": TEST_USER_ID},
            )
            assert response.status_code == 201, f"Failed for type: {station_type}"

    @pytest.mark.asyncio
    async def test_invalid_station_type(self, client: AsyncClient):
        """Invalid station type should return 422."""
        district_id = await create_test_district(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/stations",
            json={
                "world_id": TEST_WORLD_ID,
                "district_id": district_id,
                "station_type": "bus",  # Invalid
                "name": "Invalid Station",
                "position_x": 0.0,
                "position_y": 0.0,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 422


class TestLineTypes:
    """Tests for different line types."""

    @pytest.mark.asyncio
    async def test_all_line_types_valid(self, client: AsyncClient):
        """All line types should be valid."""
        for line_type in ["subway", "rail"]:
            response = await client.post(
                f"/worlds/{TEST_WORLD_ID}/transit/lines",
                json={
                    "world_id": TEST_WORLD_ID,
                    "line_type": line_type,
                    "name": f"{line_type.title()} Line",
                    "color": "#FF0000",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )
            assert response.status_code == 201, f"Failed for type: {line_type}"

    @pytest.mark.asyncio
    async def test_invalid_line_type(self, client: AsyncClient):
        """Invalid line type should return 422."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/transit/lines",
            json={
                "world_id": TEST_WORLD_ID,
                "line_type": "tram",  # Invalid
                "name": "Invalid Line",
                "color": "#FF0000",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 422
