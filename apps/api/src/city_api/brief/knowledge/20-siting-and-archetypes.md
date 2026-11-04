# Site and Situation: Why Cities Form Where They Do, by Terrain Archetype

Research corpus for City Doodle's "World Brief" LLM prompt and the "found your city" flow.
Compiled 2026-11-03.

**How to read this file**

- **Site** means the physical ground a city sits on: its hills, water supply, flood risk, harbor depth and defensibility. **Situation** means where the city sits relative to everything else: routes, trade, rivers, hinterland and rivals. Site factors usually explain why a city was *founded* in a spot. Situation explains why it kept *growing*. (geographyfieldwork.com/SiteSituation.htm, internetgeography.net/?p=1080)
- Each section has prose for the LLM, plus `yaml` blocks meant to be machine-converted to JSON later.
- **Tags:** facts marked `[verified]` were checked against at least one encyclopedic, government or academic source during this research. Facts marked `[hedge]` are disputed or vary between sources, and the product copy should keep the softening word ("about", "often said", "traditionally"). Numbers in the "engine target" fields are **design heuristics for the generator, not real-world measurements**.
- Directions in city records (`water_side`) are **approximate, as seen from the historic downtown**, and simplified to fit the engine's N/E/S/W vocabulary.
- **Source format:** citations are short URLs. "WP" means a Wikipedia article (en.wikipedia.org/wiki/…) and "EB" means Britannica (britannica.com/place/…).

---

## Table of Contents

1. Siting factors (19 factors, with examples)
2. Archetypes: the 8 engine archetypes and 8 candidate archetypes
3. Spatial vocabulary → parameter mapping
4. City records (45 real cities)
5. Appendix: quick reference tables, slope thresholds, accuracy cautions

---

## 1. Siting Factors

Each factor has a short explanation, examples, and an `engine_hint` that describes what the terrain generator would need to produce it.

### 1.1 Natural harbor
A natural harbor is deep, sheltered water protected from storms by headlands, islands or a narrow entrance. Ships could anchor safely before breakwaters existed, so harbor towns became ports and naval bases. Many of the best natural harbors are **drowned river valleys (rias)** that the sea flooded after the last Ice Age.
- **Sydney:** Port Jackson is a ria cut into Hawkesbury Sandstone and flooded about 10,000 years ago. Its many fingers give it a very long, indented shoreline. `[verified]` (WP Geography_of_Sydney; WP Port_Jackson)
- **Halifax:** the harbour is widely described as one of the world's largest ice-free natural harbours. The "second largest" claim is contested. `[hedge]` Citadel Hill, which overlooks it, is a glacial drumlin. `[verified]` (WP Halifax_Harbour)
- **Istanbul:** the Golden Horn is a roughly 7.5 km horn-shaped inlet. It served as the city's sheltered harbor through the Byzantine and Ottoman eras. `[verified]` (WP Golden_Horn)
- **Valletta:** the city sits on the Sciberras peninsula between two natural harbours, Grand Harbour and Marsamxett. `[verified]` (WP Grand_Harbour)
```yaml
engine_hint: {bay_enabled: true, bay_shape: "narrow-mouth, branching", coast_ruggedness: medium-high, relief: rolling-hilly, headlands: true}
```

### 1.2 River ford / lowest bridging point
A ford is a shallow, firm-bottomed place where people could wade a river. Roads converged on fords, and later bridges replaced them. The **lowest bridging point**, meaning the crossing closest to the sea, is especially powerful because it combines a land route with access for seagoing ships.
- **Oxford:** the name is generally read as "ford of the oxen" (Oxnaforda, first recorded in 912). It sat where a north–south cattle route crossed the Thames. `[verified]` (oxoniensia.org/volumes/1973/davis.pdf; etymonline.com/word/oxford)
- **Frankfurt:** "ford of the Franks", first written as *Franconofurd* in 794. `[verified]` (WP History_of_Frankfurt; EB Frankfurt-am-Main)
- **London:** gravel terraces made a firm crossing point at the Thames. The Romans were the first to bridge the river there, around AD 43–50, and the river was tidal up to the bridge. `[verified]` Bridge dates vary by source. `[hedge]` (publications.naturalengland.org.uk; WP London_Bridge)
- **Innsbruck:** the name means "bridge over the Inn". It grew where the bridge met the Brenner Pass trade route. `[verified]` (WP Innsbruck; EB Innsbruck)
```yaml
engine_hint: {river: single, river_width: narrow-medium, crossing_point: marked, roads_converge_on: crossing}
```

### 1.3 Confluence
A confluence is a place where two rivers meet. The point of land between them is easy to defend on two sides, and it controls traffic on both rivers. Confluence cities often have a wedge-shaped downtown and lots of bridges.
- **Pittsburgh:** the Allegheny and Monongahela join here to form the Ohio. This "Forks of the Ohio" was fought over by France and Britain (Fort Duquesne, then Fort Pitt). Downtown's "Golden Triangle" fills the wedge. `[verified]` (nps.gov/parkhistory/online_books/founders/sitec37.htm; WP Point_State_Park)
- **Khartoum:** the Blue Nile and White Nile meet at al-Mogran ("the confluence"). The name is popularly said to mean "elephant's trunk", after the shape of the land, but the etymology is disputed. `[hedge]` (WP Khartoum)
- **Koblenz:** the name comes from Latin *Confluentes*, "at the confluence" of the Rhine and Moselle. The tip of land between them is the Deutsches Eck. `[verified]` (WP Koblenz)
- **Lyon:** the Presqu'île is a tongue of land between the Rhône and Saône. Roman Lugdunum (43 BC) was founded on Fourvière hill above the meeting point. `[verified]` (WP Fourvière; en.visiterlyon.com)
```yaml
engine_hint: {rivers: 2+, river_join: true, downtown_at: "wedge between rivers", bridges: many}
```

### 1.4 Head of navigation / fall line
The **head of navigation** is the farthest point upstream that ships can reach. Rapids or falls stop them there, so goods had to be unloaded, and towns grew at the transfer point. Falling water also powered mills. On the U.S. East Coast, the **Atlantic Seaboard Fall Line** is the boundary between hard Piedmont rock and the soft Coastal Plain, and it produced a chain of cities. `[verified]` (britannica.com/science/fall-line; WP Atlantic_Seaboard_Fall_Line)
- **Fall-line cities:** Britannica lists Trenton, Philadelphia, Baltimore, Washington, Richmond, Columbia SC, Augusta and Columbus GA. `[verified]` (kids.britannica.com/students/article/fall-line/274261)
- **Minneapolis:** St. Anthony Falls is the only major natural waterfall on the upper Mississippi. It was the head of steamboat navigation and powered the flour mills that made Minneapolis the flour-milling capital (roughly 1880–1930). `[verified]` (WP Saint_Anthony_Falls; nps.gov/miss)
- **Montreal:** the Lachine Rapids made the city the head of ocean navigation on the St. Lawrence, so cargo was transshipped there. The Lachine Canal opened in 1825. `[verified]` (canadashistory.ca; McGill digitized sources)
- **Louisville:** the Falls of the Ohio were the only *major* navigational barrier on the Ohio. Cargo was portaged around them. George Rogers Clark's party arrived in 1778. `[verified]` (nps.gov/places/george-rogers-clark-home-site-at-the-falls-of-the-ohio-river.htm)
- **Kinshasa and Brazzaville:** Pool Malebo is the upstream end of the Livingstone Falls, which block the lower Congo. The two capitals face each other across the pool and are the closest pair of national capitals apart from Rome and Vatican City. `[verified]` (WP Pool_Malebo)
```yaml
engine_hint: {river: single, rapids_marker: true, relief_step: "upland → lowland break across map", downtown_at: "foot of rapids"}
```

### 1.5 Estuary
NOAA defines an estuary as a partly enclosed body of water where river freshwater mixes with seawater. Bays, lagoons, sounds and sloughs can all be estuaries. `[verified]` (oceanservice.noaa.gov/facts/estuary.html) Estuary ports sit inland for shelter, but tides still carry ships in.
- **London:** Thames estuary. The river is tidal up to Teddington.
- **Hamburg:** a tidal port on the Elbe. Sources put it 110 to 140 km from the North Sea, depending on how distance is measured. `[hedge]` (WP Port_of_Hamburg; hafen-hamburg.de/en/tide)
- **Lisbon:** sits on the Tagus estuary. Its inner basin, the Mar da Palha ("Sea of Straw"), is up to about 23 km wide. `[verified]` (WP History_of_Lisbon)
- **Buenos Aires:** on the Río de la Plata, which is often described as the widest estuary in the world. `[hedge]`
- **New York:** the Hudson is tidal far inland, up to the dam at Troy.
```yaml
engine_hint: {river_mouth: wide-funnel, tidal_flats: true, water_side: one, river_widens_toward_sea: true}
```

### 1.6 Defensive hill / acropolis
A steep, isolated hill could be held against attackers and seen from far away. The citadel goes on top and the town spreads down its flanks, often along a single ridge.
- **Athens:** the Acropolis is a limestone outcrop with sheer sides that rises above the plain. Classic "high city".
- **Edinburgh:** Castle Rock is a Carboniferous volcanic plug. Glaciers shaped it into a "crag and tail", and the Royal Mile runs down the tail. `[verified]` (edinburghgeolsoc.org/geological-site/castle-rock; WP Castle_Rock_(Edinburgh))
- **Quebec City:** Upper Town is walled and sits on Cap Diamant, a promontory 98 m high, which earned the city the nickname "Gibraltar of North America". `[verified]` (thecanadianencyclopedia.ca)
- **Belgrade:** the fortress stands on the Kalemegdan ridge above the Sava–Danube confluence. "Beograd" means "white city/fortress". `[verified]` (WP Belgrade_Fortress)
```yaml
engine_hint: {relief: hilly, isolated_peak_near_center: true, peak_prominence: high, downtown_at: "foot or flank of peak"}
```

### 1.7 Island / defensive water
Water was the best moat available. Island cities were easy to defend and naturally became trading posts, but they run short of land, which drives landfill, bridges and density.
- **Paris:** began on the Île de la Cité, which made the Seine easy to cross and the settlement easy to defend. Whether Gallic Lutetia itself stood on the island is debated. `[hedge]` (WP Île_de_la_Cité; sjsu.edu/faculty/watkins/paris.htm)
- **Tenochtitlan (Mexico City):** founded in 1325 on an island in Lake Texcoco. It was linked to shore by causeways and expanded with chinampas (built-up garden islands). `[verified]` (EB Mexico-City/History)
- **Venice:** built on about 118 islands in a lagoon, settled by mainlanders fleeing 5th-century invasions. `[verified]` (EB summary/Venice)
- **Stockholm:** built on 14 islands where Lake Mälaren meets the Baltic. `[verified]` for the count across several sources, though Britannica just says "numerous islands" (EB Stockholm)
```yaml
engine_hint: {water_side: all, island_count: 1+, landfill_pressure: high}
```

