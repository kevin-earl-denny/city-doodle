"""Road network repository - data access for road nodes and edges."""

import math
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from city_api.models import RoadEdge as RoadEdgeModel
from city_api.models import RoadNode as RoadNodeModel
from city_api.schemas import (
    Point,
    RoadEdge,
    RoadEdgeCreate,
    RoadEdgeUpdate,
    RoadNetwork,
    RoadNetworkStats,
    RoadNode,
    RoadNodeCreate,
    RoadNodeUpdate,
)
from city_api.schemas.road_network import ROAD_CLASS_DEFAULTS


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _calculate_edge_length(from_pos: dict, to_pos: dict, geometry: list[dict]) -> float:
    """Calculate the total length of an edge including intermediate points."""
    points = [from_pos] + geometry + [to_pos]
    total = 0.0
    for i in range(len(points) - 1):
        dx = points[i + 1]["x"] - points[i]["x"]
        dy = points[i + 1]["y"] - points[i]["y"]
        total += math.sqrt(dx * dx + dy * dy)
    return total


# ============================================================================
# Road Node Operations
# ============================================================================


async def create_node(db: AsyncSession, node_create: RoadNodeCreate) -> RoadNode:
    """Create a new road node."""
    node = RoadNodeModel(
        world_id=node_create.world_id,
        position=node_create.position.model_dump(),
        node_type=node_create.node_type.value,
        name=node_create.name,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    # Don't try to get connected edges for new nodes
    return _node_to_schema(node, include_edges=False)


async def create_nodes_bulk(db: AsyncSession, nodes: list[RoadNodeCreate]) -> list[RoadNode]:
    """Create multiple nodes at once."""
    models = [
        RoadNodeModel(
            world_id=n.world_id,
            position=n.position.model_dump(),
            node_type=n.node_type.value,  # Pass string value for PostgreSQL enum
            name=n.name,
        )
        for n in nodes
    ]
    db.add_all(models)
    await db.commit()
    for m in models:
        await db.refresh(m)
    # Don't try to get connected edges for new nodes
    return [_node_to_schema(m, include_edges=False) for m in models]


async def get_node(db: AsyncSession, node_id: UUID) -> RoadNode | None:
    """Get a road node by ID."""
    result = await db.execute(
        select(RoadNodeModel)
        .where(RoadNodeModel.id == node_id)
        .options(selectinload(RoadNodeModel.edges_from), selectinload(RoadNodeModel.edges_to))
    )
    node = result.scalar_one_or_none()
    if node is None:
        return None
    return _node_to_schema(node, include_edges=True)


async def get_node_model(db: AsyncSession, node_id: UUID) -> RoadNodeModel | None:
    """Get a road node model by ID (for internal use)."""
    result = await db.execute(select(RoadNodeModel).where(RoadNodeModel.id == node_id))
    return result.scalar_one_or_none()


async def list_nodes_by_world(db: AsyncSession, world_id: UUID) -> list[RoadNode]:
    """List all road nodes in a world."""
    result = await db.execute(
        select(RoadNodeModel)
        .where(RoadNodeModel.world_id == world_id)
        .options(selectinload(RoadNodeModel.edges_from), selectinload(RoadNodeModel.edges_to))
    )
    nodes = result.scalars().all()
    return [_node_to_schema(n, include_edges=True) for n in nodes]


async def update_node(
    db: AsyncSession, node_id: UUID, node_update: RoadNodeUpdate
) -> RoadNode | None:
    """Update a road node."""
    result = await db.execute(
        select(RoadNodeModel)
        .where(RoadNodeModel.id == node_id)
        .options(selectinload(RoadNodeModel.edges_from), selectinload(RoadNodeModel.edges_to))
    )
    node = result.scalar_one_or_none()
    if node is None:
        return None

    if node_update.position is not None:
        node.position = node_update.position.model_dump()
    if node_update.node_type is not None:
        node.node_type = node_update.node_type.value
    if node_update.name is not None:
        node.name = node_update.name

    await db.commit()
    # Re-query with selectinload to get fresh relationships
    # (db.refresh() would expire them, causing MissingGreenlet in async)
    result2 = await db.execute(
        select(RoadNodeModel)
        .where(RoadNodeModel.id == node_id)
        .options(selectinload(RoadNodeModel.edges_from), selectinload(RoadNodeModel.edges_to))
    )
    node = result2.scalar_one()
    return _node_to_schema(node, include_edges=True)


async def delete_node(db: AsyncSession, node_id: UUID) -> bool:
    """Delete a road node. Connected edges are deleted via CASCADE."""
    result = await db.execute(delete(RoadNodeModel).where(RoadNodeModel.id == node_id))
    await db.commit()
    return result.rowcount > 0


# ============================================================================
# Road Edge Operations
# ============================================================================


async def create_edge(db: AsyncSession, edge_create: RoadEdgeCreate) -> RoadEdge | None:
    """Create a new road edge. Returns None if nodes don't exist."""
    # Verify nodes exist
    from_node = await get_node_model(db, edge_create.from_node_id)
    to_node = await get_node_model(db, edge_create.to_node_id)
    if from_node is None or to_node is None:
        return None

    # Apply defaults based on road class
    defaults = ROAD_CLASS_DEFAULTS.get(edge_create.road_class, {})
    speed_limit = edge_create.speed_limit or defaults.get("speed_limit")
    lanes = edge_create.lanes if edge_create.lanes != 2 else defaults.get("lanes", 2)

    # Calculate length
    geometry = [p.model_dump() for p in edge_create.geometry] if edge_create.geometry else []
    length = _calculate_edge_length(from_node.position, to_node.position, geometry)

    edge = RoadEdgeModel(
        world_id=edge_create.world_id,
        from_node_id=edge_create.from_node_id,
        to_node_id=edge_create.to_node_id,
        road_class=edge_create.road_class.value,
        geometry=geometry,
        length_meters=length,
        speed_limit=speed_limit,
        name=edge_create.name,
        is_one_way=edge_create.is_one_way,
        lanes=lanes,
        district_id=edge_create.district_id,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return _edge_to_schema(edge)


async def create_edges_bulk(db: AsyncSession, edges: list[RoadEdgeCreate]) -> list[RoadEdge]:
    """Create multiple edges at once. Skips edges with invalid node references."""
    created = []
    for edge_create in edges:
        edge = await create_edge(db, edge_create)
        if edge is not None:
            created.append(edge)
    return created


async def get_edge(db: AsyncSession, edge_id: UUID) -> RoadEdge | None:
    """Get a road edge by ID."""
    result = await db.execute(select(RoadEdgeModel).where(RoadEdgeModel.id == edge_id))
    edge = result.scalar_one_or_none()
    if edge is None:
        return None
    return _edge_to_schema(edge)


async def list_edges_by_world(db: AsyncSession, world_id: UUID) -> list[RoadEdge]:
    """List all road edges in a world."""
    result = await db.execute(select(RoadEdgeModel).where(RoadEdgeModel.world_id == world_id))
    edges = result.scalars().all()
    return [_edge_to_schema(e) for e in edges]


async def list_edges_by_node(db: AsyncSession, node_id: UUID) -> list[RoadEdge]:
    """List all edges connected to a node."""
    result = await db.execute(
        select(RoadEdgeModel).where(
            (RoadEdgeModel.from_node_id == node_id) | (RoadEdgeModel.to_node_id == node_id)
        )
    )
    edges = result.scalars().all()
    return [_edge_to_schema(e) for e in edges]


async def update_edge(
    db: AsyncSession, edge_id: UUID, edge_update: RoadEdgeUpdate
) -> RoadEdge | None:
    """Update a road edge."""
    result = await db.execute(select(RoadEdgeModel).where(RoadEdgeModel.id == edge_id))
    edge = result.scalar_one_or_none()
    if edge is None:
        return None

    if edge_update.road_class is not None:
        edge.road_class = edge_update.road_class.value
    if edge_update.geometry is not None:
        edge.geometry = [p.model_dump() for p in edge_update.geometry]
        # Recalculate length when geometry changes
        from_node = await get_node_model(db, edge.from_node_id)
        to_node = await get_node_model(db, edge.to_node_id)
        if from_node and to_node:
            edge.length_meters = _calculate_edge_length(
                from_node.position, to_node.position, edge.geometry
            )
    if edge_update.speed_limit is not None:
        edge.speed_limit = edge_update.speed_limit
    if edge_update.name is not None:
        edge.name = edge_update.name
    if edge_update.is_one_way is not None:
        edge.is_one_way = edge_update.is_one_way
    if edge_update.lanes is not None:
        edge.lanes = edge_update.lanes

    await db.commit()
    await db.refresh(edge)
    return _edge_to_schema(edge)


async def delete_edge(db: AsyncSession, edge_id: UUID) -> bool:
    """Delete a road edge."""
    result = await db.execute(delete(RoadEdgeModel).where(RoadEdgeModel.id == edge_id))
    await db.commit()
    return result.rowcount > 0


# ============================================================================
# Network Operations
# ============================================================================


async def get_road_network(db: AsyncSession, world_id: UUID) -> RoadNetwork:
    """Get the complete road network for a world."""
    nodes = await list_nodes_by_world(db, world_id)
    edges = await list_edges_by_world(db, world_id)
    return RoadNetwork(world_id=world_id, nodes=nodes, edges=edges)


async def get_network_stats(db: AsyncSession, world_id: UUID) -> RoadNetworkStats:
    """Get statistics about a road network."""
    nodes = await list_nodes_by_world(db, world_id)
    edges = await list_edges_by_world(db, world_id)

    # Count edges by class
    edges_by_class: dict[str, int] = {}
    total_length = 0.0
    for edge in edges:
        class_name = edge.road_class.value
        edges_by_class[class_name] = edges_by_class.get(class_name, 0) + 1
        total_length += edge.length_meters

    # Calculate connectivity (simple: 1.0 if graph is connected, else ratio)
    connectivity_score = _calculate_connectivity(nodes, edges) if nodes else 1.0

    return RoadNetworkStats(
        world_id=world_id,
        total_nodes=len(nodes),
        total_edges=len(edges),
        total_length_meters=total_length,
        edges_by_class=edges_by_class,
        connectivity_score=connectivity_score,
    )


def _calculate_connectivity(nodes: list[RoadNode], edges: list[RoadEdge]) -> float:
    """Calculate connectivity score using Union-Find."""
    if not nodes:
        return 1.0

    # Build adjacency using node IDs
    node_ids = {n.id for n in nodes}
    parent: dict[UUID, UUID] = {n.id: n.id for n in nodes}

    def find(x: UUID) -> UUID:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: UUID, y: UUID) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Union all connected nodes
    for edge in edges:
        if edge.from_node_id in node_ids and edge.to_node_id in node_ids:
            union(edge.from_node_id, edge.to_node_id)

    # Count unique components
    components = len(set(find(n.id) for n in nodes))

    # Return ratio (1 component = 1.0, N components = 1/N)
    return 1.0 / components if components > 0 else 1.0


async def delete_edges_by_district(db: AsyncSession, district_id: UUID) -> tuple[int, int]:
    """Delete all road edges belonging to a district and clean up orphaned nodes.

    CITY-298: When a district is deleted, its associated road edges and any
    nodes that become orphaned (no remaining edges) must be removed.

    Returns (edges_deleted, nodes_deleted).
    """
    # Collect node IDs referenced by the edges we're about to delete
    edge_rows = await db.execute(
        select(RoadEdgeModel.from_node_id, RoadEdgeModel.to_node_id).where(
            RoadEdgeModel.district_id == district_id
        )
    )
    candidate_node_ids: set[UUID] = set()
    for row in edge_rows:
        candidate_node_ids.add(row[0])
        candidate_node_ids.add(row[1])

    # Delete the edges
    result = await db.execute(delete(RoadEdgeModel).where(RoadEdgeModel.district_id == district_id))
    edges_deleted = result.rowcount

    # Delete orphaned nodes (nodes with no remaining edges)
    nodes_deleted = 0
    for node_id in candidate_node_ids:
        remaining = await db.execute(
            select(RoadEdgeModel.id)
            .where((RoadEdgeModel.from_node_id == node_id) | (RoadEdgeModel.to_node_id == node_id))
            .limit(1)
        )
        if remaining.first() is None:
            await db.execute(delete(RoadNodeModel).where(RoadNodeModel.id == node_id))
            nodes_deleted += 1

    return edges_deleted, nodes_deleted


async def clear_road_network(db: AsyncSession, world_id: UUID) -> int:
    """Delete all nodes and edges in a world. Returns count of deleted nodes.

    Edges are deleted via CASCADE when nodes are deleted.
    """
    result = await db.execute(delete(RoadNodeModel).where(RoadNodeModel.world_id == world_id))
    await db.commit()
    return result.rowcount


# ============================================================================
# Schema Converters
# ============================================================================


def _node_to_schema(node: RoadNodeModel, include_edges: bool = False) -> RoadNode:
    """Convert SQLAlchemy model to Pydantic schema.

    Args:
        node: The SQLAlchemy model
        include_edges: If True, tries to get connected edge IDs from loaded relationships.
                       Only set this to True if relationships were loaded with selectinload().
    """
    connected_edges: list[UUID] = []
    if include_edges:
        # Relationships must be loaded with selectinload() before calling this
        if node.edges_from is not None:
            connected_edges.extend([e.id for e in node.edges_from])
        if node.edges_to is not None:
            connected_edges.extend([e.id for e in node.edges_to])

    return RoadNode(
        id=node.id,
        world_id=node.world_id,
        position=Point(**node.position),
        node_type=node.node_type,
        name=node.name,
        connected_edges=list(set(connected_edges)),
        created_at=_ensure_utc(node.created_at),
        updated_at=_ensure_utc(node.updated_at),
    )


def _edge_to_schema(edge: RoadEdgeModel) -> RoadEdge:
    """Convert SQLAlchemy model to Pydantic schema."""
    return RoadEdge(
        id=edge.id,
        world_id=edge.world_id,
        from_node_id=edge.from_node_id,
        to_node_id=edge.to_node_id,
        road_class=edge.road_class,
        geometry=[Point(**p) for p in edge.geometry] if edge.geometry else [],
        length_meters=edge.length_meters,
        speed_limit=edge.speed_limit,
        name=edge.name,
        is_one_way=edge.is_one_way,
        lanes=edge.lanes,
        district_id=edge.district_id,
        created_at=_ensure_utc(edge.created_at),
        updated_at=_ensure_utc(edge.updated_at),
    )
