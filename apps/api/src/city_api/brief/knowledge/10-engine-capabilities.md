# What City Doodle's terrain engine can draw

Read this before filling a World Brief. It describes what the generator can actually produce today, so the brief never promises terrain the map won't show.

## The map
- A world is a 3×3 grid of tiles. The finished map is about 80 km across, with the historic core at the centre.
- North is up, east is right.
- The terrain is a noise heightfield shaped by one **archetype mask**. The water level then decides what is sea and what is land.
- Features the engine can produce: ocean/coastline, bays and coves, rivers (with widths), lakes (glacial, crater, oxbow, reservoir, rift, pond, kettle), beaches, barrier islands with lagoons, tidal flats and inlets, delta channels and wetlands, and contour lines.

## Archetypes (pick exactly one)

| id | What the generator makes | Water it guarantees |
|---|---|---|
| `coastal` | Open coast along one side of the map, beaches, small bays, sometimes barrier islands | Ocean on one side |
| `bay_harbor` | Ocean on one side, with a large sheltered bay carved into the land near the centre | Bay plus ocean beyond |
| `river_valley` | One river channel through the centre, with dry valley walls on both sides. No sea | One river |
| `lakefront` | A large lake filling one side of the map, beaches on its shore, possibly smaller lakes | Big lake on one side |
| `inland` (shown to users as **Plains**) | Dry rolling land with no sea, no lakes, and currently no rivers | None |
| `island` | Land in the middle surrounded by sea on all sides, sometimes satellite islets | Sea all around |
| `peninsula` | A wedge of land pointing into the sea, with the mainland at one end | Sea on three sides |
| `delta` | A flat fan where a river splits into 5–8 channels before reaching the sea, with wetlands | Sea on one side plus distributaries |

**Picking an archetype:**
- An **estuary** (Lisbon, Hamburg, London) maps to `bay_harbor` when the water body is wide, and to `river_valley` when it is narrow.
- A **confluence** (Pittsburgh, Lyon, Khartoum) maps to `river_valley`. Tell the user the second river is not drawn yet.
- A **fjord** (Bergen, Oslo-style inlet) maps to `bay_harbor` with `coast: "rugged"` and `relief: "mountainous"`.
- An **archipelago** (Stockholm) maps to `island`.
- A **lagoon** (Venice) maps to `coastal`. Barrier islands with a lagoon behind them are the closest match.
- A **mountain valley** (Salt Lake City, Innsbruck, Kathmandu) maps to `river_valley` with `relief: "mountainous"` until a dedicated archetype ships.
- A **canyon**, **oasis** or **mesa** maps to the nearest of `river_valley` or `inland`. Note the gap in `unsupported`.

## Brief fields and how they are used

| Field | Effect today |
|---|---|
| `archetype` | Fully drives terrain |
| `water_side` | Stored as `water_direction_deg`. The generator is being updated to honour it (until then, the side is chosen by the seed) |
| `river.axis` | Stored as `river_axis_deg` for river valleys. Same rollout status as `water_side` |
| `river.count` | More than one river cannot be forced yet; extra rivers come from the terrain if the terrain makes them |
| `relief` | Stored. It will drive terrain roughness: `flat` is a smooth plain, `mountainous` means many tight ridges |
| `coast` | Stored. It will drive coastline smoothing |
| `growth_story` and `sliders` | Fully drive the street network, block sizes, district sizes and transit |

**Consistency rules for the brief:**
- For `island`, `water_side` must be `all_around`.
- For `inland` and `river_valley`, `water_side` must be `none`.
- For other archetypes, `water_side` must be a compass direction.
- `peninsula`: `water_side` is the direction the tip points.
- `bay_harbor`: `water_side` is the direction the bay opens toward the ocean.
- `delta`: `water_side` is where the sea is.

## What the engine cannot draw (put these in `unsupported`, in plain words)
- Climate, weather, seasons, snow, vegetation type, deserts as sand
- More than one forced river, or two rivers meeting
- Mountains or hills placed on a specific side; relief is map-wide
- Specific landmarks (a castle hill, a volcano, a waterfall, cliffs at one spot)
- Man-made water: canals, harbours with breakwaters, reservoirs with dams, landfill
- Multiple archetypes at once ("island in a lake", "coast plus a big lake")
- Exact real-world geography. We evoke a city's *feel*; we never replicate its map

Add a note to `unsupported` only for something the user actually asked for and won't get. Keep each note under 12 words and friendly, for example "Snowy winters: I can't draw weather yet."