### 1.8 Mountain pass / gap
Routes through mountains funnel into passes and **gaps**, where a river cuts through a ridge. Towns guard and supply these chokepoints.
- **Innsbruck:** sits on the Inn valley route to the Brenner Pass, the easiest crossing of the Alps between Germany and Italy. `[verified]` (EB Innsbruck)
- **Peshawar:** at the eastern foot of the Khyber Pass between South and Central Asia.
- **Guildford (UK):** a textbook "gap town" where the River Wey cuts through the chalk North Downs.
```yaml
engine_hint: {relief: mountainous, valley_corridor: true, corridor_direction: "N-S or E-W", downtown_at: "valley throat"}
```

### 1.9 Oasis / spring
In dry country, a reliable spring or a river fed by mountains decides where anyone can live at all. The city's footprint follows its irrigated green belt.
- **Damascus:** the Barada River rises in the Anti-Lebanon mountains and waters the Ghouta oasis, then disappears into the desert. Britannica calls Damascus "perhaps the oldest continuously inhabited" ancient city. `[verified]`, though the "oldest" claim is hedged in every source (EB Damascus; kids.britannica.com)
- **Las Vegas:** Spanish for "the meadows". Artesian springs made it a water stop on the Old Spanish Trail, and the name dates from about 1829. `[verified]` (shpo.nv.gov historical marker)
- **Addis Ababa:** founded in 1886 by Menelik II and Empress Taytu, who chose the site partly for the Filwoha hot springs. Some sources give 1887. `[hedge]` (WP History_of_Addis_Ababa; addismayor.gov.et)
- **Bath (UK):** Roman Aquae Sulis was built around Britain's only naturally hot springs. `[verified]` (WP Aquae_Sulis; british-history.ac.uk)
```yaml
engine_hint: {water_coverage: "<2%", spring_or_short_river: true, relief: "flat basin with mountains on one side", green_belt_follows_water: true}
```

### 1.10 Portage
A portage is the overland carry between two waterways. Settlements grew at its ends, and canals later followed the same line.
- **Chicago:** a short, marshy portage over a low continental divide linked Lake Michigan (via the Chicago River) to the Des Plaines, Illinois and Mississippi rivers. It became the Illinois & Michigan Canal and later the Sanitary and Ship Canal. `[verified]` (nps.gov/places/chicago-portage.htm; WP Chicago_Portage)
- **Auckland:** Māori canoe portages crossed the narrow isthmus between the Waitematā and Manukau harbours. At Te Tō Waka only about 200 m of land separated the Manukau from the Tāmaki River. `[verified]` (teara.govt.nz/en/auckland-region/page-3; WP Auckland_isthmus)
- **Toronto:** the end of the Toronto Carrying-Place Trail, which ran from Lake Ontario toward Lake Simcoe and the upper Great Lakes.
- **Corinth:** the *Diolkos* was a paved trackway for hauling ships across the Isthmus of Corinth.
```yaml
engine_hint: {two_water_bodies: true, narrow_land_between: true, low_divide: true}
```

### 1.11 River meander / oxbow
A tight river loop makes a natural moat on three sides. The town takes the neck of land, and a single wall or castle closes the gap. Rivers with sinuosity (channel length ÷ straight-line distance) of 1.5 or more are conventionally called meandering. `[verified]` (people.ohio.edu/dyer/TPE; USGS PP 282-B, pubs.usgs.gov/publication/pp282B) When a loop is cut off, it becomes an oxbow lake.
- **Bern:** founded in 1191 on a narrow hill in a loop of the Aare, which surrounds it on three sides. UNESCO World Heritage since 1983. `[verified]` (WP Old_City_(Bern); whc.unesco.org/en/list/267)
- **Durham (UK):** the cathedral and castle stand on a peninsula inside a deep loop of the River Wear.
- **Besançon (France):** the old town fills a loop of the Doubs, with a citadel on the neck.
- **Toledo (Spain):** the Tagus wraps around the hill town in a deep gorge.
```yaml
engine_hint: {river_course: meandering, loop_count: 1-3, downtown_inside_loop: true}
```

### 1.12 Delta
A delta is the low, fan- or bird-foot-shaped landform a river builds where it reaches the sea. Its land is fertile but flat, flood-prone and sinking, and it is threaded by distributary channels. Galloway's 1975 scheme sorts deltas by their dominant force. **River-dominated** deltas (Mississippi) have a bird's-foot shape. **Wave-dominated** deltas (Nile) have a smooth, arcuate front. **Tide-dominated** deltas (Ganges–Brahmaputra) are cut by many funnel channels and islands. `[verified]` (geo.libretexts.org Coastal Dynamics 2.7.3; arxiv.org/pdf/0711.3283)
- **New Orleans:** the French Quarter (1718) sits on the Mississippi's natural levee, the "high ground". A large share of the city is at or below sea level; one 2016 ASCE study puts it at about 65% of New Orleans proper. `[hedge]`, as the figure depends on the area measured (WP Drainage_in_New_Orleans)
- **Rotterdam:** on the Nieuwe Maas in the Rhine–Meuse delta. It is Europe's largest port, and its harbor area stretches about 40 km to the sea. `[verified]` (WP Port_of_Rotterdam)
- **Dhaka:** on the Buriganga in the Ganges–Brahmaputra delta. Ground elevation is roughly 1–14 m. The city is ringed by six interconnected river systems. `[verified]` (core.ac.uk/download/12549139.pdf; banglapedia.org)
- **Alexandria:** founded in 331 BC on the western edge of the Nile Delta, on a strip between the sea and Lake Mareotis.
```yaml
engine_hint: {relief: flat, elevation: "0-10 m", distributaries: 3+, river_course: braided_or_branching, wetlands: true, barrier_islands: optional}
```

### 1.13 Lagoon
A lagoon is shallow water cut off from the sea by barrier islands, spits or reefs. It provides calm water and protection, but its access channels may need dredging.
- **Venice:** about 118 islands in the Venetian Lagoon. Buildings stand on timber piles driven into the lagoon mud. `[verified]` (EB Venice; engineeringrome.org)
- **Lagos:** Portuguese for "lakes". The city began on Lagos Island and its neighbors at the mouth of Lagos Lagoon, sheltered from the Atlantic by sand spits. `[verified]` (WP Lagos_Lagoon; WP History_of_Lagos)
- **Abidjan:** built around the Ébrié Lagoon. The Vridi Canal was cut through the sandbar around 1950–51, which turned the lagoon into a deep-water port. `[verified]` (WP Autonomous_Port_of_Abidjan; EB Abidjan)
```yaml
engine_hint: {barrier_islands: true, lagoon_behind_barrier: true, inlets: 1-3, water_coverage: "40-60%"}
```

### 1.14 Isthmus
An isthmus is a narrow neck of land between two bodies of water. It controls movement by land and offers a short-cut between seas, with water on two sides.
- **Corinth:** controlled the land route into the Peloponnese and the Diolkos ship-haul. The Corinth Canal opened in 1893.
- **Panama City:** founded in 1519 on the Pacific side of the isthmus.
- **Auckland:** the isthmus narrows to about 2 km between two harbours. It is studded with a volcanic field of roughly 48–53 vents, depending on how they are counted. `[hedge]` (teara.govt.nz; WP Auckland_volcanic_field)
- **Madison, WI:** downtown and the Capitol sit on an isthmus between Lakes Mendota and Monona. `[verified]` (WP Madison_Isthmus)
- **Seattle:** sits on a hilly glacial isthmus between Puget Sound and Lake Washington. `[verified]` (WP Regrading_in_Seattle)
```yaml
engine_hint: {water_side: ["two opposite sides"], land_width_at_center: narrow, relief: any}
```

### 1.15 Plateau / mesa
A high, flat-topped tableland with steep edges is easy to defend and can be cooler and healthier than the lowlands. It also limits sprawl and forces cities to climb or bridge.
- **Constantine (Algeria):** sits on a rock plateau of about 650 m, ringed on most sides by the Rhumel gorge, which is 150–300 m deep. It is called the "City of Bridges". `[verified]` (EB Constantine; WP Constantine,_Algeria)
- **Acoma Pueblo (New Mexico):** "Sky City" sits on a sandstone mesa and is among the oldest continuously inhabited communities in North America.
- **Orvieto (Italy):** built on a sheer-sided butte of volcanic tuff.
- **Bogotá / Madrid:** large-scale plateau capitals, on the Sabana de Bogotá and the Spanish Meseta respectively.
```yaml
engine_hint: {relief: "flat top + steep edges", escarpment_ring: true, elevation_offset: high}
```

### 1.16 Valley floor
Flat land between mountains brings water, farmland and an easy road along the valley, but it is often hemmed in, foggy or smoggy.
- **Kathmandu:** the valley floor is the bed of the drained Paleo-Kathmandu Lake, with up to about 500 m of lake sediment. That makes fertile soil, and the Manjushri legend explains its draining. `[verified]` (WP Paleo_Kathmandu_Lake)
- **Medellín:** fills the narrow Aburrá Valley at about 1,500 m. The business district is on the valley floor along the Medellín River, while neighborhoods climb the steep sides and are linked by Metrocable gondolas. `[verified]` (WP Medellín; WP Metrocable_(Medellín))
- **Mexico City:** in the high Valley of Mexico basin at about 2,240 m, on old lakebed.
- **Salt Lake City:** in a valley between the Wasatch and Oquirrh ranges.
```yaml
engine_hint: {relief: "mountainous rim, flat floor", valley_axis: "N-S or E-W", river: "single along axis", developable_fraction: low}
```

### 1.17 Fjord / drowned valley
A **fjord** is a glacially carved, steep-walled valley flooded by the sea, usually deep and U-shaped. A **ria** is a river-cut valley that the sea flooded. The two look similar but have different origins.
- **Bergen:** "the city between the seven mountains" (Ulriken, the highest, is 643 m), facing fjords and islands. It is the old Hanseatic port of Bryggen and very rainy. `[verified]` for the mountains; rainfall figures vary `[hedge]` (lifeinnorway.net/bergen-facts)
- **Oslo:** sits at the head of the Oslofjord, which **is not a true glacial fjord**. NASA describes it as a tectonic rift valley. `[verified]` (earthobservatory.nasa.gov/images/46940)
- **Kotor (Montenegro):** the Bay of Kotor is often called "Europe's southernmost fjord", but it is actually a ria, a river canyon drowned by rising sea. `[verified]` (earthobservatory.nasa.gov/images/90926)
- **Sydney, Auckland, San Francisco:** rias or drowned river valleys. `[verified]` (UCMP Berkeley; Bay Nature; WP Auckland_isthmus)
```yaml
engine_hint: {coast_ruggedness: fjordic, inlet_long_narrow: true, relief: steep, flat_land: "thin strip at inlet head/shore"}
```

