"""Pydantic schemas for API request/response models."""

from city_api.schemas.city import (
    CityClassification,
    CityCreate,
    CityResponse,
    CityUpdate,
)
from city_api.schemas.district import (
    District,
    DistrictBulkCreate,
    DistrictCreate,
    DistrictType,
    DistrictUpdate,
)
from city_api.schemas.job import Job, JobCreate, JobStatus, JobType
from city_api.schemas.neighborhood import (
    Neighborhood,
    NeighborhoodBulkCreate,
    NeighborhoodCreate,
    NeighborhoodUpdate,
)
from city_api.schemas.poi import (
    POI,
    POIBulkCreate,
    POICreate,
    POIType,
    POIUpdate,
)
from city_api.schemas.road_network import (
    NodeType,
    Point,
    RoadClass,
    RoadEdge,
    RoadEdgeBulkCreate,
    RoadEdgeCreate,
    RoadEdgeUpdate,
    RoadNetwork,
    RoadNetworkStats,
    RoadNode,
    RoadNodeBulkCreate,
    RoadNodeCreate,
    RoadNodeUpdate,
)
from city_api.schemas.seed import PlacedSeed, PlacedSeedBulkCreate, PlacedSeedCreate, Position
from city_api.schemas.stadium import (
    ParkingLot,
    ParkingLotConfig,
    Stadium,
    StadiumCreate,
    StadiumPlacement,
    StadiumSize,
    StadiumType,
    StadiumWithImpact,
    StreetGridImpact,
    STADIUM_SIZE_CONFIG,
)
from city_api.schemas.transit import (
    LineType,
    StationType,
    TransitLine,
    TransitLineBulkCreate,
    TransitLineCreate,
    TransitLineSegment,
    TransitLineSegmentBulkCreate,
    TransitLineSegmentCreate,
    TransitLineSegmentUpdate,
    TransitLineUpdate,
    TransitLineWithSegments,
    TransitNetwork,
    TransitNetworkStats,
    TransitStation,
    TransitStationBulkCreate,
    TransitStationCreate,
    TransitStationUpdate,
)
from city_api.schemas.tile import (
    TerrainData,
    Tile,
    TileCreate,
    TileFeatures,
    TileLock,
    TileLockCreate,
    TileUpdate,
)
from city_api.schemas.user import (
    UserResponse,
)
from city_api.schemas.world import World, WorldCreate, WorldSettings, WorldUpdate

__all__ = [
    # City
    "CityClassification",
    "CityCreate",
    "CityResponse",
    "CityUpdate",
    # World
    "World",
    "WorldCreate",
    "WorldUpdate",
    "WorldSettings",
    # Tile
    "Tile",
    "TileCreate",
    "TileUpdate",
    "TileLock",
    "TileLockCreate",
    "TerrainData",
    "TileFeatures",
    # Job
    "Job",
    "JobCreate",
    "JobStatus",
    "JobType",
    # District
    "District",
    "DistrictBulkCreate",
    "DistrictCreate",
    "DistrictType",
    "DistrictUpdate",
    # Neighborhood
    "Neighborhood",
    "NeighborhoodBulkCreate",
    "NeighborhoodCreate",
    "NeighborhoodUpdate",
    # POI
    "POI",
    "POIBulkCreate",
    "POICreate",
    "POIType",
    "POIUpdate",
    # Road Network
    "RoadClass",
    "NodeType",
    "Point",
    "RoadNode",
    "RoadNodeCreate",
    "RoadNodeUpdate",
    "RoadNodeBulkCreate",
    "RoadEdge",
    "RoadEdgeCreate",
    "RoadEdgeUpdate",
    "RoadEdgeBulkCreate",
    "RoadNetwork",
    "RoadNetworkStats",
    # Seed
    "PlacedSeed",
    "PlacedSeedCreate",
    "PlacedSeedBulkCreate",
    "Position",
    # Transit
    "LineType",
    "StationType",
    "TransitLine",
    "TransitLineBulkCreate",
    "TransitLineCreate",
    "TransitLineSegment",
    "TransitLineSegmentBulkCreate",
    "TransitLineSegmentCreate",
    "TransitLineSegmentUpdate",
    "TransitLineUpdate",
    "TransitLineWithSegments",
    "TransitNetwork",
    "TransitNetworkStats",
    "TransitStation",
    "TransitStationBulkCreate",
    "TransitStationCreate",
    "TransitStationUpdate",
    # User/Auth
    "UserResponse",
    # Stadium
    "Stadium",
    "StadiumCreate",
    "StadiumPlacement",
    "StadiumSize",
    "StadiumType",
    "StadiumWithImpact",
    "StreetGridImpact",
    "ParkingLot",
    "ParkingLotConfig",
    "STADIUM_SIZE_CONFIG",
]
