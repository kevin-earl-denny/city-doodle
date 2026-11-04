# API Conventions

This document describes the patterns and conventions used in the City Doodle backend API.

## URL Structure

```
/auth/*                           - Authentication endpoints
/worlds                           - World CRUD
/worlds/{id}/districts            - District operations for a world
/worlds/{id}/neighborhoods        - Neighborhood operations
/worlds/{id}/transit              - Transit network operations
/worlds/{id}/road-network         - Road network operations
/worlds/{id}/seeds                - Placed seed operations

/districts/{id}                   - Single district operations
/neighborhoods/{id}               - Single neighborhood operations
/road-nodes/{id}                  - Single road node operations
/road-edges/{id}                  - Single road edge operations
/transit/stations/{id}            - Single station operations
/transit/lines/{id}               - Single line operations
```

## HTTP Methods

- `GET`: Retrieve resources
- `POST`: Create resources
- `PATCH`: Partial update (only send changed fields)
- `DELETE`: Remove resources

## Bulk Operations

For batch operations, use `/bulk` endpoints:
```
POST /worlds/{id}/districts/bulk
POST /worlds/{id}/road-nodes/bulk
POST /worlds/{id}/road-edges/bulk
```

Bulk endpoints accept arrays and return arrays in the same order.

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success (with body) |
| 201 | Created |
| 204 | No Content (success, no body) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized |
| 403 | Forbidden (not owner) |
| 404 | Not Found |
| 500 | Server Error |

## Error Format

```json
{
  "detail": "Error message here"
}
```

Or for validation errors:
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Authentication

All endpoints except `/`, `/health` and the OpenAPI docs require a Clerk session token:
```
Authorization: Bearer <Clerk session JWT>
```

Users sign up and sign in through Clerk in the web app (CITY-644). The web client gets the
short-lived token from Clerk's `getToken()` before every request. The API verifies it against
the Clerk instance JWKS and resolves the City Doodle user (`GET /auth/me` returns it). On first
sign-in the user is linked to an existing account by verified email or created. Missing or
invalid tokens get `401`. `AUTH_MODE=dev` (local development and tests only, refused on Fly)
trusts an `X-User-Id` header instead.

## World Ownership

Resources are scoped to worlds. Users can only access resources in worlds they own. The API validates ownership on every request.

## Geometry Format

All geometry uses GeoJSON:

### Polygon
```json
{
  "type": "Polygon",
  "coordinates": [
    [[x1, y1], [x2, y2], [x3, y3], [x1, y1]]
  ]
}
```

### Point
```json
{
  "type": "Point",
  "coordinates": [x, y]
}
```

## ENUM Types (CITY-192, CITY-202)

PostgreSQL native ENUMs with lowercase values:

```python
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

type_column = mapped_column(
    PGEnum(
        "value1", "value2", "value3",
        name="type_name",
        create_type=False,  # Required!
    ),
    nullable=False,
)
```

**Important**: `create_type=False` prevents SQLAlchemy from creating duplicate ENUM types and ensures lowercase values are used.

## Type Mapping

| Python Type | API Type | Notes |
|-------------|----------|-------|
| UUID | string | Serialized as string |
| datetime | string | ISO 8601 format |
| Enum | string | Lowercase value |
| Polygon | GeoJSON | Object with type + coordinates |

## Pagination

List endpoints support pagination:
```
GET /worlds/{id}/districts?limit=50&offset=0
```

## Filtering

Some endpoints support filtering:
```
GET /worlds/{id}/districts?historic_only=true
GET /worlds/{id}/transit/stations?station_type=subway
```

## Frontend Client

The API client in `apps/web/src/api/client.ts` handles:
- Token management
- Request formatting
- Error handling
- Base URL configuration

React Query hooks in `hooks.ts` provide:
- Automatic caching
- Optimistic updates
- Cache invalidation

## CORS

The API allows CORS from configured origins. In development, `localhost:5173` is allowed. Production uses the deployed frontend URL.

## Related Issues

- CITY-192: District type enum fix
- CITY-202: ENUM case sensitivity
- CITY-201: Missing tables fix
