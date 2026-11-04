"""Tests for district CRUD endpoints."""

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


class TestCreateDistrict:
    """Tests for POST /worlds/{world_id}/districts endpoint."""

    @pytest.mark.asyncio
    async def test_create_district_success(self, client: AsyncClient):
        """Create district should return 201 with district data."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "residential",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "residential"
        assert data["world_id"] == TEST_WORLD_ID
        assert data["geometry"] == SAMPLE_GEOMETRY
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_district_with_all_fields(self, client: AsyncClient):
        """Create district with all optional fields."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "commercial",
                "name": "Downtown Commercial",
                "geometry": SAMPLE_GEOMETRY,
                "density": 3.5,
                "max_height": 20,
                "transit_access": True,
                "historic": True,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "commercial"
        assert data["name"] == "Downtown Commercial"
        assert data["density"] == 3.5
        assert data["max_height"] == 20
        assert data["transit_access"] is True
        assert data["historic"] is True

    @pytest.mark.asyncio
    async def test_create_district_applies_type_defaults(self, client: AsyncClient):
        """Create district should apply type-specific defaults."""
        # downtown has default density=7.0 and max_height=30
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "downtown",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "downtown"
        assert data["density"] == 7.0
        assert data["max_height"] == 30

    @pytest.mark.asyncio
    async def test_create_district_wrong_world(self, client: AsyncClient):
        """Create district should return 404 for non-existent world."""
        fake_world_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/worlds/{fake_world_id}/districts",
            json={
                "world_id": fake_world_id,
                "type": "park",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_district_forbidden_for_other_user(self, client: AsyncClient):
        """Create district should return 403 for another user's world."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "industrial",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403


class TestBulkCreateDistricts:
    """Tests for POST /worlds/{world_id}/districts/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_create_districts_success(self, client: AsyncClient):
        """Bulk create should return 201 with multiple districts."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts/bulk",
            json={
                "districts": [
                    {
                        "world_id": TEST_WORLD_ID,
                        "type": "residential",
                        "name": "Neighborhood 1",
                        "geometry": SAMPLE_GEOMETRY,
                    },
                    {
                        "world_id": TEST_WORLD_ID,
                        "type": "commercial",
                        "name": "Shopping Area",
                        "geometry": SAMPLE_GEOMETRY,
                    },
                    {
                        "world_id": TEST_WORLD_ID,
                        "type": "park",
                        "name": "Central Park",
                        "geometry": SAMPLE_GEOMETRY,
                    },
                ]
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 3
        names = [d["name"] for d in data]
        assert "Neighborhood 1" in names
        assert "Shopping Area" in names
        assert "Central Park" in names


class TestListDistricts:
    """Tests for GET /worlds/{world_id}/districts endpoint."""

    @pytest.mark.asyncio
    async def test_list_districts_empty(self, client: AsyncClient):
        """List districts should return empty list for world with no districts."""
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/districts",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_districts_returns_created(self, client: AsyncClient):
        """List districts should return all created districts."""
        # Create a district
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "residential",
                "name": "Test District",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # List districts
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/districts",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test District"

    @pytest.mark.asyncio
    async def test_list_districts_historic_only(self, client: AsyncClient):
        """List districts with historic_only filter."""
        # Create historic and non-historic districts
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "hospital",
                "name": "Historic Town Hall",
                "geometry": SAMPLE_GEOMETRY,
                "historic": True,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "residential",
                "name": "New Suburb",
                "geometry": SAMPLE_GEOMETRY,
                "historic": False,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # List all
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/districts",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert len(response.json()) == 2

        # List historic only
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/districts?historic_only=true",
            headers={"X-User-Id": TEST_USER_ID},
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Historic Town Hall"
        assert data[0]["historic"] is True


class TestGetDistrict:
    """Tests for GET /districts/{district_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_district_success(self, client: AsyncClient):
        """Get district should return district data."""
        # Create a district
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "downtown",
                "name": "Mixed District",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Get the district
        response = await client.get(
            f"/districts/{district_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Mixed District"
        assert data["type"] == "downtown"

    @pytest.mark.asyncio
    async def test_get_district_not_found(self, client: AsyncClient):
        """Get district should return 404 for non-existent district."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/districts/{fake_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_district_forbidden_for_other_user(self, client: AsyncClient):
        """Get district should return 403 for another user's district."""
        # Create district as user 1
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "airport",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Try to get as user 2
        response = await client.get(
            f"/districts/{district_id}",
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403


class TestUpdateDistrict:
    """Tests for PATCH /districts/{district_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_district_success(self, client: AsyncClient):
        """Update district should return updated data."""
        # Create a district
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "residential",
                "name": "Original Name",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Update the district
        response = await client.patch(
            f"/districts/{district_id}",
            json={"name": "Updated Name", "density": 2.5},
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["density"] == 2.5

    @pytest.mark.asyncio
    async def test_update_district_type(self, client: AsyncClient):
        """Update district type should succeed."""
        # Create a district
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "residential",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Update the type
        response = await client.patch(
            f"/districts/{district_id}",
            json={"type": "commercial"},
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert response.json()["type"] == "commercial"

    @pytest.mark.asyncio
    async def test_update_district_type_applies_new_defaults(self, client: AsyncClient):
        """CITY-297: Changing district type should update density/max_height to new type defaults."""
        # Create a residential district (default: density=3.0, max_height=8)
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "residential",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert create_response.status_code == 201
        data = create_response.json()
        district_id = data["id"]
        assert data["density"] == 3.0
        assert data["max_height"] == 8

        # Change type to downtown (default: density=7.0, max_height=30)
        response = await client.patch(
            f"/districts/{district_id}",
            json={"type": "downtown"},
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "downtown"
        assert data["density"] == 7.0
        assert data["max_height"] == 30

    @pytest.mark.asyncio
    async def test_update_district_type_preserves_explicit_density(self, client: AsyncClient):
        """CITY-297: Changing type with explicit density should keep the provided density."""
        # Create a residential district
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "residential",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Change type to downtown but provide explicit density
        response = await client.patch(
            f"/districts/{district_id}",
            json={"type": "downtown", "density": 5.0},
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "downtown"
        assert data["density"] == 5.0  # Explicit value preserved
        assert data["max_height"] == 30  # Default applied since not explicitly set

    @pytest.mark.asyncio
    async def test_update_district_not_found(self, client: AsyncClient):
        """Update district should return 404 for non-existent district."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"/districts/{fake_id}",
            json={"name": "New Name"},
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_district_forbidden_for_other_user(self, client: AsyncClient):
        """Update district should return 403 for another user's district."""
        # Create district as user 1
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "park",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Try to update as user 2
        response = await client.patch(
            f"/districts/{district_id}",
            json={"name": "Hacked"},
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403


class TestDeleteDistrict:
    """Tests for DELETE /districts/{district_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_district_success(self, client: AsyncClient):
        """Delete district should return 204."""
        # Create a district
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "industrial",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Delete the district
        response = await client.delete(
            f"/districts/{district_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/districts/{district_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_district_not_found(self, client: AsyncClient):
        """Delete district should return 404 for non-existent district."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/districts/{fake_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_district_forbidden_for_other_user(self, client: AsyncClient):
        """Delete district should return 403 for another user's district."""
        # Create district as user 1
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "hospital",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        district_id = create_response.json()["id"]

        # Try to delete as user 2
        response = await client.delete(
            f"/districts/{district_id}",
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403

        # Verify it still exists
        get_response = await client.get(
            f"/districts/{district_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert get_response.status_code == 200


class TestDeleteAllDistricts:
    """Tests for DELETE /worlds/{world_id}/districts endpoint."""

    @pytest.mark.asyncio
    async def test_delete_all_districts_success(self, client: AsyncClient):
        """Delete all districts should return 204."""
        # Create multiple districts
        for i in range(3):
            await client.post(
                f"/worlds/{TEST_WORLD_ID}/districts",
                json={
                    "world_id": TEST_WORLD_ID,
                    "type": "residential",
                    "name": f"District {i}",
                    "geometry": SAMPLE_GEOMETRY,
                },
                headers={"X-User-Id": TEST_USER_ID},
            )

        # Verify they exist
        list_response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/districts",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert len(list_response.json()) == 3

        # Delete all
        response = await client.delete(
            f"/worlds/{TEST_WORLD_ID}/districts",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify all are gone
        list_response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/districts",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert list_response.json() == []

    @pytest.mark.asyncio
    async def test_delete_all_districts_forbidden(self, client: AsyncClient):
        """Delete all districts should return 403 for another user's world."""
        response = await client.delete(
            f"/worlds/{TEST_WORLD_ID}/districts",
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403


class TestDistrictTypes:
    """Tests for different district types and their defaults."""

    @pytest.mark.asyncio
    async def test_all_district_types_valid(self, client: AsyncClient):
        """All district types should be valid."""
        district_types = [
            "residential",
            "downtown",
            "commercial",
            "industrial",
            "hospital",
            "university",
            "k12",
            "park",
            "airport",
        ]
        for dtype in district_types:
            response = await client.post(
                f"/worlds/{TEST_WORLD_ID}/districts",
                json={
                    "world_id": TEST_WORLD_ID,
                    "type": dtype,
                    "geometry": SAMPLE_GEOMETRY,
                },
                headers={"X-User-Id": TEST_USER_ID},
            )
            assert response.status_code == 201, f"Failed for type: {dtype}"
            assert response.json()["type"] == dtype

    @pytest.mark.asyncio
    async def test_invalid_district_type(self, client: AsyncClient):
        """Invalid district type should return 422."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={
                "world_id": TEST_WORLD_ID,
                "type": "invalid_type",
                "geometry": SAMPLE_GEOMETRY,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 422


class TestDeleteDistrictCleansUpRoads:
    """CITY-298: Deleting a district should remove associated road edges and orphaned nodes."""

    @pytest.mark.asyncio
    async def test_delete_district_removes_road_edges(self, client: AsyncClient):
        """Road edges belonging to a deleted district should be removed."""
        headers = {"X-User-Id": TEST_USER_ID}

        # Create a district
        district_resp = await client.post(
            f"/worlds/{TEST_WORLD_ID}/districts",
            json={"world_id": TEST_WORLD_ID, "type": "residential", "geometry": SAMPLE_GEOMETRY},
            headers=headers,
        )
        assert district_resp.status_code == 201
        district_id = district_resp.json()["id"]

        # Create two road nodes
        node1_resp = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 10, "y": 10},
                "node_type": "intersection",
            },
            headers=headers,
        )
        assert node1_resp.status_code == 201
        node1_id = node1_resp.json()["id"]

        node2_resp = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 50, "y": 50},
                "node_type": "intersection",
            },
            headers=headers,
        )
        assert node2_resp.status_code == 201
        node2_id = node2_resp.json()["id"]

        # Create a road edge linked to the district
        edge_resp = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "local",
                "district_id": district_id,
            },
            headers=headers,
        )
        assert edge_resp.status_code == 201
        edge_id = edge_resp.json()["id"]

        # Verify the edge exists
        edge_get = await client.get(f"/road-edges/{edge_id}", headers=headers)
        assert edge_get.status_code == 200

        # Delete the district
        delete_resp = await client.delete(f"/districts/{district_id}", headers=headers)
        assert delete_resp.status_code == 204

        # Verify the edge is gone
        edge_get2 = await client.get(f"/road-edges/{edge_id}", headers=headers)
        assert edge_get2.status_code == 404

        # Verify orphaned nodes are also cleaned up
        node1_get = await client.get(f"/road-nodes/{node1_id}", headers=headers)
        assert node1_get.status_code == 404

        node2_get = await client.get(f"/road-nodes/{node2_id}", headers=headers)
        assert node2_get.status_code == 404