### 1.18 Lakeshore
A large lake gives fresh water, fisheries and calm-water shipping without ocean storms. Lake cities often follow the shoreline in a grid and push parks or landfill onto the waterfront.
- **Chicago:** built on flat, wet ground at the lakeshore. The city raised its street grade from the 1850s and **reversed the Chicago River** in 1900 to keep sewage out of its drinking water. `[verified]` (WP Chicago_River; mwrd.org)
- **Geneva:** at the outlet where the Rhône leaves Lake Geneva.
- **Toronto:** on Lake Ontario, sheltered by the Toronto Islands, a former sandspit.
- **Madison:** between two lakes (see isthmus).
```yaml
engine_hint: {water_side: one, water_type: lake, beach: gentle, waves: low, outflow_river: optional}
```

### 1.19 Coastal plain with barrier islands
Gentle coasts with plenty of sediment grow long sandy **barrier islands** separated from the mainland by lagoons and marsh. In the U.S. they run along the Gulf and Atlantic coasts as far north as Long Island. `[verified]` (encyclopedia.com "Barrier islands"; USGS PP 1156) Resort and port towns build on the islands themselves. These are exposed to hurricanes and erosion.
- **Galveston:** on a barrier island about 28 miles long. After the 1900 hurricane killed at least 6,000 people, the city built a seawall and **raised its grade with dredged fill**, jacking up about 2,000 buildings. `[verified]` (asce.org Galveston Seawall and Grade Raising; inventionandtech.com)
- **Miami Beach:** a barrier island developed in the 1910s.
- **Atlantic City:** on Absecon Island.
- **Padre Island (Texas):** often called the world's longest barrier island. `[hedge]`
```yaml
engine_hint: {relief: flat, coast_ruggedness: smooth, barrier_islands: true, barrier_offset: "1-5 km", inlets: few, lagoon_marsh: true}
```

---

## 2. Terrain Archetypes

### How to read the archetype blocks
- **`water_coverage_pct`** is the target share of the map tile that is water, as an engine heuristic.
- **Relief classes:**

| Class | Local relief across the map | Slopes |
|---|---|---|
| `flat` | < 20 m | mostly < 2% |
| `gentle` | 20–80 m | mostly < 5% |
| `rolling` | 80–150 m | 5–10% common |
| `hilly` | 150–400 m | 10–25% common |
| `steep` | 400–1,000 m | large areas > 25% |
| `mountainous` | > 1,000 m | |

  Planning codes commonly treat slopes under about 10–15% as freely buildable, 15–25% as buildable with special design, and 25–30% or more as generally unsuitable. (Greenville, IL code at codelibrary.amlegal.com; Williamsburg, VA comprehensive plan at williamsburgva.gov; Carlsbad, CA hillside guidelines)
- **`elevation_m`** is the typical elevation range of the developed area above sea level.
- **`existing_engine_preset`** points to `apps/worker/src/city_worker/terrain/geographic_presets.py`.

---

### 2.1 `coastal` (existing)
**Physical description:** an open, fairly straight coast on one side, usually a sandy or rocky shore on a coastal plain. Bays are small, and barrier islands appear on gentle coasts. Typically one river reaches the sea. Relief runs from flat to rolling, and hills or an escarpment sometimes sit behind the plain.

**City form:**
- The historic core sits at a river mouth or a small cove, often just above the beach.
- Growth runs **along the coast** as a linear "ribbon" (resort strips, coast roads), then backfills inland.
- Hills behind the plain cap growth and become affluent districts with views.
- Constraints include storm surge, erosion and the lack of a sheltered harbor, which often leads to artificial breakwaters.

**Examples:**
- **Barcelona:** the Pla de Barcelona is a coastal plain boxed in by the Llobregat and Besòs rivers and the Collserola hills. Cerdà's Eixample grid filled it.
- **Tel Aviv:** founded in 1909 on coastal dunes. It grew as a linear beach city.
- **Rio de Janeiro (ocean side):** a beach crescent squeezed between ocean and granite hills.
- **Durban, Nice, Los Angeles:** coastal plains backed by hills or mountains.

```yaml
id: coastal
status: existing
water_coverage_pct: [20, 40]
relief: [flat, rolling]
elevation_m: [0, 100]
typical_slope_pct: [0, 8]
coastline: {ruggedness: smooth-to-moderate, features: [beach, small_bays, optional_barrier_islands]}
water_features: [ocean_one_side, 0-2 rivers, optional_lagoon]
downtown_at: "river mouth or cove, just inland of beach"
growth: "linear along coast, then inland"
tagline: "Coastal: sun, sand, and a long seaside promenade. Think Barcelona, Tel Aviv, Nice."
existing_engine_preset: {water_level: 0.35, beach_enabled: true, bay_enabled: true, barrier_islands_enabled: true}
```

### 2.2 `bay_harbor` (existing)
**Physical description:** a large, sheltered body of water partly enclosed by headlands or a peninsula, with a narrow mouth. The shoreline is often indented, with coves and secondary inlets, and is frequently a drowned river valley. Rolling to hilly land rings the water, and islands may sit inside the bay.

**City form:**
- Downtown faces the harbor on the **most sheltered shore**, with piers and wharves along it.
- The city wraps around the bay and leapfrogs to the far shore by ferry, then by bridges or tunnels (Sydney Harbour Bridge, Golden Gate, Bay Bridge).
- Hills ringing the harbor become view neighborhoods.
- Landfill extends the waterfront, as in much of San Francisco's bayside and Boston.

**Examples:**
- **San Francisco:** the bay is a drowned river valley that the sea entered through the Golden Gate about 10,000–11,000 years ago. `[verified]` (pubs.usgs.gov/pp/1014; baynature.org)
- **Sydney:** a branching ria with a very long shoreline. `[verified]`
- **Halifax:** one of the world's great ice-free harbours, guarded from Citadel Hill. `[verified]`
- **Rio de Janeiro:** Portuguese navigators in 1502 mistook Guanabara Bay for a river mouth, hence "River of January". `[verified]` (EB Rio-de-Janeiro-Brazil) Sugarloaf marks the entrance.
- **Hong Kong:** Victoria Harbour between Hong Kong Island and Kowloon.
- **Cape Town:** the Dutch East India Company refreshment station of 1652 on Table Bay, below Table Mountain.

```yaml
id: bay_harbor
status: existing
water_coverage_pct: [30, 50]
relief: [rolling, hilly]
elevation_m: [0, 300]
typical_slope_pct: [2, 20]
coastline: {ruggedness: moderate-high, features: [enclosed_bay, narrow_mouth, headlands, coves, optional_bay_islands]}
water_features: [bay, ocean_beyond_mouth, 0-2 rivers_into_bay]
downtown_at: "sheltered inner shore of bay"
growth: "wraps around bay; ferries then bridges to far shore; hills ring harbor"
tagline: "Bay / Harbor: sheltered water, busy docks. Think San Francisco, Sydney, Halifax."
existing_engine_preset: {water_level: 0.38, bay_min_concavity_angle: 25, bay_erosion_strength: 1.2, barrier_islands_enabled: false}
```

### 2.3 `river_valley` (existing)
**Physical description:** a single major river crossing the map, with a floodplain and terraces on either side and valley walls, bluffs or hills beyond. Water coverage is low. Valleys are often **asymmetric**, with steep bluffs on one bank and a flat floodplain on the other.

**City form:**
- The old core sits on a terrace or bluff just above flood level, at a crossing point.
- The city grows **along the valley axis**, and bridges stitch the two banks together.
- The flat bank fills in with industry and grids, while the bluff side gets castles, parks and wealthy housing.
- Flood levees and riverfront promenades are common.

**Examples:**
- **Budapest:** hilly Buda on the west bank and flat Pest on the east. Elevation runs from 96 m at the Danube to 527 m on János-hegy. The towns merged in 1873. `[verified]` (WP Budapest)
- **Paris:** grew outward from river islands across the Seine's meanders.
- **Cairo:** the Nile Valley at the apex of the delta. Ancient Memphis guarded the point where valley meets delta. `[verified]`, secondary sources
- **Kyiv:** stands on high bluffs on the Dnieper's west bank above a flat east bank.
- **Prague:** the Vltava valley, with the castle hill on one bank.

```yaml
id: river_valley
status: existing
water_coverage_pct: [3, 12]
relief: [gentle, hilly]
elevation_m: [20, 500]
typical_slope_pct: [0, 15]
coastline: none
water_features: [1 major river, 0-3 tributaries, optional_oxbows, optional_river_islands]
river_course: [straight, meandering]
downtown_at: "terrace/bluff above floodplain at crossing"
growth: "linear along valley; bridges link banks; bluff vs floodplain contrast"
tagline: "River Valley: one big river, many bridges. Think Budapest, Paris, Prague."
existing_engine_preset: {water_level: 0.28, min_river_length: 6, beach_enabled: false, bay_enabled: false}
```

### 2.4 `lakefront` (existing)
**Physical description:** a large freshwater lake on one side, with a gentle beach or low bluffs. There is no tide and the waves are modest. There may be an outflow river, and smaller lakes or wetlands may lie inland. Relief is flat to rolling, from glacial landscapes.

**City form:**
- Downtown sits on the shore, often at a river mouth.
- A grid runs back from the shoreline, and the lakefront becomes parks, beaches and landfill.
- The city grows in a **half-ring** around its lakefront core.

**Examples:**
- **Chicago:** a flat lakeshore. The city raised its grade and reversed its river. `[verified]`
- **Toronto:** on Lake Ontario behind the Toronto Islands.
- **Geneva:** the Rhône outflow from Lake Geneva.
- **Zurich:** at the outlet of Lake Zurich, where the Limmat leaves.
- **Madison:** two lakes with an isthmus between.
- **Kisumu:** on Lake Victoria.

```yaml
id: lakefront
status: existing
water_coverage_pct: [15, 35]
relief: [flat, rolling]
elevation_m: [50, 600]
typical_slope_pct: [0, 6]
coastline: {ruggedness: smooth, features: [gentle_beach, optional_low_bluffs, optional_sandspit]}
water_features: [large_lake_one_side, 0-1 outflow_river, 2-8 small_inland_lakes]
downtown_at: "lakeshore, often at river mouth/outflow"
growth: "half-ring around lakefront; grid back from shore"
tagline: "Lakefront: big fresh water, no tides, endless shoreline parks. Think Chicago, Toronto, Geneva."
existing_engine_preset: {water_level: 0.34, bay_enabled: false, barrier_islands_enabled: false, max_lakes: 8}
```

### 2.5 `inland` (existing)
**Physical description:** no coast. Water is limited to streams or a small river, so water coverage is low. These cities sit on plains, plateaus or ridges and were placed by **situation**: railroads, mines, crossroads or political choice.

**City form:**
- Growth is roughly **concentric or star-shaped** along highways and rail lines, with few natural barriers.
- Terrain is the main constraint, such as a ridge line or an escarpment.

