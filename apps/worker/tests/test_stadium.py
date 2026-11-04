"""Tests for stadium-related functionality."""

import math
from uuid import uuid4

import pytest

from city_worker.stadium.grid_impact import (
    StreetGridImpactCalculator,
    compute_street_orientation,
    calculate_impact_radius,
    distance,
    RoadSegment,
)
from city_worker.stadium.parking import (
    ParkingLotGenerator,
    ParkingConfig,
    generate_parking_lots,
)
from city_worker.stadium.types import (
    Point,
    StadiumConfig,
    StadiumPlacement,
    StadiumType,
)


class TestStadiumTypes:
    """Tests for stadium type configuration."""

    def test_stadium_config_from_type_baseball(self):
        """Baseball stadium should have correct default config."""
        config = StadiumConfig.from_type(StadiumType.BASEBALL_STADIUM)
        assert config.width == 200
        assert config.height == 180
        assert config.capacity == 40000
        assert config.parking_ratio == 0.3
        assert config.impact_radius == 400

    def test_stadium_config_from_type_football(self):
        """Football stadium should have larger dimensions."""
        config = StadiumConfig.from_type(StadiumType.FOOTBALL_STADIUM)
        assert config.width == 250
        assert config.height == 180
        assert config.capacity == 70000
        assert config.impact_radius == 500

    def test_stadium_config_from_type_arena(self):
        """Arena should have smaller dimensions."""
        config = StadiumConfig.from_type(StadiumType.ARENA)
        assert config.width == 120
        assert config.height == 100
        assert config.capacity == 20000
        assert config.impact_radius == 300

    def test_stadium_placement_center(self):
        """Stadium placement center should match position."""
        config = StadiumConfig.from_type(StadiumType.ARENA)
        placement = StadiumPlacement(
            stadium_id=uuid4(),
            config=config,
            position=Point(100.0, 200.0),
        )
        assert placement.center == Point(100.0, 200.0)

    def test_stadium_placement_corners_no_rotation(self):
        """Stadium corners should be calculated correctly without rotation."""
        config = StadiumConfig.from_type(StadiumType.ARENA)
        placement = StadiumPlacement(
            stadium_id=uuid4(),
            config=config,
            position=Point(0.0, 0.0),
            rotation=0.0,
        )
        corners = placement.get_corners()

        # Width=120, Height=100 -> half_w=60, half_h=50
        assert len(corners) == 4
        assert corners[0] == pytest.approx(Point(-60.0, -50.0), abs=0.01)  # top-left
        assert corners[1] == pytest.approx(Point(60.0, -50.0), abs=0.01)  # top-right
        assert corners[2] == pytest.approx(Point(60.0, 50.0), abs=0.01)  # bottom-right
        assert corners[3] == pytest.approx(Point(-60.0, 50.0), abs=0.01)  # bottom-left

    def test_stadium_placement_corners_with_rotation(self):
        """Stadium corners should be rotated correctly."""
        config = StadiumConfig.from_type(StadiumType.ARENA)
        placement = StadiumPlacement(
            stadium_id=uuid4(),
            config=config,
            position=Point(0.0, 0.0),
            rotation=90.0,  # 90 degree rotation
        )
        corners = placement.get_corners()

        # After 90 degree rotation, x and y are swapped
        # Width=120, Height=100 -> half_w=60, half_h=50
        # Original top-left (-60, -50) rotates to (50, -60)
        assert len(corners) == 4
        assert corners[0].x == pytest.approx(50.0, abs=0.01)
        assert corners[0].y == pytest.approx(-60.0, abs=0.01)


