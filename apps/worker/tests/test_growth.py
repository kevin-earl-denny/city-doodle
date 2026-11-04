"""Tests for the growth simulation module."""

from uuid import uuid4

from city_worker.growth import GrowthChangelog, GrowthConfig
from city_worker.growth.simulator import (
    TRANSIT_ACCESS_GROWTH_MULTIPLIER,
    GrowthSimulator,
    _point_in_ring,
)
from city_worker.growth.types import ChangeEntry


def _make_district(
    district_type: str = "residential",
    density: float = 3.0,
    max_height: int = 8,
    historic: bool = False,
    transit_access: bool = False,
) -> dict:
    """Helper to create a test district dict."""
    return {
        "id": str(uuid4()),
        "world_id": str(uuid4()),
        "type": district_type,
        "name": f"Test {district_type}",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]],
            ],
        },
        "density": density,
        "max_height": max_height,
        "transit_access": transit_access,
        "historic": historic,
    }


def _make_road_node(x: float = 500, y: float = 500) -> dict:
    """Helper to create a test road node dict."""
    return {
        "id": str(uuid4()),
        "world_id": str(uuid4()),
        "position": {"x": x, "y": y},
        "node_type": "intersection",
        "name": None,
    }


class TestGrowthConfig:
    def test_default_config(self):
        config = GrowthConfig(world_id=uuid4())
        assert config.years == 1
        assert config.expansion_rate == 0.02
        assert "residential" in config.infill_rates

    def test_custom_years(self):
        config = GrowthConfig(world_id=uuid4(), years=5)
        assert config.years == 5


class TestGrowthChangelog:
    def test_to_dict(self):
        wid = uuid4()
        changelog = GrowthChangelog(world_id=wid, years_simulated=5)
        changelog.districts_infilled = 3
        changelog.entries.append(
            ChangeEntry(
                action="infill",
                entity_type="district",
                entity_id="abc",
                details={"old_density": 3.0, "new_density": 3.15},
            )
        )

        d = changelog.to_dict()
        assert d["world_id"] == str(wid)
        assert d["years_simulated"] == 5
        assert d["summary"]["districts_infilled"] == 3
        assert len(d["entries"]) == 1
        assert d["entries"][0]["action"] == "infill"