**Examples:**
- **Johannesburg:** founded in the 1886 Witwatersrand gold rush. It is often called the largest city not on a river, lake or coastline. `[verified]` (WP Witwatersrand_Gold_Rush; uj.ac.za); the superlative itself is `[hedge]`
- **Madrid:** a central plateau capital on the Meseta.
- **Atlanta:** founded as "Terminus" of a railroad in 1837.
- **Denver:** the "Mile High City" at the edge of the Plains below the Rockies.
- **Brasília:** a planned capital on the central plateau, inaugurated in 1960.

```yaml
id: inland
status: existing
water_coverage_pct: [0, 4]
relief: [flat, rolling]
elevation_m: [200, 2500]
typical_slope_pct: [0, 8]
coastline: none
water_features: [0-2 small rivers or creeks, 0-2 reservoirs]
downtown_at: "crossroads / railhead / ridge"
growth: "concentric or star along transport corridors"
tagline: "Inland: no coast, all crossroads. Think Johannesburg, Madrid, Denver."
existing_engine_preset: {water_level: 0.15, height_scale: 0.2515, beach_enabled: false}
```

### 2.6 `island` (existing)
**Physical description:** land surrounded by water. It may be one main island or a cluster. Shores are rocky or sandy, and there may be a central spine of hills or a volcanic peak. Rivers are short.

**City form:**
- The old core sits at the best harbor on the island, usually the sheltered side facing the mainland.
- Land is scarce, so cities build up (skyscrapers) and out (**land reclamation**).
- Bridges, tunnels and ferries tie the island to the mainland, and the ring road follows the shore.

**Examples:**
- **Manhattan:** a dense grid on a narrow island between the Hudson and East rivers.
- **Singapore:** reclamation has grown its land area by roughly 20–25% since the 1960s. `[hedge]` (WP Land_reclamation_in_Singapore)
- **Mumbai:** seven islands merged over about 150 years. The Hornby Vellard (begun 1782) closed the "Great Breach". `[verified]` (WP Hornby_Vellard)
- **Montreal:** a river island with Mount Royal (233 m) at its center.
- **Malé:** a whole capital on one small coral island.
- **Hong Kong Island:** steep slopes, with the city on a narrow shelf and reclaimed waterfront.

```yaml
id: island
status: existing
water_coverage_pct: [50, 80]
relief: [gentle, steep]
elevation_m: [0, 500]
typical_slope_pct: [0, 25]
coastline: {ruggedness: moderate, features: [beaches, coves, optional_offshore_islets, optional_reef]}
water_features: [water_all_sides, short_streams, optional_harbor_inlet]
downtown_at: "most sheltered harbor facing mainland"
growth: "densify upward + reclaim land; bridges/tunnels to mainland"
tagline: "Island: water on every side, bridges to everywhere. Think Manhattan, Singapore, Montreal."
existing_engine_preset: {water_level: 0.42, beach_width_multiplier: 1.3, barrier_islands_enabled: true}
```

### 2.7 `peninsula` (existing)
**Physical description:** land jutting into water, with water on three sides and a neck connecting it to the mainland. The tip is often hilly or rocky. Harbors form in the bays on either side of the neck.

**City form:**
- The old town sits at or near the **tip**, which is the most defensible spot with the best harbor access.
- Growth runs back toward the neck, and the narrow neck becomes a bottleneck for traffic and walls.
- Landfill widens the neck over time. Bridges reach across to adjacent shores.

**Examples:**
- **San Francisco:** water on three sides at the tip of a peninsula.
- **Boston:** the Shawmut Peninsula (about 789 acres), joined by a narrow neck, was **more than doubled** by landfill, Back Bay being the largest project. Overall, Boston's land area has more than tripled since 1630. `[verified]` (WP Back_Bay,_Boston; historyofmassachusetts.org)
- **Istanbul (historic peninsula):** bounded by the Golden Horn, the Bosphorus and the Sea of Marmara. Its seven hills echo Rome's. `[verified]` (WP Seven_hills_of_Istanbul)
- **Valletta:** a grid city built on the Sciberras peninsula from 1566, after the Great Siege. `[verified]` (WP Valletta)
- **Halifax:** the peninsula between the harbour and the Northwest Arm.

```yaml
id: peninsula
status: existing
water_coverage_pct: [40, 65]
relief: [rolling, hilly]
elevation_m: [0, 300]
typical_slope_pct: [2, 20]
coastline: {ruggedness: moderate, features: [tip_headland, bays_either_side_of_neck, narrow_neck]}
water_features: [water_three_sides, 0-1 rivers]
downtown_at: "near the tip"
growth: "from tip back toward neck; landfill widens neck; bridges across"
tagline: "Peninsula: water on three sides, one way out. Think San Francisco, Boston, Valletta."
existing_engine_preset: {water_level: 0.40, bay_min_concavity_angle: 40, barrier_islands_enabled: false}
```

### 2.8 `delta` (existing)
**Physical description:** very flat, low land (often 0–10 m) where a river splits into **many distributary channels** before reaching the sea. It has marshes, natural levees, shifting islands, sometimes barrier islands, and a lobed or bird's-foot coast.

**City form:**
- The core sits on **natural levees**, the slightly higher banks of the main channel, or at the **apex** where the delta begins.
- Growth spreads onto drained marsh behind levees and pumps.
- The city depends on canals, dikes and drainage. Subsidence and flood risk shape everything.
- Many bridges are needed because channels cut the land into islands.

**Examples:**
- **New Orleans:** built on the natural levee of the Mississippi's crescent. Much of the city lies at or below sea level. `[verified]` / `[hedge]`
- **Rotterdam:** Rhine–Meuse delta, Europe's largest port. `[verified]`
- **Dhaka:** Ganges–Brahmaputra delta, ringed by rivers. `[verified]`
- **Shanghai:** on the Huangpu at the Yangtze delta.
- **Kolkata:** on the Hooghly distributary of the Ganges.
- **Cairo:** at the delta apex. `[verified]`, secondary sources

```yaml
id: delta
status: existing
water_coverage_pct: [30, 55]
relief: [flat]
elevation_m: [-5, 15]
typical_slope_pct: [0, 1]
coastline: {ruggedness: lobed-or-birdfoot, features: [distributary_mouths, marsh, optional_barrier_islands, mudflats]}
water_features: [main_channel, 3-8 distributaries, wetlands, oxbows, optional_lagoon]
river_course: braided_or_branching
downtown_at: "natural levee of main channel or delta apex"
growth: "onto drained marsh behind levees; canals; many bridges"
tagline: "Delta: where the river fans out and the land barely rises. Think New Orleans, Rotterdam, Dhaka."
existing_engine_preset: {water_level: 0.33, height_scale: 0.1886, min_river_length: 4, bay_river_mouth_factor: 3.0, barrier_islands_enabled: true}
```

---

### Candidate new archetypes

### 2.9 `fjord` (candidate)
**Physical description:** a long, narrow, deep sea inlet with steep walls rising to mountains. Usable flat land is limited to the head of the inlet, river deltas at side valleys, and a thin shore shelf. The coast is extremely rugged and branching, with many islands at the mouth. Waterfalls come off hanging valleys.

**City form:**
- The town clings to the shore and the delta at the fjord head or a side bay, with the harbor right at the center.
- Growth climbs the slopes on switchbacks and funiculars, or runs along the shore.
- Tunnels and ferries replace roads. Very little flat land is available.

**Examples:**
- **Bergen:** between seven mountains and fjords, with the Bryggen wharf and the Fløyen funicular. `[verified]`
- **Trondheim:** on Trondheimsfjord at the mouth of the Nidelva.
- **Juneau (Alaska):** squeezed between the Gastineau Channel and mountains. No road links it to the rest of North America.
- **Vancouver / Seattle:** glacially carved inlets and sounds (Burrard Inlet, Puget Sound). These are looser examples.
- Note that Oslo and Kotor look the part but are geologically a rift and a ria respectively. `[verified]`

```yaml
id: fjord
status: candidate
water_coverage_pct: [25, 45]
relief: [steep, mountainous]
elevation_m: [0, 1200]
typical_slope_pct: [10, 60]
coastline: {ruggedness: fjordic, features: [long_narrow_inlet, side_arms, skerries_islands_at_mouth, head_delta]}
water_features: [sea_inlet, short_steep_rivers, waterfalls, optional_glacial_lakes]
downtown_at: "inlet head or side-bay delta"
growth: "along shore + up slopes; tunnels/ferries"
tagline: "Fjord: mountains plunge straight into the sea. Think Bergen, Trondheim, Juneau."
engine_notes: "Needs high coastline ruggedness and a dendritic inlet carved through high relief; flat land only at inlet head/side deltas."
```

### 2.10 `mountain_valley` (candidate)
**Physical description:** an enclosed basin or long valley ringed by mountains, with a river or lake on the floor. There are steep sides and alluvial fans at side-valley mouths. Water coverage is low, though there may have been an ancient lakebed.

