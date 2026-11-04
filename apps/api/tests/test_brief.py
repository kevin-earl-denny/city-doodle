"""Tests for the World Brief compiler, prompt and endpoint (CITY-659)."""

from uuid import UUID

import pytest
from httpx import AsyncClient

from city_api.brief import service
from city_api.brief.compiler import compile_brief
from city_api.brief.prompt import SYSTEM_PROMPT, build_user_message
from city_api.brief.schema import WorldBrief

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def make_brief(**overrides) -> WorldBrief:
    data = {
        "archetype": "bay_harbor",
        "water_side": "south_east",
        "river": {"count": 1, "course": "meandering", "axis": "north_south"},
        "relief": "hilly",
        "coast": "varied",
        "growth_story": "hill_town",
        "sliders": {
            "grid_organic": 0.85,
            "sprawl_compact": 0.85,
            "transit_car": 0.3,
            "historic_modern": 0.25,
            "block_size_meters": 60,
            "district_size_meters": 1200,
        },
        "name": "Porto Gelo",
        "name_suggestions": ["Port Wren", "Gullhaven", "New Calloway", "Saltmarsh"],
        "founding_year": 1702,
        "founding_story": "Fishermen settled the steep west bank where the Wren meets the bay.",
        "feels_like": ["Lisbon", "Porto"],
        "legend": {
            "water": "Bay opens to the south-east",
            "river": "One river, winding in from the north",
            "ground": "Hilly west bank, flat east bank",
            "streets": "Hill Town, then Boomtown Grid",
        },
        "unsupported": ["Colder climate: I can't draw weather yet."],
    }
    data.update(overrides)
    return WorldBrief.model_validate(data)


class TestCompiler:
    def test_maps_brief_to_settings(self):
        brief, settings, warnings = compile_brief(make_brief())
        assert settings.geographic_setting == "bay_harbor"
        assert settings.water_direction_deg == 45.0  # south-east: 0=E, 90=S
        assert settings.river_axis_deg is None  # only river valleys get an axis
        assert settings.relief == "hilly"
        assert settings.block_size_meters == 60
        assert settings.grid_organic == 0.85
        assert warnings == []

    @pytest.mark.parametrize(
        ("side", "deg"),
        [("east", 0.0), ("south", 90.0), ("west", 180.0), ("north", 270.0), ("north_east", 315.0)],
    )
    def test_compass_convention_matches_engine(self, side, deg):
        _, settings, _ = compile_brief(make_brief(archetype="coastal", water_side=side))
        assert settings.water_direction_deg == deg

    def test_river_valley_gets_axis_and_no_water_side(self):
        brief, settings, warnings = compile_brief(
            make_brief(archetype="river_valley", water_side="east")
        )
        assert settings.river_axis_deg == 90.0
        assert settings.water_direction_deg is None
        assert brief.water_side == "none"
        assert warnings

    def test_island_forces_water_all_around(self):
        brief, settings, warnings = compile_brief(make_brief(archetype="island", water_side="west"))
        assert brief.water_side == "all_around"
        assert settings.water_direction_deg is None
        assert warnings

    def test_clamps_out_of_range_sliders(self):
        raw = make_brief()
        raw.sliders.block_size_meters = 22  # Venice-sized, below the engine minimum
        raw.sliders.district_size_meters = 9000
        raw.sliders.grid_organic = 1.4
        _, settings, _ = compile_brief(raw)
        assert settings.block_size_meters == 50
        assert settings.district_size_meters == 6000
        assert settings.grid_organic == 1.0

    def test_no_river_clears_axis(self):
        brief, _, _ = compile_brief(
            make_brief(river={"count": 0, "course": "meandering", "axis": "east_west"})
        )
        assert brief.river.course == "none"
        assert brief.river.axis is None


class TestPrompt:
    def test_system_prompt_is_static_and_includes_corpus(self):
        assert "engine-capabilities" in SYSTEM_PROMPT
        assert "siting-and-archetypes" in SYSTEM_PROMPT
        assert "urban-morphology" in SYSTEM_PROMPT

    def test_user_message_wraps_text_and_previous_brief(self):
        msg = build_user_message("a hilly port", make_brief(), "move the river east")
        assert "<player_description>\na hilly port" in msg
        assert "<current_brief>" in msg
        assert "<change_request>\nmove the river east" in msg


class TestEndpoint:
    @pytest.mark.asyncio
    async def test_returns_brief_and_compiled_settings(self, client: AsyncClient, monkeypatch):
        async def fake_generate(request, user_id):
            assert user_id == UUID(TEST_USER_ID)
            return make_brief()

        monkeypatch.setattr("city_api.routes.brief.generate_brief", fake_generate)
        response = await client.post(
            "/worlds/brief",
            json={"prompt": "A hilly port where a river spills into a sheltered bay"},
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["brief"]["name"] == "Porto Gelo"
        assert data["settings"]["geographic_setting"] == "bay_harbor"
        assert data["settings"]["water_direction_deg"] == 45.0

    @pytest.mark.asyncio
    async def test_503_when_not_configured(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(service.settings, "anthropic_api_key", None)
        response = await client.post(
            "/worlds/brief",
            json={"prompt": "an island town"},
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_rejects_empty_prompt(self, client: AsyncClient):
        response = await client.post(
            "/worlds/brief", json={"prompt": ""}, headers={"X-User-Id": TEST_USER_ID}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rate_limit(self, monkeypatch):
        monkeypatch.setattr(service.settings, "brief_rate_limit_per_minute", 2)
        user = UUID("00000000-0000-0000-0000-0000000000aa")
        service._recent.pop(user, None)
        service._check_rate_limit(user)
        service._check_rate_limit(user)
        with pytest.raises(service.BriefRateLimited):
            service._check_rate_limit(user)


def test_created_world_keeps_brief_hints():
    """WorldSettings accepts the new optional fields, and defaults leave them unset."""
    from city_api.schemas.world import WorldSettings

    assert WorldSettings().water_direction_deg is None
    s = WorldSettings(water_direction_deg=90.0, river_axis_deg=45.0, relief="flat")
    assert s.relief == "flat"
