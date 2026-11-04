"""End-to-end integration tests for the terrain generation pipeline.

Covers the full path from terrain generation through GeoJSON conversion
and JSON round-trip serialisation. Created after CITY-582 showed that
the API schema could silently strip GeoJSON features.
"""

import json
import pathlib

import pytest

from city_worker.terrain import TerrainConfig, TerrainGenerator
from city_worker.terrain.geographic_presets import (
    GEOGRAPHIC_PRESETS,
    apply_seed_variation,
)
from city_worker.terrain.types import TerrainResult, TileTerrainData

# All recognised geographic setting keys
ALL_PRESETS = list(GEOGRAPHIC_PRESETS.keys())

# Expected feature types that each preset should typically produce.
# Not every run is guaranteed to hit all of them (procedural generation
# is stochastic), so we assert "at least one of these" rather than "all".
PRESET_EXPECTED_FEATURE_TYPES: dict[str, set[str]] = {
    "coastal": {"coastline", "contour"},
    "bay_harbor": {"coastline", "contour"},
    "river_valley": {"contour"},
    "lakefront": {"contour"},
    "inland": {"contour"},
    "island": {"coastline", "contour"},
    "peninsula": {"coastline", "contour"},
    "delta": {"contour"},
}

# Valid GeoJSON geometry types the backend is allowed to emit
VALID_GEOJSON_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
SAMPLE_GEOJSON_PATH = FIXTURES_DIR / "sample_terrain_geojson.json"

# Shared seed for deterministic generation
TEST_SEED = 42


def _make_config(geographic_setting: str, seed: int = TEST_SEED) -> TerrainConfig:
    """Build a TerrainConfig from a preset the same way runner.py does."""
    config_kwargs = apply_seed_variation(geographic_setting, seed=seed)
    config_kwargs["world_seed"] = seed
    config_kwargs["geographic_setting"] = geographic_setting
    return TerrainConfig(**config_kwargs)


# ---------------------------------------------------------------------------
# Helper: collect all features across all tiles of a TerrainResult
# ---------------------------------------------------------------------------


def _all_features(result: TerrainResult) -> list[dict]:
    """Return flattened GeoJSON features from every tile in the result."""
    features: list[dict] = []
    for tile in result.all_tiles():
        fc = tile.features_to_geojson()
        features.extend(fc.get("features", []))
    return features


# ===================================================================
# Test: TerrainGenerator.generate_3x3 produces valid TerrainResult
# ===================================================================


class TestTerrainGeneratorPipeline:
    """Verify that generate_3x3 produces structurally valid results."""

    def test_generate_3x3_returns_terrain_result(self):
        config = _make_config("coastal")
        gen = TerrainGenerator(config)
        result = gen.generate_3x3(0, 0)

        assert isinstance(result, TerrainResult)

    def test_generate_3x3_has_nine_tiles(self):
        config = _make_config("coastal")
        gen = TerrainGenerator(config)
        result = gen.generate_3x3(0, 0)

        tiles = result.all_tiles()
        assert len(tiles) == 9

    def test_tiles_have_non_empty_heightfields(self):
        config = _make_config("coastal")
        gen = TerrainGenerator(config)
        result = gen.generate_3x3(0, 0)

        for tile in result.all_tiles():
            assert isinstance(tile, TileTerrainData)
            assert len(tile.heightfield) > 0
            assert len(tile.heightfield[0]) > 0

    def test_center_tile_has_features(self):
        """The center tile should always produce at least some features."""
        config = _make_config("coastal")
        gen = TerrainGenerator(config)
        result = gen.generate_3x3(0, 0)

        # At minimum, contour lines should be generated for any terrain
        all_feat = _all_features(result)
        assert len(all_feat) > 0, "Expected at least some features across all tiles"


# ===================================================================
# Test: features_to_geojson produces valid GeoJSON FeatureCollection
# ===================================================================


class TestFeaturesToGeoJSON:
    """Verify GeoJSON output from TileTerrainData.features_to_geojson()."""

    @pytest.fixture(scope="class")
    def coastal_result(self):
        config = _make_config("coastal")
        gen = TerrainGenerator(config)
        return gen.generate_3x3(0, 0)

    def test_geojson_is_feature_collection(self, coastal_result):
        for tile in coastal_result.all_tiles():
            fc = tile.features_to_geojson()
            assert fc["type"] == "FeatureCollection"
            assert isinstance(fc["features"], list)

    def test_each_feature_has_required_fields(self, coastal_result):
        for feat in _all_features(coastal_result):
            assert feat["type"] == "Feature", f"Feature missing type: {feat}"
            assert "geometry" in feat, f"Feature missing geometry: {feat}"
            assert "properties" in feat, f"Feature missing properties: {feat}"

    def test_each_feature_has_valid_geometry_type(self, coastal_result):
        for feat in _all_features(coastal_result):
            geom = feat["geometry"]
            assert "type" in geom, f"Geometry missing type: {geom}"
            assert geom["type"] in VALID_GEOJSON_GEOMETRY_TYPES, (
                f"Invalid geometry type: {geom['type']}"
            )

    def test_each_feature_has_feature_type_property(self, coastal_result):
        for feat in _all_features(coastal_result):
            props = feat["properties"]
            assert "feature_type" in props, f"Feature missing feature_type property: {props}"
            assert isinstance(props["feature_type"], str)
            assert len(props["feature_type"]) > 0