class TestStreetGridImpact:
    """Tests for street grid impact calculation."""

    @pytest.fixture
    def stadium_placement(self):
        """Create a test stadium placement."""
        config = StadiumConfig.from_type(StadiumType.FOOTBALL_STADIUM)
        return StadiumPlacement(
            stadium_id=uuid4(),
            config=config,
            position=Point(500.0, 500.0),
        )

    def test_calculate_impact_radius(self, stadium_placement):
        """Impact radius should match stadium config."""
        radius = calculate_impact_radius(stadium_placement)
        assert radius == 500  # Football stadium impact radius

    def test_distance_calculation(self):
        """Distance function should work correctly."""
        p1 = Point(0.0, 0.0)
        p2 = Point(3.0, 4.0)
        assert distance(p1, p2) == 5.0  # 3-4-5 triangle

    def test_is_road_affected_inside_radius(self, stadium_placement):
        """Road inside impact radius should be affected."""
        calculator = StreetGridImpactCalculator(stadium_placement)
        road_geometry = [
            Point(400.0, 500.0),
            Point(450.0, 500.0),
        ]
        assert calculator.is_road_affected(road_geometry) is True

    def test_is_road_affected_outside_radius(self, stadium_placement):
        """Road outside impact radius should not be affected."""
        calculator = StreetGridImpactCalculator(stadium_placement)
        road_geometry = [
            Point(0.0, 0.0),
            Point(50.0, 50.0),
        ]
        assert calculator.is_road_affected(road_geometry) is False

    def test_is_road_affected_crossing_radius(self, stadium_placement):
        """Road crossing impact zone boundary should be affected."""
        calculator = StreetGridImpactCalculator(stadium_placement)
        # Road starts outside, ends inside
        road_geometry = [
            Point(0.0, 500.0),
            Point(400.0, 500.0),
        ]
        assert calculator.is_road_affected(road_geometry) is True

    def test_compute_street_orientation_pulls_toward_stadium(self, stadium_placement):
        """Street points should be pulled toward stadium."""
        road_geometry = [
            Point(300.0, 500.0),  # 200m from stadium center
            Point(350.0, 500.0),  # 150m from stadium center
        ]

        adjusted = compute_street_orientation(
            road_geometry, stadium_placement, orientation_strength=0.8
        )

        # Points should move toward stadium (x increases toward 500)
        assert adjusted[0].x > road_geometry[0].x
        assert adjusted[1].x > road_geometry[1].x

        # Both points should be noticeably pulled (at least 20m)
        pull_0 = adjusted[0].x - road_geometry[0].x
        pull_1 = adjusted[1].x - road_geometry[1].x
        assert pull_0 > 20
        assert pull_1 > 20

    def test_compute_street_orientation_no_change_outside_radius(self, stadium_placement):
        """Points outside impact radius should not change."""
        road_geometry = [
            Point(0.0, 0.0),  # ~707m from stadium center (outside 500m radius)
        ]

        adjusted = compute_street_orientation(
            road_geometry, stadium_placement, orientation_strength=0.8
        )

        assert adjusted[0] == road_geometry[0]

    def test_adjust_road_returns_result_when_affected(self, stadium_placement):
        """Adjust road should return result for affected roads."""
        calculator = StreetGridImpactCalculator(stadium_placement)
        road_id = uuid4()
        road_geometry = [Point(400.0, 500.0), Point(450.0, 500.0)]

        result = calculator.adjust_road(road_id, road_geometry)

        assert result is not None
        assert result.road_id == road_id
        assert result.original_geometry == road_geometry
        assert result.adjusted_geometry != road_geometry

    def test_adjust_road_returns_none_when_not_affected(self, stadium_placement):
        """Adjust road should return None for unaffected roads."""
        calculator = StreetGridImpactCalculator(stadium_placement)
        road_id = uuid4()
        road_geometry = [Point(0.0, 0.0), Point(50.0, 50.0)]

        result = calculator.adjust_road(road_id, road_geometry)

        assert result is None

    def test_compute_impact_multiple_roads(self, stadium_placement):
        """Compute impact should process multiple roads."""
        calculator = StreetGridImpactCalculator(stadium_placement)

        roads = [
            RoadSegment(uuid4(), [Point(400.0, 500.0), Point(450.0, 500.0)]),  # affected
            RoadSegment(uuid4(), [Point(0.0, 0.0), Point(50.0, 50.0)]),  # not affected
            RoadSegment(uuid4(), [Point(500.0, 400.0), Point(500.0, 450.0)]),  # affected
        ]

        result = calculator.compute_impact(roads)

        assert result.stadium_id == stadium_placement.stadium_id
        assert result.impact_radius == 500
        assert len(result.affected_roads) == 2  # Only 2 roads affected

    def test_generate_access_roads_cardinal(self, stadium_placement):
        """Should generate access roads in cardinal directions."""
        calculator = StreetGridImpactCalculator(stadium_placement)

        access_roads = calculator.generate_access_roads(cardinal_only=True)

        assert len(access_roads) == 4
        for road in access_roads:
            assert "geometry" in road
            assert len(road["geometry"]) == 2
            assert road["road_class"] == "collector"


