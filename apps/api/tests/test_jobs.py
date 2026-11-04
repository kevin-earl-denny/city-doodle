"""Tests for job endpoints."""

from uuid import uuid4

import pytest

from city_api.repositories import job as job_repo
from city_api.schemas import JobStatus

# Fixed test user IDs matching those created in conftest.py
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"

# Fixed test tile ID matching the one created in conftest.py
TEST_TILE_ID = "00000000-0000-0000-0000-000000000020"


class TestCreateJob:
    """Tests for POST /jobs."""

    @pytest.mark.asyncio
    async def test_create_job_success(self, client):
        """Successfully create a job."""
        user_id = TEST_USER_ID

        response = await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "terrain_generation"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "terrain_generation"
        assert data["status"] == "pending"
        assert data["user_id"] == user_id
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_job_with_tile_id(self, client):
        """Create a job with a target tile."""
        user_id = TEST_USER_ID
        tile_id = TEST_TILE_ID

        response = await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={
                "type": "growth_simulation",
                "tile_id": tile_id,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["tile_id"] == tile_id

    @pytest.mark.asyncio
    async def test_create_job_with_params(self, client):
        """Create a job with custom parameters."""
        user_id = TEST_USER_ID

        response = await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={
                "type": "export_png",
                "params": {"resolution": 1920, "format": "png"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["params"]["resolution"] == 1920
        assert data["params"]["format"] == "png"

    @pytest.mark.asyncio
    async def test_create_job_invalid_type(self, client):
        """Fail to create job with invalid type."""
        user_id = TEST_USER_ID

        response = await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "invalid_type"},
        )

        assert response.status_code == 422


class TestListJobs:
    """Tests for GET /jobs."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, client):
        """List jobs when none exist."""
        user_id = TEST_USER_ID

        response = await client.get(
            "/jobs",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_jobs_returns_user_jobs(self, client):
        """List jobs returns only current user's jobs."""
        user_id = TEST_USER_ID

        # Create some jobs
        await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "terrain_generation"},
        )
        await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "export_png"},
        )

        response = await client.get(
            "/jobs",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_excludes_other_users(self, client):
        """List jobs excludes other users' jobs."""
        user1 = TEST_USER_ID
        user2 = OTHER_USER_ID

        # User 1 creates a job
        await client.post(
            "/jobs",
            headers={"X-User-ID": user1},
            json={"type": "terrain_generation"},
        )

        # User 2 lists jobs
        response = await client.get(
            "/jobs",
            headers={"X-User-ID": user2},
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_tile(self, client):
        """Filter jobs by tile ID."""
        user_id = TEST_USER_ID
        tile_id = TEST_TILE_ID

        # Create jobs with and without tile
        await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "terrain_generation", "tile_id": tile_id},
        )
        await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "export_png"},
        )

        response = await client.get(
            f"/jobs?tile_id={tile_id}",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["tile_id"] == tile_id


class TestGetJob:
    """Tests for GET /jobs/{job_id}."""

    @pytest.mark.asyncio
    async def test_get_job_success(self, client):
        """Get a job by ID."""
        user_id = TEST_USER_ID

        # Create a job
        create_response = await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "terrain_generation"},
        )
        job_id = create_response.json()["id"]

        # Get the job
        response = await client.get(
            f"/jobs/{job_id}",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client):
        """Get a non-existent job returns 404."""
        user_id = TEST_USER_ID
        job_id = uuid4()

        response = await client.get(
            f"/jobs/{job_id}",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_job_wrong_user(self, client):
        """Cannot access another user's job."""
        user1 = TEST_USER_ID
        user2 = OTHER_USER_ID

        # User 1 creates a job
        create_response = await client.post(
            "/jobs",
            headers={"X-User-ID": user1},
            json={"type": "terrain_generation"},
        )
        job_id = create_response.json()["id"]

        # User 2 tries to access it
        response = await client.get(
            f"/jobs/{job_id}",
            headers={"X-User-ID": user2},
        )

        assert response.status_code == 403
        assert "another user" in response.json()["detail"]


class TestCancelJob:
    """Tests for POST /jobs/{job_id}/cancel."""

    @pytest.mark.asyncio
    async def test_cancel_job_success(self, client):
        """Cancel a pending job."""
        user_id = TEST_USER_ID

        # Create a job
        create_response = await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "terrain_generation"},
        )
        job_id = create_response.json()["id"]

        # Cancel the job
        response = await client.post(
            f"/jobs/{job_id}/cancel",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, client):
        """Cancel a non-existent job returns 404."""
        user_id = TEST_USER_ID
        job_id = uuid4()

        response = await client.post(
            f"/jobs/{job_id}/cancel",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_job_wrong_user(self, client):
        """Cannot cancel another user's job."""
        user1 = TEST_USER_ID
        user2 = OTHER_USER_ID

        # User 1 creates a job
        create_response = await client.post(
            "/jobs",
            headers={"X-User-ID": user1},
            json={"type": "terrain_generation"},
        )
        job_id = create_response.json()["id"]

        # User 2 tries to cancel
        response = await client.post(
            f"/jobs/{job_id}/cancel",
            headers={"X-User-ID": user2},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Requires db_session fixture which has event loop issues with client fixture in PostgreSQL CI"
    )
    async def test_cancel_running_job_fails(self, client, db_session):
        """Cannot cancel a running job."""
        user_id = TEST_USER_ID

        # Create a job
        create_response = await client.post(
            "/jobs",
            headers={"X-User-ID": user_id},
            json={"type": "terrain_generation"},
        )
        job_id = create_response.json()["id"]

        # Set job to running via repository
        from uuid import UUID

        await job_repo.update_job_status(db_session, UUID(job_id), JobStatus.RUNNING)

        # Try to cancel
        response = await client.post(
            f"/jobs/{job_id}/cancel",
            headers={"X-User-ID": user_id},
        )

        assert response.status_code == 409