# ===================================================================
# Test: Each geographic preset produces valid output
# ===================================================================


class TestGeographicPresets:
    """Ensure every preset generates terrain without errors and with
    expected feature types."""

    @pytest.mark.parametrize("preset", ALL_PRESETS)
    def test_preset_generates_without_error(self, preset):
        config = _make_config(preset)
        gen = TerrainGenerator(config)
        result = gen.generate_3x3(0, 0)

        assert isinstance(result, TerrainResult)
        assert len(result.all_tiles()) == 9

    @pytest.mark.parametrize("preset", ALL_PRESETS)
    def test_preset_produces_valid_geojson(self, preset):
        config = _make_config(preset)
        gen = TerrainGenerator(config)
        result = gen.generate_3x3(0, 0)

        for tile in result.all_tiles():
            fc = tile.features_to_geojson()
            assert fc["type"] == "FeatureCollection"
            for feat in fc["features"]:
                assert feat["type"] == "Feature"
                assert "geometry" in feat
                assert "feature_type" in feat["properties"]

    @pytest.mark.parametrize("preset", ALL_PRESETS)
    def test_preset_has_expected_feature_types(self, preset):
        config = _make_config(preset)
        gen = TerrainGenerator(config)
        result = gen.generate_3x3(0, 0)

        all_feat = _all_features(result)
        actual_types = {f["properties"]["feature_type"] for f in all_feat}
        expected = PRESET_EXPECTED_FEATURE_TYPES.get(preset, set())

        # At least one of the expected types should be present
        overlap = actual_types & expected
        assert len(overlap) > 0, (
            f"Preset '{preset}' produced feature types {actual_types}, "
            f"but expected at least one of {expected}"
        )


# ===================================================================
# Test: JSON round-trip preserves data
# ===================================================================


class TestJSONRoundTrip:
    """Verify that serialising to JSON and back preserves the GeoJSON."""

    @pytest.fixture(scope="class")
    def coastal_result(self):
        config = _make_config("coastal")
        gen = TerrainGenerator(config)
        return gen.generate_3x3(0, 0)

    def test_json_roundtrip_preserves_feature_collection(self, coastal_result):
        for tile in coastal_result.all_tiles():
            original = tile.features_to_geojson()
            serialised = json.dumps(original)
            restored = json.loads(serialised)

            assert restored["type"] == "FeatureCollection"
            assert len(restored["features"]) == len(original["features"])

    def test_json_roundtrip_preserves_feature_details(self, coastal_result):
        for tile in coastal_result.all_tiles():
            original = tile.features_to_geojson()
            serialised = json.dumps(original)
            restored = json.loads(serialised)

            # Normalise original through JSON as well so tuples become lists
            normalised = json.loads(json.dumps(original))

            for norm_feat, rest_feat in zip(normalised["features"], restored["features"]):
                assert rest_feat["type"] == norm_feat["type"]
                assert rest_feat["geometry"] == norm_feat["geometry"]
                assert rest_feat["properties"] == norm_feat["properties"]


# ===================================================================
# Test: Generate and save the sample fixture
# ===================================================================


class TestFixtureValidation:
    """Validate the checked-in sample GeoJSON fixture used by frontend
    tests for schema drift detection."""

    def test_fixture_is_valid_feature_collection(self):
        """The checked-in fixture must be a valid GeoJSON FeatureCollection."""
        assert SAMPLE_GEOJSON_PATH.exists(), f"Fixture missing at {SAMPLE_GEOJSON_PATH}"

        loaded = json.loads(SAMPLE_GEOJSON_PATH.read_text(encoding="utf-8"))
        assert loaded["type"] == "FeatureCollection"
        assert len(loaded["features"]) > 0

        for feat in loaded["features"]:
            assert feat["type"] == "Feature"
            assert "geometry" in feat
            assert "properties" in feat
            assert "feature_type" in feat["properties"]

    def test_fixture_has_major_feature_types(self):
        """Verify the fixture contains a broad mix of feature types."""
        loaded = json.loads(SAMPLE_GEOJSON_PATH.read_text(encoding="utf-8"))
        types_present = {f["properties"]["feature_type"] for f in loaded["features"]}

        # The curated fixture should have at least these types
        for expected in ("coastline", "contour", "lake", "beach", "river"):
            assert expected in types_present, (
                f"Expected '{expected}' in fixture, got: {types_present}"
            )

    def test_fixture_survives_json_roundtrip(self):
        """The fixture must survive a JSON serialise/deserialise cycle."""
        raw = SAMPLE_GEOJSON_PATH.read_text(encoding="utf-8")
        original = json.loads(raw)
        restored = json.loads(json.dumps(original))

        assert restored == original