**City form:**
- Downtown sits on the flat floor, near the river or at a crossing.
- Sprawl fills the floor, then climbs the fans and slopes, with informal settlements on the steepest sides.
- Transit must climb (Medellín's gondolas). Inversions trap air pollution, and the long axis channels transport.

**Examples:**
- **Kathmandu:** a former lakebed valley. `[verified]`
- **Medellín:** a narrow Andean valley at about 1,500 m. `[verified]`
- **Innsbruck:** the Inn valley on the Brenner route. `[verified]`
- **Salt Lake City:** a valley below the Wasatch Front.
- **Mexico City:** a high basin on drained lakes at about 2,240 m.
- **Quito:** a long, narrow Andean valley at about 2,850 m.

```yaml
id: mountain_valley
status: candidate
water_coverage_pct: [1, 8]
relief: [mountainous]
elevation_m: [500, 3000]
typical_slope_pct: [0, 5] # floor; walls 25-60
coastline: none
water_features: [1 axial river, side_streams, optional_lake_or_lakebed]
downtown_at: "valley floor near river/crossing"
growth: "fills floor, then climbs fans and slopes"
tagline: "Mountain Valley: peaks on every side, the city in the bowl. Think Kathmandu, Medellín, Innsbruck."
engine_notes: "High rim + flat floor mask; developable area = floor; slopes >25% unbuildable."
```

### 2.11 `archipelago` (candidate)
**Physical description:** many islands, from a few to dozens, separated by channels, straits or a lagoon. Each island has a short coastline, and water is everywhere between them.

**City form:**
- Each island becomes a district, and the main island holds the old core.
- **Bridges and ferries** are the city's skeleton.
- Canals between islands may be dug or straightened, and growth jumps from island to island.

**Examples:**
- **Stockholm:** 14 islands where a lake meets the Baltic, plus a vast outer archipelago. `[verified]`
- **Venice:** about 118 lagoon islands. `[verified]`
- **St. Petersburg:** founded in 1703 on the islands of the Neva delta. The count is "33" or "42" depending on the register, versus 101 in the 19th century. `[hedge]` (EB St-Petersburg-Russia/History; whc.unesco.org/en/list/540)
- **Hong Kong:** more than 260 islands.
- **Amsterdam:** about 90 islands created by the canal ring. `[verified]` (multiple)

```yaml
id: archipelago
status: candidate
water_coverage_pct: [45, 70]
relief: [flat, rolling]
elevation_m: [0, 100]
typical_slope_pct: [0, 10]
coastline: {ruggedness: high, features: [many_islands, channels, straits]}
water_features: [channels_between_islands, optional_lake_to_sea_link, optional_lagoon]
island_count: [5, 40]
downtown_at: "central/oldest island"
growth: "island-hopping via bridges; canals"
tagline: "Archipelago: a city of islands stitched by bridges. Think Stockholm, Venice, St. Petersburg."
```

### 2.12 `estuary` (candidate)
**Physical description:** a river widening into a long, funnel-shaped tidal mouth. There are mudflats, salt marsh and sandbanks, and a strong tidal range. The banks are low, and the sea is out of view, down-estuary.

**City form:**
- The port and old core sit at the **lowest bridging point** or a deep-water bend, well upriver for shelter.
- Docks march downstream toward the sea as ships grow larger (London's docks moved to Tilbury; Rotterdam's to Europoort).
- One bank is often industrial and the other residential.

**Examples:**
- **London:** a gravel-terrace crossing on the tidal Thames. `[verified]`
- **Hamburg:** a tidal port 110 km or more up the Elbe. `[verified]` / `[hedge]`
- **Lisbon:** on the Tagus estuary and its Mar da Palha. `[verified]`
- **Buenos Aires:** on the Río de la Plata.
- **Quebec City:** at the narrows where the St. Lawrence estuary begins. The name probably comes from an Algonquian word for "narrowing of the river". `[verified]` (thecanadianencyclopedia.ca)

```yaml
id: estuary
status: candidate
water_coverage_pct: [15, 35]
relief: [flat, rolling]
elevation_m: [0, 100]
typical_slope_pct: [0, 6]
coastline: {ruggedness: smooth, features: [funnel_mouth, mudflats, salt_marsh, sandbanks]}
water_features: [1 river widening toward map edge, tidal_creeks, docks]
downtown_at: "lowest bridging point / deep bend"
growth: "docks migrate downstream; banks differ"
tagline: "Estuary: where the river tastes the sea. Think London, Hamburg, Lisbon."
```

### 2.13 `confluence` (candidate)
**Physical description:** two or three rivers meeting, which forms a wedge or tongue of land at the junction. The land may be a low point between rivers or a raised bluff overlooking them. The valleys run in different directions.

**City form:**
- Downtown fills the **wedge**, with a fort or park at the tip.
- The city spreads up each valley like a "Y", and bridges cross every arm.
- Hills between the valleys become separate neighborhoods.

**Examples:**
- **Pittsburgh:** the Golden Triangle at the Forks of the Ohio. `[verified]`
- **Khartoum:** the Blue and White Niles meet at al-Mogran. `[verified]`
- **Lyon:** the Presqu'île between the Rhône and Saône. `[verified]`
- **Belgrade:** Sava and Danube, with the Kalemegdan fortress. `[verified]`
- **Chongqing:** a hilly peninsula between the Jialing and Yangtze, the "mountain city". `[verified]` (WP Yuzhong_District)
- **Wuhan:** the Han meets the Yangtze. The three towns of Wuchang, Hankou and Hanyang give the name ("Wu" plus "Han"). `[verified]` (newworldencyclopedia.org/entry/Wuhan)
- **Winnipeg:** The Forks, a meeting place for at least 6,000 years. `[verified]` (pc.gc.ca; winnipeg.ca)
- **Koblenz, Passau ("City of Three Rivers"), Prayagraj (Ganges and Yamuna, the Sangam):** further confluence cities.

```yaml
id: confluence
status: candidate
water_coverage_pct: [5, 15]
relief: [gentle, hilly]
elevation_m: [20, 400]
typical_slope_pct: [0, 20]
coastline: none
water_features: [2-3 rivers joining, optional_river_island_at_junction]
river_course: [straight, meandering]
downtown_at: "wedge/tongue between rivers"
growth: "Y-shaped up each valley; bridges on every arm"
tagline: "Confluence: two rivers shake hands downtown. Think Pittsburgh, Lyon, Khartoum."
```

### 2.14 `desert_oasis` (candidate)
**Physical description:** arid land with almost no surface water except a spring, a short river fed by mountains, or groundwater (karez/qanat). There is a sharp edge between the green irrigated zone and the desert. Mountains or a basin rim are often on one side.

**City form:**
- The old city sits **at the water source**, surrounded by orchards and gardens.
- Modern growth pushes out into the desert on pumped water, and the green belt shrinks. (Damascus's Ghouta has been shrinking under urban expansion. `[verified]`)
- Caravan routes enter at the gates.

**Examples:**
- **Damascus:** the Barada and the Ghouta oasis. `[verified]`
- **Las Vegas:** "the meadows", springs on the Old Spanish Trail. `[verified]`
- **Timbuktu:** the edge of the Sahara near the Niger, where camel caravans met river boats. `[verified]` (worldhistory.org/timbuktu)
- **Kashgar:** a Silk Road oasis at the western edge of the Tarim Basin.
- **Siwa:** an oasis in Egypt's Western Desert, home of the oracle of Amun.
- **Palm Springs:** grew at the Agua Caliente hot springs.

```yaml
id: desert_oasis
status: candidate
water_coverage_pct: [0, 3]
relief: [flat, rolling]
elevation_m: [-150, 1500]
typical_slope_pct: [0, 5]
coastline: none
water_features: [spring_or_short_river, irrigation_canals, optional_playa_or_salt_lake]
vegetation: "green ring around water, desert beyond"
downtown_at: "at the spring/river"
growth: "outward into desert on pumped water; green belt shrinks"
tagline: "Desert Oasis: one spring, a thousand palms. Think Damascus, Las Vegas, Timbuktu."
```

### 2.15 `canyon` (candidate)
**Physical description:** a river incised deeply into a plateau or between cliffs. The rim and the canyon floor are both flat, separated by near-vertical walls. The floor is narrow and the rim may be broad.

**City form:**
- The city sits either **on the rim**, defended by the gorge and joined across it by spectacular bridges, or **in the canyon**, where it is linear along the river and climbs the walls.
- Elevation strongly sorts neighborhoods.

**Examples:**
- **La Paz:** spills down a canyon below the Altiplano at about 3,600 m. El Alto sits on the plateau above. It is the world's highest de facto capital. `[verified]` (guinnessworldrecords.com/world-records/65059-highest-capital); the canyon description is from general sources `[hedge]`
- **Ronda (Spain):** split by El Tajo gorge, about 120 m deep, and joined by the Puente Nuevo (completed 1793). `[verified]` (WP Puente_Nuevo)
- **Constantine (Algeria):** a plateau city wrapped by the Rhumel gorge. `[verified]`
- **Petra:** the Nabataean city entered through the Siq canyon. It ran on rock-cut channels and cisterns, and a tunnel diverted floods from the Siq. `[verified]` (amnh.org; historyhit.com)
- **Cuenca (Spain):** "hanging houses" over the Huécar gorge.

```yaml
id: canyon
status: candidate
water_coverage_pct: [1, 6]
relief: [steep]
elevation_m: [200, 4000]
typical_slope_pct: [0, 5] # rim & floor; walls 60+
coastline: none
water_features: [1 incised river, optional_waterfalls]
downtown_at: "rim edge (defensive) or canyon floor (linear)"
growth: "along rim or along floor; bridges across gorge"
tagline: "Canyon: a city on the edge, held together by bridges. Think Ronda, Constantine, La Paz."
engine_notes: "Terrace heightmap: plateau surface cut by a narrow, deep river trench; bridges are hero features."
```

### 2.16 `lagoon` (candidate)
**Physical description:** shallow, calm water behind a barrier of sand islands or spits, connected to the sea by one or a few inlets. It has marsh islands and mudflats, and the land is very low.

**City form:**
- The core sits on islands or sandbars **inside** the lagoon, protected from the sea.
- Bridges and causeways reach the mainland, and canals replace streets (Venice).
- Ports require dredged inlets (Abidjan's Vridi Canal). The barrier island becomes a beach or resort strip (Venice Lido, Lagos's Victoria Island).

**Examples:**
- **Venice:** islands on timber piles. `[verified]`
- **Lagos:** Lagos Island and Victoria Island at the lagoon mouth. `[verified]`
- **Abidjan:** the Plateau business district on the Ébrié Lagoon. `[verified]`
- **Tenochtitlan:** lake rather than lagoon, but the same island-city logic.

```yaml
id: lagoon
status: candidate
water_coverage_pct: [40, 60]
relief: [flat]
elevation_m: [0, 10]
typical_slope_pct: [0, 2]
coastline: {ruggedness: smooth_outer, features: [barrier_islands_or_spits, 1-3 inlets, marsh_islands]}
water_features: [lagoon, sea_beyond_barrier, optional_river_into_lagoon]
downtown_at: "island inside the lagoon"
growth: "causeways to mainland; canals; dredged inlets; resort strip on barrier"
tagline: "Lagoon: calm water behind the dunes, canals for streets. Think Venice, Lagos, Abidjan."
```

---

## 3. Spatial Vocabulary → Parameter Mapping

### 3.1 Proposed parameter schema (for the World Brief)
```yaml
water_side: [N, NE, E, SE, S, SW, W, NW]  # list; [] = landlocked; "all" = island
water_type: ocean | bay | lake | lagoon | estuary | fjord | none
coast_ruggedness: smooth | moderate | rugged | fjordic          # 0.0-1.0 if numeric
water_coverage_pct: 0-80
relief: flat | gentle | rolling | hilly | steep | mountainous
relief_focus: none | center | ring | one_side(N/E/S/W) | ridge(axis) | scattered
rivers:
  - course: straight | meandering | braided | branching(delta)
    from: N|E|S|W|NE|...   # entry edge
    to: N|E|S|W|... | coast
    size: creek | river | major
    joins: <river index or null>   # for confluences
lakes: {count: 0-8, size: small | medium | large}
islands_offshore: {count: 0-40, type: barrier | rocky | bay_islands | archipelago}
special: [harbor_mouth, isthmus, peninsula_tip, meander_loop, gorge, plateau, rapids, spring]
```

### 3.2 Phrase → parameter table

| User phrase | Parameter mapping |
|---|---|
| "ocean to the east", "faces the sea", "on the Atlantic side" | `water_side: [E]`, `water_type: ocean` |
| "coastal city", "on the coast", "seaside" | `water_side: [one side]` (pick from context or default S/E), `water_coverage_pct: 25–35` |
| "landlocked", "inland", "in the middle of nowhere", "prairie town" | `water_side: []`, `water_type: none`, `water_coverage_pct: 0–4` |
| "island city", "surrounded by water" | `water_side: all` |
| "peninsula", "juts into the sea", "water on three sides" | `water_side: [3 sides]`, `special: [peninsula_tip]` |
| "on a narrow neck", "between two lakes/seas", "isthmus" | `water_side: [opposite pair]`, `special: [isthmus]` |
| "sheltered bay", "natural harbor", "protected harbor" | `water_type: bay`, `special: [harbor_mouth]`, `coast_ruggedness: moderate–rugged` |
| "rocky coast", "craggy", "cliffs", "rugged shoreline" | `coast_ruggedness: rugged`, `relief: hilly+` near coast |
| "long sandy beaches", "smooth coastline" | `coast_ruggedness: smooth`, beach on |
| "barrier islands", "sandbars offshore", "Outer Banks–style" | `islands_offshore: {type: barrier, count: 2–6}` |
| "fjords", "deep inlets", "mountains plunge into the sea" | `water_type: fjord`, `coast_ruggedness: fjordic`, `relief: steep–mountainous` |
| "lagoon", "calm water behind dunes" | `water_type: lagoon`, `islands_offshore: barrier` |
| "river runs through it", "river through downtown" | `rivers: [{course: meandering, size: river}]`, downtown on it |
| "river cuts diagonally (NW→SE)" | `rivers: [{from: NW, to: SE}]` |
| "lazy/winding/snaking river", "meanders", "oxbows" | `course: meandering` (sinuosity ≥ 1.5) |
| "straight river", "canal-like" | `course: straight` |
| "braided river", "gravel bars", "many channels" | `course: braided` |
| "river mouth", "where the river meets the sea" | river `to: coast` + estuary or delta |
| "delta", "river splits into many channels", "marshy mouth" | `course: branching`, `relief: flat`, distributaries 3–8 |
| "where two rivers meet", "fork", "confluence" | 2 rivers with `joins`; downtown at the wedge |
| "river loop", "town in a bend" | `special: [meander_loop]` |
| "rapids", "waterfall", "falls" | `special: [rapids]`, relief step across the river |
| "gorge", "canyon", "ravine" | `special: [gorge]`, `relief: steep` along the river |
| "flat", "pancake-flat", "floodplain", "prairie" | `relief: flat` |
| "gently rolling", "low hills" | `relief: gentle/rolling` |
| "hilly", "seven hills", "steep streets" | `relief: hilly`, `relief_focus: scattered/center` |
| "hills ring the harbor", "amphitheater of hills" | `relief_focus: ring` around water (Valparaíso, Hong Kong, Rio) |
| "mountains to the west", "backed by mountains" | `relief_focus: one_side(W)`, `relief: steep` on that side |
| "in a valley", "between mountains" | `relief: mountainous`, `relief_focus: ridge` both sides, flat floor |
| "steep bluffs along the river", "high bank" | asymmetric river valley: one bank steep, other flat |
| "on a plateau/mesa", "tableland" | `special: [plateau]`, escarpment ring |
| "castle on a hill", "acropolis", "citadel rock" | `relief_focus: center`, isolated peak near downtown |
| "desert", "oasis", "dry" | `water_coverage_pct: 0–3`, `special: [spring]` |
| "lake to the north", "lakefront" | `water_side: [N]`, `water_type: lake` |
| "lots of little lakes", "lake country" | `lakes: {count: 5–8, size: small}` |
| "islands in the bay" | `islands_offshore: {type: bay_islands, count: 1–4}` |
| "archipelago", "city of islands" | `islands_offshore: {type: archipelago, count: 10–40}`, high water coverage |

### 3.3 Precedence and defaults (guidance for the LLM)
- **A named example city wins over generic words.** "Like Lisbon" implies `water_side: [S]`, an estuary, a hilly relief, and the ocean to the W/SW.
- **Contradictions:** "island" plus "landlocked" should become a river island or lake island (Montreal, Paris's Île de la Cité, Tenochtitlan).
- **Relief vocabulary, ordered:** flat < gentle < rolling < hilly < steep < mountainous.
- **Directional sanity check:** rivers flow downhill toward the water side. If the user says "ocean to the east" and "river flows west", ask the engine to bend the river or treat it as a tributary.
- **Engine reality check:** cities rarely occupy slopes over about 25–30% (planning codes treat these as generally unbuildable). Hilly briefs still need a developable floor or terraces.

---

## 4. City Records

Format notes:
- `water_side` lists the direction(s) of major open water from the historic core.
- `rivers` gives a count, then each river's name and course.
- `relief` uses the classes in section 2.
- Fun facts are written to be product-safe. Keep the hedges.

```yaml
- name: Lisbon
  country: Portugal
  archetypes: [estuary, bay_harbor]
  water_side: [S, SW]
  rivers: {count: 1, list: [{name: Tagus, course: "estuary widening into Mar da Palha"}]}
  relief: hilly
  notable_features: [Tagus estuary, castle hill (São Jorge), steep trams/funiculars, Baixa grid]
  fun_fact: "After the 1755 earthquake, fire and tsunami, Lisbon's flattened lower town was rebuilt as a strict grid (the Baixa Pombalina) with quake-resistant timber cages inside the walls."
  sources: [en.wikipedia.org/wiki/Pombaline_style, en.wikipedia.org/wiki/History_of_Lisbon]

- name: San Francisco
  country: USA
  archetypes: [peninsula, bay_harbor]
  water_side: [N, E, W]
  rivers: {count: 0}
  relief: hilly
  notable_features: [Golden Gate strait, drowned river valley bay, many steep hills, bayside landfill]
  fun_fact: "San Francisco Bay was a river valley until the sea poured in through the Golden Gate about 10,000-11,000 years ago."
  sources: [pubs.usgs.gov/pp/1014, baynature.org/magazine/summer2010/was-there-ever-a-waterfall-at-the-golden-gate]

- name: Sydney
  country: Australia
  archetypes: [bay_harbor]
  water_side: [N, E]
  rivers: {count: 1, list: [{name: Parramatta, course: "drowned valley forming the harbour's western arm"}]}
  relief: rolling
  notable_features: [Port Jackson ria, sandstone headlands, hundreds of km of harbour shoreline]
  fun_fact: "Sydney Harbour is a river valley carved in sandstone and drowned by rising seas after the last Ice Age, which is why it has so many fingers and coves."
  sources: [en.wikipedia.org/wiki/Geography_of_Sydney, en.wikipedia.org/wiki/Port_Jackson]

- name: Halifax
  country: Canada
  archetypes: [bay_harbor, peninsula]
  water_side: [E, S, W]
  rivers: {count: 0}
  relief: rolling
  notable_features: [deep ice-free harbour, Bedford Basin, The Narrows, Citadel Hill drumlin]
  fun_fact: "Citadel Hill, Halifax's star fort hill, is actually a drumlin: a teardrop mound left by a glacier."
  sources: [en.wikipedia.org/wiki/Halifax_Harbour]

- name: Rio de Janeiro
  country: Brazil
  archetypes: [bay_harbor, coastal]
  water_side: [E, S]
  rivers: {count: 0}
  relief: steep
  notable_features: [Guanabara Bay, Sugarloaf, granite domes rising from the shore, ocean beaches]
  fun_fact: "Portuguese sailors arrived on 1 January 1502, mistook Guanabara Bay for a river mouth, and named it 'River of January'."
  sources: [britannica.com/place/Rio-de-Janeiro-Brazil]

- name: Istanbul
  country: Türkiye
  archetypes: [peninsula, bay_harbor]
  water_side: [N, E, S]
  rivers: {count: 0}
  relief: hilly
  notable_features: [Golden Horn harbor, Bosphorus strait, seven hills on the historic peninsula]
  fun_fact: "Like Rome, Constantinople was deliberately described as a city of seven hills, all on its walled historic peninsula."
  sources: [en.wikipedia.org/wiki/Seven_hills_of_Istanbul, en.wikipedia.org/wiki/Golden_Horn]

- name: Hong Kong
  country: China (SAR)
  archetypes: [bay_harbor, archipelago, island]
  water_side: [N, S, E, W]
  rivers: {count: 0}
  relief: steep
  notable_features: [Victoria Harbour, steep island peaks, reclaimed waterfront, 260+ islands]
  fun_fact: "With little flat land between peaks and sea, much of Hong Kong's downtown waterfront sits on reclaimed land."
  sources: [en.wikipedia.org/wiki/Victoria_Harbour]

- name: New York (Manhattan)
  country: USA
  archetypes: [island, estuary, bay_harbor]
  water_side: [E, S, W]
  rivers: {count: 2, list: [{name: Hudson, course: "tidal estuary, straight N-S"}, {name: East River, course: "tidal strait"}]}
  relief: gentle
  notable_features: [Upper New York Bay, Hudson estuary, rigid grid, landfill shoreline]
  fun_fact: "The Hudson is tidal far upstream of the city, so 'downriver' at Manhattan is really an arm of the sea."
  sources: [en.wikipedia.org/wiki/Hudson_River]

- name: Boston
  country: USA
  archetypes: [peninsula, bay_harbor]
  water_side: [E, N]
  rivers: {count: 1, list: [{name: Charles, course: "dammed basin, meandering"}]}
  relief: gentle
  notable_features: [Shawmut Peninsula, Back Bay landfill, leveled hills]
  fun_fact: "Boston leveled its own hills to fill its bays. Back Bay is landfill, and the city's land area has more than tripled since 1630."
  sources: [en.wikipedia.org/wiki/Back_Bay,_Boston, historyofmassachusetts.org/how-boston-lost-its-hills]

- name: Venice
  country: Italy
  archetypes: [lagoon, archipelago]
  water_side: [all]
  rivers: {count: 0}
  relief: flat
  notable_features: [about 118 islands, canals for streets, timber pile foundations, Lido barrier]
  fun_fact: "Venice stands on timber piles driven into lagoon mud. Kept waterlogged and away from air, the wood has lasted for centuries."
  sources: [britannica.com/summary/Venice, engineeringrome.org/in-the-beginning-was-a-marsh-the-history-of-venices-foundation-and-materials]

- name: Stockholm
  country: Sweden
  archetypes: [archipelago]
  water_side: [E, W]
  rivers: {count: 0}
  relief: rolling
  notable_features: [14 islands, Lake Mälaren to the west, Baltic to the east, Gamla stan]
  fun_fact: "Stockholm grew where Lake Mälaren drains into the Baltic. Whoever held the islands controlled traffic between lake and sea."
  sources: [britannica.com/place/Stockholm, en.wikipedia.org/wiki/Geography_of_Stockholm]

- name: St. Petersburg
  country: Russia
  archetypes: [delta, archipelago]
  water_side: [W]
  rivers: {count: 1, list: [{name: Neva, course: "short delta with many branches and canals"}]}
  relief: flat
  notable_features: [Neva delta islands, canals, hundreds of bridges, Peter and Paul Fortress]
  fun_fact: "Peter the Great founded the city in 1703 on marshy delta islands. Counts range from 33 to 42 islands today, versus 101 in the 19th century."
  sources: [britannica.com/place/St-Petersburg-Russia/History, gw2ru.com/travel/2442-petersburg-33-islands]

- name: Amsterdam
  country: Netherlands
  archetypes: [delta, archipelago]
  water_side: [N]
  rivers: {count: 1, list: [{name: Amstel, course: "dammed, straight into the IJ"}]}
  relief: flat
  notable_features: [dam on the Amstel, 17th-c. canal ring, about 90 canal islands]
  fun_fact: "The name means 'dam on the Amstel'. Dam Square marks the spot, first recorded around 1275."
  sources: [etymonline.com/word/amsterdam, theculturetrip.com/europe/netherlands/articles/why-is-amsterdam-called-amsterdam]

- name: Bergen
  country: Norway
  archetypes: [fjord]
  water_side: [W, N]
  rivers: {count: 0}
  relief: mountainous
  notable_features: [seven mountains, Bryggen Hanseatic wharf, Fløyen funicular, fjord approaches]
  fun_fact: "Bergen calls itself the city between seven mountains. Locals still argue about which seven count. Ulriken is the tallest at 643 m."
  sources: [lifeinnorway.net/bergen-facts]

- name: Seattle
  country: USA
  archetypes: [isthmus, bay_harbor, fjord]
  water_side: [W, E]
  rivers: {count: 0}
  relief: hilly
  notable_features: [Elliott Bay, Puget Sound, Lake Washington, glacial hills, regrades]
  fun_fact: "Seattle literally washed away Denny Hill, sluicing it into Elliott Bay with water jets in phases from 1898 to 1930."
  sources: [en.wikipedia.org/wiki/Regrading_in_Seattle, earthmagazine.org]

- name: Pittsburgh
  country: USA
  archetypes: [confluence, river_valley]
  water_side: []
  rivers: {count: 3, list: [{name: Allegheny, course: "from NE"}, {name: Monongahela, course: "from SE"}, {name: Ohio, course: "formed at junction, flows NW"}]}
  relief: hilly
  notable_features: [Golden Triangle, Point State Park, bluffs, many bridges]
  fun_fact: "France and Britain fought over the Forks of the Ohio. Fort Duquesne became Fort Pitt, and downtown now fills the wedge between the rivers."
  sources: [nps.gov/parkhistory/online_books/founders/sitec37.htm, en.wikipedia.org/wiki/Point_State_Park]

- name: Khartoum
  country: Sudan
  archetypes: [confluence, desert_oasis]
  water_side: []
  rivers: {count: 2, list: [{name: Blue Nile, course: "from E/SE"}, {name: White Nile, course: "from S"}]}
  relief: flat
  notable_features: [al-Mogran confluence, three cities (Khartoum, Omdurman, Khartoum North)]
  fun_fact: "The name is popularly said to mean 'elephant's trunk', after the strip of land between the two Niles, though scholars debate it."
  sources: [en.wikipedia.org/wiki/Khartoum]

- name: Lyon
  country: France
  archetypes: [confluence, river_valley]
  water_side: []
  rivers: {count: 2, list: [{name: Rhône, course: "from NE, fast"}, {name: Saône, course: "from N, meandering"}]}
  relief: hilly
  notable_features: [Presqu'île, Fourvière hill, Croix-Rousse slopes, Musée des Confluences at the tip]
  fun_fact: "Romans founded Lugdunum in 43 BC on Fourvière hill, chosen for its view over both rivers."
  sources: [en.wikipedia.org/wiki/Fourvi%C3%A8re, en.visiterlyon.com]

- name: Belgrade
  country: Serbia
  archetypes: [confluence]
  water_side: []
  rivers: {count: 2, list: [{name: Sava, course: "from W"}, {name: Danube, course: "from NW, turning E"}]}
  relief: rolling
  notable_features: [Kalemegdan fortress ridge, Great War Island, river plains to the north]
  fun_fact: "Beograd means 'white city', traditionally after the pale ridge and fortress above the meeting of the Sava and Danube."
  sources: [en.wikipedia.org/wiki/Belgrade_Fortress]

- name: Chongqing
  country: China
  archetypes: [confluence, mountain_valley]
  water_side: []
  rivers: {count: 2, list: [{name: Jialing, course: "from N, meandering"}, {name: Yangtze, course: "from SW, meandering"}]}
  relief: steep
  notable_features: [Yuzhong peninsula, Chaotianmen confluence, streets on slopes, many bridges]
  fun_fact: "Built on mountains with rivers on three sides, Chongqing earned two nicknames: 'mountain city' and 'city on rivers'."
  sources: [en.wikipedia.org/wiki/Yuzhong_District]

- name: Wuhan
  country: China
  archetypes: [confluence, lakefront]
  water_side: []
  rivers: {count: 2, list: [{name: Yangtze, course: "SW to NE, wide"}, {name: Han, course: "from W"}]}
  relief: flat
  notable_features: [Three Towns, many lakes, "Thoroughfare of Nine Provinces"]
  fun_fact: "Wuhan's name stitches together its three river-split towns: Wuchang + Hankou/Hanyang."
  sources: [newworldencyclopedia.org/entry/Wuhan]

- name: New Orleans
  country: USA
  archetypes: [delta]
  water_side: [S, N]
  rivers: {count: 1, list: [{name: Mississippi, course: "meandering crescent"}]}
  relief: flat
  notable_features: [natural levee, Lake Pontchartrain, much land at or below sea level, pumps and levees]
  fun_fact: "The French Quarter sits on the river's natural levee, the city's original high ground. Newer neighborhoods sit on drained swamp behind it."
  sources: [en.wikipedia.org/wiki/Drainage_in_New_Orleans]

- name: Cairo
  country: Egypt
  archetypes: [river_valley, delta, desert_oasis]
  water_side: []
  rivers: {count: 1, list: [{name: Nile, course: "straight S to N, splitting into delta just north"}]}
  relief: flat
  notable_features: [delta apex, Nile islands, desert plateaus both sides]
  fun_fact: "Since pharaonic Memphis, Egypt's capital has sat where the narrow Nile Valley opens into the delta fan, a natural control point."
  sources: [secondary: rallehabi.kau.edu.sa research PDF on Cairo history]

- name: Dhaka
  country: Bangladesh
  archetypes: [delta]
  water_side: []
  rivers: {count: 6, list: [{name: Buriganga, course: "tidal, S/W edge"}, {name: Turag, course: N}, {name: Balu, course: E}, {name: Shitalakshya, course: E}, {name: Dhaleshwari, course: S}, {name: Tongi Khal, course: N}]}
  relief: flat
  notable_features: [Ganges-Brahmaputra delta, ground 1-14 m above sea level, ringed by rivers]
  fun_fact: "Dhaka is ringed by six interconnected river systems, so floods can arrive from almost every side."
  sources: [core.ac.uk/download/12549139.pdf, en.banglapedia.org/index.php/Buriganga_River]

- name: Rotterdam
  country: Netherlands
  archetypes: [delta, estuary]
  water_side: [W]
  rivers: {count: 1, list: [{name: Nieuwe Maas, course: "straight E-W delta channel"}]}
  relief: flat
  notable_features: [Rhine-Meuse delta, 40 km of port to the sea, polders]
  fun_fact: "Rotterdam's port stretches about 40 km down the delta to the North Sea. It was the world's busiest port from 1962 to 2004."
  sources: [en.wikipedia.org/wiki/Port_of_Rotterdam]

- name: Chicago
  country: USA
  archetypes: [lakefront, inland]
  water_side: [E]
  rivers: {count: 1, list: [{name: Chicago River, course: "short, branching, now flowing away from lake"}]}
  relief: flat
  notable_features: [Lake Michigan shore, portage to Mississippi basin, raised street grade]
  fun_fact: "In 1900 Chicago reversed its river so sewage would flow toward the Mississippi instead of into the lake it drinks from."
  sources: [en.wikipedia.org/wiki/Chicago_River, nps.gov/places/chicago-portage.htm]

- name: Geneva
  country: Switzerland
  archetypes: [lakefront, river_valley]
  water_side: [NE]
  rivers: {count: 2, list: [{name: Rhône, course: "outflow from lake, flowing W"}, {name: Arve, course: "joins from SE"}]}
  relief: rolling
  notable_features: [lake outlet, Old Town hill, Alps and Jura on the horizon]
  fun_fact: "Geneva sits right where the Rhône drains out of Lake Geneva, so the city grew around a lake outlet that doubled as a river crossing."
  sources: [britannica.com/place/Geneva-Switzerland]

- name: Bern
  country: Switzerland
  archetypes: [river_valley]
  water_side: []
  rivers: {count: 1, list: [{name: Aare, course: "meandering, loops around old town"}]}
  relief: rolling
  notable_features: [meander-loop peninsula, arcaded streets, UNESCO old town]
  fun_fact: "Founded in 1191 on a hill wrapped on three sides by the Aare, Bern needed walls only on its fourth side."
  sources: [en.wikipedia.org/wiki/Old_City_(Bern), whc.unesco.org/en/list/267]

- name: Edinburgh
  country: UK (Scotland)
  archetypes: [coastal, inland]
  water_side: [N]
  rivers: {count: 1, list: [{name: Water of Leith, course: "small, winding to the Forth"}]}
  relief: hilly
  notable_features: [Castle Rock volcanic plug, Royal Mile on crag-and-tail, Arthur's Seat (251 m), Firth of Forth]
  fun_fact: "The castle sits on an ancient volcanic plug. A glacier left a ramp of rock behind it, and that ramp became the Royal Mile."
  sources: [edinburghgeolsoc.org/geological-site/castle-rock, en.wikipedia.org/wiki/Castle_Rock_(Edinburgh)]

- name: Quebec City
  country: Canada
  archetypes: [estuary, river_valley]
  water_side: [S, E]
  rivers: {count: 2, list: [{name: St. Lawrence, course: "narrows to ~1 km, then widens to estuary"}, {name: Saint-Charles, course: "joins from W/N"}]}
  relief: hilly
  notable_features: [Cap Diamant (98 m), walled Upper Town, Lower Town at the waterline, Citadelle]
  fun_fact: "'Quebec' probably comes from an Algonquian word for 'where the river narrows'. The St. Lawrence pinches to just over 1 km here."
  sources: [thecanadianencyclopedia.ca]

- name: Montreal
  country: Canada
  archetypes: [island, river_valley]
  water_side: [all]
  rivers: {count: 2, list: [{name: St. Lawrence, course: "SW to NE with Lachine Rapids"}, {name: Rivière des Prairies, course: "north channel"}]}
  relief: rolling
  notable_features: [Mount Royal (233 m), Lachine Rapids, Lachine Canal, river island]
  fun_fact: "The Lachine Rapids stopped ocean ships at Montreal, which made it the place where cargo switched from ships to canoes heading west."
  sources: [canadashistory.ca/explore/historic-sites/the-lives-of-the-lachine-canal]

- name: Minneapolis
  country: USA
  archetypes: [river_valley]
  water_side: []
  rivers: {count: 1, list: [{name: Mississippi, course: "NW to SE, through a gorge below the falls"}]}
  relief: gentle
  notable_features: [St. Anthony Falls, many lakes, river gorge]
  fun_fact: "St. Anthony Falls, the only major waterfall on the upper Mississippi, powered so many mills that Minneapolis was the flour capital of the world for about 50 years."
  sources: [en.wikipedia.org/wiki/Saint_Anthony_Falls, mnagmag.org/lessons/water-power-on-the-mississippi]

- name: Kinshasa
  country: DR Congo
  archetypes: [river_valley, lakefront]
  water_side: [N]
  rivers: {count: 1, list: [{name: Congo, course: "widens into Pool Malebo, then rapids downstream"}]}
  relief: gentle
  notable_features: [Pool Malebo, Livingstone Falls downstream, Brazzaville across the water]
  fun_fact: "Kinshasa and Brazzaville face each other across Pool Malebo, the closest pair of national capitals apart from Rome and Vatican City."
  sources: [en.wikipedia.org/wiki/Pool_Malebo]

- name: La Paz
  country: Bolivia
  archetypes: [canyon, mountain_valley]
  water_side: []
  rivers: {count: 1, list: [{name: Choqueyapu, course: "incised canyon stream (largely channeled)"}]}
  relief: mountainous
  notable_features: [canyon below the Altiplano, El Alto on the rim, cable-car network, ~3,600 m elevation]
  fun_fact: "La Paz is the world's highest de facto capital. The city tumbles down a canyon from El Alto on the Altiplano rim."
  sources: [guinnessworldrecords.com/world-records/65059-highest-capital, britannica.com/place/La-Paz-Bolivia]

- name: Kathmandu
  country: Nepal
  archetypes: [mountain_valley]
  water_side: []
  rivers: {count: 2, list: [{name: Bagmati, course: "meandering, exits via Chobhar gorge"}, {name: Bishnumati, course: "joins Bagmati"}]}
  relief: mountainous
  notable_features: [former lakebed valley floor ~1,400 m, ringed by hills, Chobhar gorge outlet]
  fun_fact: "The Kathmandu Valley was once a lake. Legend says the bodhisattva Manjushri drained it by cutting the gorge at Chobhar, and geology confirms the lake was real."
  sources: [en.wikipedia.org/wiki/Paleo_Kathmandu_Lake]

- name: Medellín
  country: Colombia
  archetypes: [mountain_valley]
  water_side: []
  rivers: {count: 1, list: [{name: Medellín (Porce), course: "straight, flows N along valley axis"}]}
  relief: mountainous
  notable_features: [Aburrá Valley ~1,500 m, Metrocable gondolas, hillside barrios]
  fun_fact: "Medellín's hillside neighborhoods are linked to the valley-floor metro by gondolas. Metrocable Line K opened in 2004."
  sources: [en.wikipedia.org/wiki/Metrocable_(Medell%C3%ADn)]

- name: Mexico City
  country: Mexico
  archetypes: [mountain_valley, lagoon]
  water_side: []
  rivers: {count: 0}
  relief: mountainous
  notable_features: [Valley of Mexico basin ~2,240 m, drained Lake Texcoco, Tenochtitlan island core, subsidence]
  fun_fact: "The Aztec capital Tenochtitlan (1325) stood on an island in Lake Texcoco, linked to shore by causeways. Today the city is sinking into the old lakebed."
  sources: [britannica.com/place/Mexico-City/History]

- name: Damascus
  country: Syria
  archetypes: [desert_oasis]
  water_side: []
  rivers: {count: 1, list: [{name: Barada, course: "short, from Anti-Lebanon, fans into irrigation and vanishes"}]}
  relief: gentle
  notable_features: [Ghouta oasis, Mount Qasioun, rain shadow of Anti-Lebanon]
  fun_fact: "The Barada river waters the Ghouta oasis and then disappears into the desert. Without it, perhaps the world's oldest continuously inhabited city could not exist."
  sources: [britannica.com/place/Damascus, kids.britannica.com/students/article/Damascus/110115]

- name: Las Vegas
  country: USA
  archetypes: [desert_oasis, mountain_valley]
  water_side: []
  rivers: {count: 0}
  relief: gentle
  notable_features: [desert basin ringed by mountains, former artesian springs]
  fun_fact: "'Las Vegas' means 'the meadows'. Artesian springs once made green grass here, a vital stop on the Old Spanish Trail."
  sources: [shpo.nv.gov/nevadas-historical-markers/historical-markers/las-vegas-the-meadows-1]

- name: Johannesburg
  country: South Africa
  archetypes: [inland]
  water_side: []
  rivers: {count: 0}
  relief: rolling
  notable_features: [Witwatersrand ridge, Highveld ~1,750 m, mine dumps]
  fun_fact: "Founded in the 1886 gold rush, Johannesburg is often called the world's largest city not on a river, lake or coastline. Gold, not water, chose its site."
  sources: [en.wikipedia.org/wiki/Witwatersrand_Gold_Rush, uj.ac.za/about/global-engagement/international-students/about-johannesburg]

- name: Lagos
  country: Nigeria
  archetypes: [lagoon, island, coastal]
  water_side: [S, N, E]
  rivers: {count: 0}
  relief: flat
  notable_features: [Lagos Lagoon, Lagos Island, Victoria Island, sand spits, harbour channel]
  fun_fact: "'Lagos' is Portuguese for 'lakes', so 'Lagos Lagoon' basically says 'lakes lagoon'. Locals have long called the city Eko."
  sources: [en.wikipedia.org/wiki/Lagos_Lagoon, en.wikipedia.org/wiki/History_of_Lagos]

- name: Auckland
  country: New Zealand
  archetypes: [isthmus, bay_harbor]
  water_side: [N, S]
  rivers: {count: 0}
  relief: rolling
  notable_features: [Waitematā and Manukau harbours, ~50 volcanic cones, Rangitoto]
  fun_fact: "Auckland's isthmus narrows to about 2 km between two harbours. Māori hauled canoes across it, and at one portage only about 200 m of land separated the waters."
  sources: [teara.govt.nz/en/auckland-region/page-3, en.wikipedia.org/wiki/Auckland_volcanic_field]

- name: Valparaíso
  country: Chile
  archetypes: [bay_harbor, coastal]
  water_side: [N, W]
  rivers: {count: 0}
  relief: steep
  notable_features: [amphitheater of ~42 cerros (hills), funicular ascensores, narrow flat port strip]
  fun_fact: "Valparaíso climbs its hillside amphitheater by funicular. The first ascensor ran in 1883, and the 1914 Panama Canal ended its golden age as the stop before Cape Horn."
  sources: [en.wikipedia.org/wiki/Hills_of_Valpara%C3%ADso, travelhx.com/en/stories/valparaiso-facts]

- name: Constantine
  country: Algeria
  archetypes: [canyon]
  water_side: []
  rivers: {count: 1, list: [{name: Rhumel, course: "deep gorge around three sides of the plateau"}]}
  relief: steep
  notable_features: [rock plateau ~650 m, gorge 150-300 m deep, Sidi M'Cid bridge, "City of Bridges"]
  fun_fact: "Constantine sits on a rock island in the sky, moated by the Rhumel gorge and stitched to the mainland by a string of bridges."
  sources: [britannica.com/place/Constantine-Algeria]

- name: Budapest
  country: Hungary
  archetypes: [river_valley]
  water_side: []
  rivers: {count: 1, list: [{name: Danube, course: "straight N to S, with islands"}]}
  relief: hilly
  notable_features: [hilly Buda west bank, flat Pest east bank, Margaret Island, Castle Hill]
  fun_fact: "Budapest is two landscapes in one city: hilly Buda (up to 527 m) faces pancake-flat Pest across the Danube. They merged in 1873."
  sources: [en.wikipedia.org/wiki/Budapest]
```

---

## 5. Appendix

### 5.1 Quick reference: archetype → archetypal siting factors
| Archetype | Primary siting factors |
|---|---|
| coastal | river mouth, beach landing, coastal plain, barrier islands |
| bay_harbor | natural harbor, ria/drowned valley, headlands |
| river_valley | ford/bridging point, terraces/bluffs, meander loop, head of navigation |
| lakefront | lakeshore, outflow river, portage |
| inland | crossroads, railhead, mineral wealth, plateau, gap |
| island | defensive water, harbor, reclamation |
| peninsula | defensive tip, two-sided harbor, neck |
| delta | natural levee, delta apex, distributary port |
| fjord (cand.) | deep sheltered inlet, head-of-fjord delta |
| mountain_valley (cand.) | valley floor, pass/gap, lakebed fertility |
| archipelago (cand.) | island chain, lake-to-sea link |
| estuary (cand.) | lowest bridging point, tidal port |
| confluence (cand.) | river junction, wedge defense |
| desert_oasis (cand.) | spring, mountain-fed river, caravan route |
| canyon (cand.) | gorge defense, plateau rim |
| lagoon (cand.) | barrier shelter, island core |

### 5.2 Slope thresholds (for engine buildability)
| Slope | Buildability | Source |
|---|---|---|
| 0–10% | unrestricted / generally suitable | Greenville, IL code; Williamsburg, VA plan |
| 10–15% | minimal-disturbance site prep | Greenville, IL |
| 15–25% | allowed with specialized design; some codes cap disturbance | Greenville, IL; Woodland Park, NJ; Carlsbad, CA |
| ≥ 25% | generally unsuitable; many codes bar regrading | Greenville, IL; Woodland Park, NJ |
| > 30% | significant constraints; avoid without waivers | Williamsburg, VA |

### 5.3 Accuracy cautions for product copy
- **Oslofjord and Bay of Kotor:** both are "fjords" in name only. Oslofjord is a tectonic rift and Kotor is a ria. Don't call either a glacial fjord.
- **"Oldest continuously inhabited city":** applies to Damascus, Jericho and others. Always hedge with "perhaps" or "one of".
- **Khartoum = "elephant's trunk":** popular, but disputed.
- **Island counts:** Stockholm (14), Venice (~118), St. Petersburg (33–42), Amsterdam (~90) and Hong Kong (260+) all depend on the counting rule. Use "about".
- **Volcano count in Auckland:** sources give 48 to 53. Use "around 50".
- **Halifax "second-largest natural harbour":** contested. Use "one of the largest ice-free natural harbours".
- **Johannesburg "largest city not on a river/lake/coast":** widely repeated, but the sources are mostly travel and university pages. Keep "often called".
- **New Orleans below sea level:** the figure depends on boundaries. One study gives about 65% of the city proper and another about 50% of the metro. Use "much of".
- **Hamburg's distance from the sea:** 110–145 km depending on the measure. Use "more than 100 km up the Elbe".
- **Singapore reclamation:** about 20–28% depending on the endpoint years. Use "roughly a quarter more land".