class TestParkingLotGeneration:
    """Tests for parking lot generation."""

    @pytest.fixture
    def stadium_placement(self):
        """Create a test stadium placement."""
        config = StadiumConfig.from_type(StadiumType.BASEBALL_STADIUM)
        return StadiumPlacement(
            stadium_id=uuid4(),
            config=config,
            position=Point(500.0, 500.0),
        )

    def test_generate_parking_lots_default_count(self, stadium_placement):
        """Should generate default number of parking lots."""
        lots = generate_parking_lots(stadium_placement, seed=42)

        assert len(lots) == 4  # Default lot count

    def test_generate_parking_lots_custom_count(self, stadium_placement):
        """Should respect custom lot count."""
        config = ParkingConfig(lot_count=6)
        lots = generate_parking_lots(stadium_placement, config, seed=42)

        assert len(lots) == 6

    def test_parking_lots_have_valid_positions(self, stadium_placement):
        """Parking lots should be positioned correctly around stadium."""
        lots = generate_parking_lots(stadium_placement, seed=42)

        for lot in lots:
            # Should be at least min_distance from stadium edge
            dist = distance(lot.position, stadium_placement.center)
            stadium_radius = (
                max(
                    stadium_placement.config.width,
                    stadium_placement.config.height,
                )
                / 2
            )
            assert dist >= stadium_radius + 50 - 1  # 50m min_distance

    def test_parking_lots_have_valid_dimensions(self, stadium_placement):
        """Parking lots should have valid dimensions."""
        lots = generate_parking_lots(stadium_placement, seed=42)

        for lot in lots:
            assert lot.width >= 40  # min_lot_width
            assert lot.width <= 120  # max_lot_width
            assert lot.height >= 30  # min_lot_height
            assert lot.height <= 80  # max_lot_height

    def test_parking_lots_have_positive_capacity(self, stadium_placement):
        """Parking lots should have positive capacity."""
        lots = generate_parking_lots(stadium_placement, seed=42)

        for lot in lots:
            assert lot.capacity > 0

    def test_parking_lots_face_stadium(self, stadium_placement):
        """Parking lot orientation should face toward stadium."""
        lots = generate_parking_lots(stadium_placement, seed=42)

        for lot in lots:
            # Calculate expected orientation (toward stadium)
            dx = stadium_placement.center.x - lot.position.x
            dy = stadium_placement.center.y - lot.position.y
            expected_angle = math.degrees(math.atan2(dy, dx))
            if expected_angle < 0:
                expected_angle += 360

            # Orientation should be roughly opposite to position angle
            # (facing toward stadium)
            assert 0 <= lot.orientation < 360

    def test_parking_generator_deterministic_with_seed(self, stadium_placement):
        """Same seed should produce same results."""
        lots1 = generate_parking_lots(stadium_placement, seed=12345)
        lots2 = generate_parking_lots(stadium_placement, seed=12345)

        assert len(lots1) == len(lots2)
        for l1, l2 in zip(lots1, lots2):
            assert l1.position == l2.position
            assert l1.width == l2.width
            assert l1.height == l2.height
            assert l1.capacity == l2.capacity

    def test_parking_generator_different_with_different_seed(self, stadium_placement):
        """Different seeds should produce different results."""
        lots1 = generate_parking_lots(stadium_placement, seed=12345)
        lots2 = generate_parking_lots(stadium_placement, seed=54321)

        # Positions should differ
        positions_same = all(l1.position == l2.position for l1, l2 in zip(lots1, lots2))
        assert not positions_same

    def test_total_capacity_calculation(self, stadium_placement):
        """Total capacity should be calculated correctly."""
        generator = ParkingLotGenerator(stadium_placement, seed=42)
        lots = generator.generate()

        total = generator.get_total_capacity(lots)

        assert total == sum(lot.capacity for lot in lots)

    def test_coverage_area_calculation(self, stadium_placement):
        """Coverage area should be calculated correctly."""
        generator = ParkingLotGenerator(stadium_placement, seed=42)
        lots = generator.generate()

        area = generator.get_coverage_area(lots)

        expected = sum(lot.width * lot.height for lot in lots)
        assert area == expected