class TestGrowthSimulator:
    def test_empty_world(self):
        """Simulation on empty world produces empty changelog."""
        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)
        changelog = sim.simulate([], [], [], [])
        assert changelog.districts_infilled == 0
        assert changelog.districts_expanded == 0
        assert changelog.roads_added == 0
        assert changelog.pois_added == 0

    def test_infill_increases_density(self):
        """District density increases after simulation."""
        district = _make_district("residential", density=3.0)
        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)

        changelog = sim.simulate([district], [], [], [])

        assert district["density"] > 3.0
        assert changelog.districts_infilled == 1

    def test_infill_respects_max_density(self):
        """Density does not exceed the type maximum."""
        district = _make_district("residential", density=7.99)
        config = GrowthConfig(world_id=uuid4(), years=10)
        sim = GrowthSimulator(config, seed=42)

        sim.simulate([district], [], [], [])

        assert district["density"] <= config.max_density["residential"]

    def test_historic_district_unchanged(self):
        """Historic districts are not modified."""
        district = _make_district("residential", density=3.0, historic=True)
        original_density = district["density"]

        config = GrowthConfig(world_id=uuid4(), years=5)
        sim = GrowthSimulator(config, seed=42)
        changelog = sim.simulate([district], [], [], [])

        assert district["density"] == original_density
        assert changelog.districts_skipped_historic == 5  # once per year

    def test_expansion_grows_geometry(self):
        """District geometry expands outward."""
        district = _make_district("downtown", density=5.0)
        original_coords = [list(p) for p in district["geometry"]["coordinates"][0]]

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)
        changelog = sim.simulate([district], [], [], [])

        new_coords = district["geometry"]["coordinates"][0]
        assert changelog.districts_expanded == 1

        # At least one coordinate should have moved outward from centroid
        cx = sum(p[0] for p in original_coords) / len(original_coords)
        cy = sum(p[1] for p in original_coords) / len(original_coords)

        for orig, new in zip(original_coords[:-1], new_coords[:-1]):
            orig_dist = ((orig[0] - cx) ** 2 + (orig[1] - cy) ** 2) ** 0.5
            new_dist = ((new[0] - cx) ** 2 + (new[1] - cy) ** 2) ** 0.5
            assert new_dist >= orig_dist

    def test_new_roads_added_on_expansion(self):
        """Road nodes and edges are added when a district expands."""
        district = _make_district("commercial", density=4.0)
        existing_node = _make_road_node(500, 500)
        existing_node["world_id"] = district["world_id"]

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)

        road_nodes = [existing_node]
        road_edges = []
        changelog = sim.simulate([district], road_nodes, road_edges, [])

        # Should have added at least one new node
        assert len(road_nodes) > 1
        assert changelog.roads_added >= 1

    def test_pois_added_at_high_density(self):
        """POIs are spawned when density exceeds threshold."""
        district = _make_district("residential", density=5.0)

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)

        pois = []
        changelog = sim.simulate([district], [], [], pois)

        assert len(pois) > 0
        assert changelog.pois_added > 0
        # Residential districts need school, park, or shopping
        poi_types = {p["type"] for p in pois}
        assert poi_types.issubset({"school", "park", "shopping"})

    def test_pois_not_duplicated(self):
        """POIs are not added if the type already exists nearby."""
        district = _make_district("residential", density=5.0)
        existing_poi = {
            "id": str(uuid4()),
            "world_id": district["world_id"],
            "type": "school",
            "name": "Existing School",
            "position_x": 500,
            "position_y": 500,
        }

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)

        pois = [existing_poi]
        sim.simulate([district], [], [], pois)

        # Should not add another school
        school_count = sum(1 for p in pois if p["type"] == "school")
        assert school_count == 1

    def test_multi_year_compounds(self):
        """Multiple years of growth compound density increases."""
        district = _make_district("downtown", density=5.0)

        config = GrowthConfig(world_id=uuid4(), years=5)
        sim = GrowthSimulator(config, seed=42)
        changelog = sim.simulate([district], [], [], [])

        assert district["density"] > 5.0
        assert changelog.districts_infilled == 5
        assert changelog.years_simulated == 5

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical results."""

        def run_sim(seed: int) -> dict:
            district = _make_district("residential", density=3.0)
            config = GrowthConfig(world_id=uuid4(), years=3)
            sim = GrowthSimulator(config, seed=seed)
            changelog = sim.simulate([district], [], [], [])
            return {
                "density": district["density"],
                "infilled": changelog.districts_infilled,
                "expanded": changelog.districts_expanded,
            }

        r1 = run_sim(42)
        r2 = run_sim(42)
        assert r1 == r2

    def test_different_seeds_vary(self):
        """Different seeds can produce different POI placement."""
        results = []
        for seed in [1, 2, 3]:
            district = _make_district("residential", density=5.0)
            config = GrowthConfig(world_id=uuid4(), years=1)
            sim = GrowthSimulator(config, seed=seed)
            pois: list[dict] = []
            sim.simulate([district], [], [], pois)
            if pois:
                results.append(pois[0]["type"])

        # With different seeds, we may get different POI types
        assert len(results) > 0

    def test_expansion_blocked_by_adjacent_district(self):
        """District expansion stops at vertices that would enter another district."""
        world_id = str(uuid4())
        # District A: square at (0,0)-(1000,1000)
        district_a = _make_district("residential", density=3.0)
        district_a["world_id"] = world_id
        district_a["geometry"]["coordinates"] = [
            [[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]],
        ]
        # District B: square directly adjacent at (1000,0)-(2000,1000)
        district_b = _make_district("commercial", density=3.0)
        district_b["world_id"] = world_id
        district_b["geometry"]["coordinates"] = [
            [[1000, 0], [2000, 0], [2000, 1000], [1000, 1000], [1000, 0]],
        ]

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)

        changelog = sim.simulate([district_a, district_b], [], [], [])

        # District A's right-edge points should NOT have entered district B
        a_ring = district_a["geometry"]["coordinates"][0]
        b_ring = district_b["geometry"]["coordinates"][0]
        for p in a_ring:
            assert not _point_in_ring(
                p[0], p[1], [[1000, 0], [2000, 0], [2000, 1000], [1000, 1000], [1000, 0]]
            ), f"District A vertex {p} entered district B"

    def test_expansion_blocked_by_water_region(self):
        """District expansion stops at vertices that would enter water."""
        district = _make_district("residential", density=3.0)
        # Place a lake covering the area above y=1000
        water_regions = [
            {
                "type": "lake",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-500, 1000], [1500, 1000], [1500, 3000], [-500, 3000], [-500, 1000]],
                    ],
                },
            }
        ]

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)

        changelog = sim.simulate([district], [], [], [], water_regions)

        # Top-edge points should not have expanded into the lake
        ring = district["geometry"]["coordinates"][0]
        for p in ring:
            assert p[1] <= 1001, f"District vertex {p} expanded into water"

    def test_fully_surrounded_does_not_expand(self):
        """A district fully surrounded by others should not count as expanded."""
        world_id = str(uuid4())
        # Inner district: small square at (500,500)-(600,600)
        inner = _make_district("residential", density=3.0)
        inner["world_id"] = world_id
        inner["geometry"]["coordinates"] = [
            [[500, 500], [600, 500], [600, 600], [500, 600], [500, 500]],
        ]
        # Outer district: large square enclosing the inner one
        outer = _make_district("commercial", density=3.0)
        outer["world_id"] = world_id
        outer["geometry"]["coordinates"] = [
            [[0, 0], [1100, 0], [1100, 1100], [0, 1100], [0, 0]],
        ]

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)
        changelog = sim.simulate([inner, outer], [], [], [])

        # Inner district had all points constrained, should not count as expanded
        expand_entries = [
            e for e in changelog.entries if e.action == "expand" and e.entity_id == inner["id"]
        ]
        assert len(expand_entries) == 0

    def test_transit_access_boosts_infill_rate(self):
        """Districts with transit_access=True grow faster than those without (CITY-429)."""
        district_no_transit = _make_district("residential", density=3.0, transit_access=False)
        district_transit = _make_district("residential", density=3.0, transit_access=True)

        config = GrowthConfig(world_id=uuid4(), years=5)

        sim_no = GrowthSimulator(config, seed=42)
        sim_no.simulate([district_no_transit], [], [], [])

        sim_yes = GrowthSimulator(config, seed=42)
        sim_yes.simulate([district_transit], [], [], [])

        assert district_transit["density"] > district_no_transit["density"]

    def test_transit_access_multiplier_value(self):
        """The transit multiplier constant is 1.3 (30% boost)."""
        assert TRANSIT_ACCESS_GROWTH_MULTIPLIER == 1.3

    def test_transit_access_boosts_expansion(self):
        """Districts with transit_access=True expand faster (CITY-429)."""
        district_no_transit = _make_district("downtown", density=5.0, transit_access=False)
        district_transit = _make_district("downtown", density=5.0, transit_access=True)

        config = GrowthConfig(world_id=uuid4(), years=1)

        sim_no = GrowthSimulator(config, seed=42)
        sim_no.simulate([district_no_transit], [], [], [])

        sim_yes = GrowthSimulator(config, seed=42)
        sim_yes.simulate([district_transit], [], [], [])

        # Transit district should have expanded further from its centroid
        def _max_vertex_dist(district: dict) -> float:
            ring = district["geometry"]["coordinates"][0]
            cx = sum(p[0] for p in ring) / len(ring)
            cy = sum(p[1] for p in ring) / len(ring)
            return max(((p[0] - cx) ** 2 + (p[1] - cy) ** 2) ** 0.5 for p in ring)

        assert _max_vertex_dist(district_transit) > _max_vertex_dist(district_no_transit)

    def test_expansion_biased_toward_transit_neighbour(self):
        """Expansion direction biases toward a transit-accessible neighbour (CITY-429)."""
        world_id = str(uuid4())

        # District under test: sits at origin
        district = _make_district("residential", density=3.0)
        district["world_id"] = world_id
        district["geometry"]["coordinates"] = [
            [[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]],
        ]

        # Transit-accessible neighbour to the east (centroid ~3000, 500)
        transit_neighbour = _make_district("commercial", density=3.0, transit_access=True)
        transit_neighbour["world_id"] = world_id
        transit_neighbour["geometry"]["coordinates"] = [
            [[2500, 0], [3500, 0], [3500, 1000], [2500, 1000], [2500, 0]],
        ]

        config = GrowthConfig(world_id=uuid4(), years=1)
        sim = GrowthSimulator(config, seed=42)
        changelog = sim.simulate([district, transit_neighbour], [], [], [])

        # The right-side vertices (x=1000 originally) should have expanded
        # further than the left-side vertices (x=0 originally) due to transit bias
        ring = district["geometry"]["coordinates"][0]
        # centroid is at ~(500, 500) originally
        right_vertices = [p for p in ring if p[0] > 500]
        left_vertices = [p for p in ring if p[0] < 500]

        if right_vertices and left_vertices:
            max_right_x = max(p[0] for p in right_vertices)
            min_left_x = min(p[0] for p in left_vertices)
            # Right side expansion from centroid should be larger than left side
            right_expansion = max_right_x - 500
            left_expansion = 500 - min_left_x
            assert right_expansion > left_expansion

    def test_transit_access_still_respects_max_density(self):
        """Transit boost does not allow density to exceed the type maximum (CITY-429)."""
        district = _make_district("residential", density=7.99, transit_access=True)
        config = GrowthConfig(world_id=uuid4(), years=10)
        sim = GrowthSimulator(config, seed=42)

        sim.simulate([district], [], [], [])

        assert district["density"] <= config.max_density["residential"]


class TestPointInRing:
    def test_point_inside_square(self):
        ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        assert _point_in_ring(5, 5, ring) is True

    def test_point_outside_square(self):
        ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        assert _point_in_ring(15, 5, ring) is False

    def test_point_on_edge(self):
        ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        # On the boundary — ray casting can go either way, just don't crash
        result = _point_in_ring(10, 5, ring)
        assert isinstance(result, bool)
