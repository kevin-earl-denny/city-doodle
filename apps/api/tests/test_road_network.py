"""Tests for road network CRUD endpoints."""

import os
import uuid

import pytest
from httpx import AsyncClient

# Test user IDs
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"

# The test world created by conftest.py
TEST_WORLD_ID = "00000000-0000-0000-0000-000000000010"

# Mirrors conftest.py: SQLite unless TEST_DATABASE_URL points elsewhere.
IS_SQLITE = os.environ.get("TEST_DATABASE_URL", "sqlite").startswith("sqlite")


class TestRoadNodes:
    """Tests for road node endpoints."""

    @pytest.mark.asyncio
    async def test_create_road_node_success(self, client: AsyncClient):
        """Test creating a road node."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 200.0},
                "node_type": "intersection",
                "name": "Test Intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["position"]["x"] == 100.0
        assert data["position"]["y"] == 200.0
        assert data["node_type"] == "intersection"
        assert data["name"] == "Test Intersection"
        assert "id" in data
        assert data["world_id"] == TEST_WORLD_ID

    @pytest.mark.asyncio
    async def test_create_road_node_endpoint_type(self, client: AsyncClient):
        """Test creating an endpoint node."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 50.0, "y": 50.0},
                "node_type": "endpoint",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        assert response.json()["node_type"] == "endpoint"

    @pytest.mark.asyncio
    async def test_list_road_nodes_empty(self, client: AsyncClient):
        """Test listing nodes when none exist."""
        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_road_nodes_with_nodes(self, client: AsyncClient):
        """Test listing nodes after creating some."""
        # Create two nodes
        for i in range(2):
            await client.post(
                f"/worlds/{TEST_WORLD_ID}/road-nodes",
                json={
                    "world_id": TEST_WORLD_ID,
                    "position": {"x": float(i * 100), "y": float(i * 100)},
                    "node_type": "intersection",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    @pytest.mark.asyncio
    async def test_get_road_node_success(self, client: AsyncClient):
        """Test getting a node by ID."""
        # Create a node
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 200.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        node_id = create_response.json()["id"]

        response = await client.get(
            f"/road-nodes/{node_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert response.json()["id"] == node_id

    @pytest.mark.asyncio
    async def test_get_road_node_connected_edges_populated(self, client: AsyncClient):
        """Test that connected_edges is populated when a node has edges."""
        # Create two nodes
        node1_resp = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 0.0, "y": 0.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        node1_id = node1_resp.json()["id"]

        node2_resp = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 0.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        node2_id = node2_resp.json()["id"]

        # Create an edge between them
        edge_resp = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        edge_id = edge_resp.json()["id"]

        # Fetch node1 and verify connected_edges contains the edge
        response = await client.get(
            f"/road-nodes/{node1_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert edge_id in data["connected_edges"]

        # Fetch node2 and verify it also has the edge
        response = await client.get(
            f"/road-nodes/{node2_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert edge_id in data["connected_edges"]

    @pytest.mark.asyncio
    async def test_get_road_node_not_found(self, client: AsyncClient):
        """Test getting a non-existent node."""
        response = await client.get(
            f"/road-nodes/{uuid.uuid4()}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_road_node_success(self, client: AsyncClient):
        """Test updating a node."""
        # Create a node
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 200.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        node_id = create_response.json()["id"]

        # Update it
        response = await client.patch(
            f"/road-nodes/{node_id}",
            json={
                "position": {"x": 150.0, "y": 250.0},
                "name": "Updated Name",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["position"]["x"] == 150.0
        assert data["position"]["y"] == 250.0
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_road_node_success(self, client: AsyncClient):
        """Test deleting a node."""
        # Create a node
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 200.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        node_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/road-nodes/{node_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/road-nodes/{node_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_road_nodes_bulk(self, client: AsyncClient):
        """Test creating multiple nodes at once."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes/bulk",
            json={
                "nodes": [
                    {
                        "world_id": TEST_WORLD_ID,
                        "position": {"x": 0.0, "y": 0.0},
                        "node_type": "intersection",
                    },
                    {
                        "world_id": TEST_WORLD_ID,
                        "position": {"x": 100.0, "y": 0.0},
                        "node_type": "intersection",
                    },
                    {
                        "world_id": TEST_WORLD_ID,
                        "position": {"x": 100.0, "y": 100.0},
                        "node_type": "endpoint",
                    },
                ]
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        assert len(response.json()) == 3


class TestRoadEdges:
    """Tests for road edge endpoints."""

    async def _create_nodes(self, client: AsyncClient) -> tuple[str, str]:
        """Helper to create two nodes and return their IDs."""
        node1_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 0.0, "y": 0.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        node2_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 0.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        return node1_response.json()["id"], node2_response.json()["id"]

    @pytest.mark.asyncio
    async def test_create_road_edge_success(self, client: AsyncClient):
        """Test creating a road edge."""
        node1_id, node2_id = await self._create_nodes(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "local",
                "name": "Main Street",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["from_node_id"] == node1_id
        assert data["to_node_id"] == node2_id
        assert data["road_class"] == "local"
        assert data["name"] == "Main Street"
        assert data["length_meters"] == 100.0  # Distance from (0,0) to (100,0)
        assert data["lanes"] == 2  # Default for local roads

    @pytest.mark.asyncio
    async def test_create_road_edge_with_geometry(self, client: AsyncClient):
        """Test creating an edge with intermediate points."""
        node1_id, node2_id = await self._create_nodes(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "collector",
                "geometry": [
                    {"x": 25.0, "y": 10.0},
                    {"x": 75.0, "y": 10.0},
                ],
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["geometry"]) == 2
        # Length should be longer due to curve
        assert data["length_meters"] > 100.0

    @pytest.mark.asyncio
    async def test_create_road_edge_arterial_defaults(self, client: AsyncClient):
        """Test that arterial roads get correct defaults."""
        node1_id, node2_id = await self._create_nodes(client)

        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "arterial",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["speed_limit"] == 60  # Default for arterial
        assert data["lanes"] == 4  # Default for arterial

    @pytest.mark.asyncio
    async def test_create_road_edge_invalid_nodes(self, client: AsyncClient):
        """Test creating an edge with non-existent nodes."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": str(uuid.uuid4()),
                "to_node_id": str(uuid.uuid4()),
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_road_edges(self, client: AsyncClient):
        """Test listing road edges."""
        node1_id, node2_id = await self._create_nodes(client)

        # Create an edge
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    @pytest.mark.asyncio
    async def test_update_road_edge(self, client: AsyncClient):
        """Test updating a road edge."""
        node1_id, node2_id = await self._create_nodes(client)

        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        edge_id = create_response.json()["id"]

        response = await client.patch(
            f"/road-edges/{edge_id}",
            json={
                "road_class": "arterial",
                "name": "Main Avenue",
                "lanes": 6,
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["road_class"] == "arterial"
        assert data["name"] == "Main Avenue"
        assert data["lanes"] == 6

    @pytest.mark.asyncio
    async def test_delete_road_edge(self, client: AsyncClient):
        """Test deleting a road edge."""
        node1_id, node2_id = await self._create_nodes(client)

        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        edge_id = create_response.json()["id"]

        response = await client.delete(
            f"/road-edges/{edge_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/road-edges/{edge_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_edges_for_node(self, client: AsyncClient):
        """Test listing edges connected to a specific node."""
        # Create three nodes
        nodes = []
        for i in range(3):
            resp = await client.post(
                f"/worlds/{TEST_WORLD_ID}/road-nodes",
                json={
                    "world_id": TEST_WORLD_ID,
                    "position": {"x": float(i * 100), "y": 0.0},
                    "node_type": "intersection",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )
            nodes.append(resp.json()["id"])

        # Create edges: node0 -> node1, node1 -> node2
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": nodes[0],
                "to_node_id": nodes[1],
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": nodes[1],
                "to_node_id": nodes[2],
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        # node1 should have 2 edges
        response = await client.get(
            f"/road-nodes/{nodes[1]}/edges",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

        # node0 should have 1 edge
        response = await client.get(
            f"/road-nodes/{nodes[0]}/edges",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    @pytest.mark.asyncio
    @pytest.mark.skipif(IS_SQLITE, reason="CITY-673: SQLite tests don't enforce ON DELETE CASCADE")
    async def test_deleting_node_cascades_to_edges(self, client: AsyncClient):
        """Test that deleting a node also deletes connected edges."""
        node1_id, node2_id = await self._create_nodes(client)

        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": node1_id,
                "to_node_id": node2_id,
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        edge_id = create_response.json()["id"]

        # Delete node1
        await client.delete(
            f"/road-nodes/{node1_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )

        # Edge should also be gone
        get_response = await client.get(
            f"/road-edges/{edge_id}",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert get_response.status_code == 404


class TestRoadNetwork:
    """Tests for road network aggregate endpoints."""

    @pytest.mark.asyncio
    async def test_get_road_network(self, client: AsyncClient):
        """Test getting the complete road network."""
        # Create some nodes and edges
        nodes = []
        for i in range(3):
            resp = await client.post(
                f"/worlds/{TEST_WORLD_ID}/road-nodes",
                json={
                    "world_id": TEST_WORLD_ID,
                    "position": {"x": float(i * 100), "y": 0.0},
                    "node_type": "intersection",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )
            nodes.append(resp.json()["id"])

        for i in range(2):
            await client.post(
                f"/worlds/{TEST_WORLD_ID}/road-edges",
                json={
                    "world_id": TEST_WORLD_ID,
                    "from_node_id": nodes[i],
                    "to_node_id": nodes[i + 1],
                    "road_class": "local",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/road-network",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["world_id"] == TEST_WORLD_ID
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 2

    @pytest.mark.asyncio
    async def test_get_road_network_stats(self, client: AsyncClient):
        """Test getting network statistics."""
        # Create a small connected network
        nodes = []
        for i in range(3):
            resp = await client.post(
                f"/worlds/{TEST_WORLD_ID}/road-nodes",
                json={
                    "world_id": TEST_WORLD_ID,
                    "position": {"x": float(i * 100), "y": 0.0},
                    "node_type": "intersection",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )
            nodes.append(resp.json()["id"])

        # Create edges with different road classes
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": nodes[0],
                "to_node_id": nodes[1],
                "road_class": "arterial",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-edges",
            json={
                "world_id": TEST_WORLD_ID,
                "from_node_id": nodes[1],
                "to_node_id": nodes[2],
                "road_class": "local",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/road-network/stats",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 3
        assert data["total_edges"] == 2
        assert data["total_length_meters"] == 200.0
        assert data["edges_by_class"]["arterial"] == 1
        assert data["edges_by_class"]["local"] == 1
        assert data["connectivity_score"] == 1.0  # Fully connected

    @pytest.mark.asyncio
    async def test_connectivity_score_disconnected(self, client: AsyncClient):
        """Test connectivity score with disconnected components."""
        # Create two nodes with no edges (2 components)
        for i in range(2):
            await client.post(
                f"/worlds/{TEST_WORLD_ID}/road-nodes",
                json={
                    "world_id": TEST_WORLD_ID,
                    "position": {"x": float(i * 100), "y": 0.0},
                    "node_type": "intersection",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )

        response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/road-network/stats",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connectivity_score"] == 0.5  # 2 components = 1/2

    @pytest.mark.asyncio
    async def test_clear_road_network(self, client: AsyncClient):
        """Test clearing all road data from a world."""
        # Create some nodes
        for i in range(2):
            await client.post(
                f"/worlds/{TEST_WORLD_ID}/road-nodes",
                json={
                    "world_id": TEST_WORLD_ID,
                    "position": {"x": float(i * 100), "y": 0.0},
                    "node_type": "intersection",
                },
                headers={"X-User-Id": TEST_USER_ID},
            )

        # Clear the network
        response = await client.delete(
            f"/worlds/{TEST_WORLD_ID}/road-network",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 204

        # Verify it's empty
        list_response = await client.get(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert list_response.status_code == 200
        assert list_response.json() == []


class TestRoadNetworkAuth:
    """Tests for road network authorization."""

    @pytest.mark.asyncio
    async def test_create_node_forbidden_other_user(self, client: AsyncClient):
        """Test that users can't create nodes in other users' worlds."""
        response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 200.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_node_forbidden_other_user(self, client: AsyncClient):
        """Test that users can't access nodes in other users' worlds."""
        # Create a node as the owner
        create_response = await client.post(
            f"/worlds/{TEST_WORLD_ID}/road-nodes",
            json={
                "world_id": TEST_WORLD_ID,
                "position": {"x": 100.0, "y": 200.0},
                "node_type": "intersection",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        node_id = create_response.json()["id"]

        # Try to access as another user
        response = await client.get(
            f"/road-nodes/{node_id}",
            headers={"X-User-Id": OTHER_USER_ID},
        )
        assert response.status_code == 403
