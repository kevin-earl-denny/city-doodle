# 02: Urban Morphology & Growth: Research for "Found Your City"

**Purpose:** source material for (a) Step 2 "How did it grow?" cards, (b) the World Brief LLM's knowledge corpus, and (c) real-world calibration of City Doodle's world settings.
**Compiled:** 2026-11-03. **Confidence flags:** `verified` = checked against a primary or scholarly source during this research. `secondary` = agreed across reputable secondary sources. `estimate` = derived or approximate, verify before showing in product copy.

---

## 0. Conventions used in this document

### 0.1 Slider semantics (as defined in `apps/web/src/api/types.ts`)

| Param | 0 | 1 | Notes for calibration |
|---|---|---|---|
| `grid_organic` | strict grid | fully organic | Anchors: Chicago (most-ordered of 100 world cities, Boeing φ = 0.90) ≈ 0.0; Rome/São Paulo/Charlotte (φ ≈ 0.002–0.005) ≈ 0.9–1.0, but Charlotte is *curvilinear-suburban* organic, not medieval organic (see §3.3). |
| `sprawl_compact` | sprawling suburbs | dense core | Anchors: Houston/Phoenix/Atlanta ≈ 0.1–0.2; Manhattan/Paris/Eixample ≈ 0.95. |
| `historic_modern` | historic preservation | modern redevelopment | Used here to mean *how much the fabric gets rebuilt vs. kept*. A pattern's *birth* can be modern (Haussmann was radical redevelopment) even though the result is now preserved. Values below describe the attitude that produced the pattern. |
| `transit_car` | transit-oriented | car-dependent | Anchors: Tokyo/Manhattan ≈ 0.1; Houston ≈ 0.9. Boeing (2020): households in 1990s-vintage US tracts own ~50% more cars (1.9 vs 1.3 per household) than pre-1940 tracts. |
| `block_size_meters` (50–300) | | | **Measured here as street center-line spacing** (block + one street width) along the *short* side unless stated. Real blocks are often elongated. Both dimensions are given in §2. |
| `district_size_meters` (1000–6000) | | | Side length of a district. Real anchors in §2.4. |

### 0.2 Two kinds of block numbers

1. **Planned/plat dimensions** of an original grid (e.g., Portland 200 ft = 61 m block face). These are the "story" numbers.
2. **Measured network grain**: Boeing (2019) gives the **median street segment length** l̃ (intersection-to-intersection, metres) for 100 whole city networks from OpenStreetMap. This is the best *consistent* cross-city number, but it averages a whole municipality: historic core plus suburbs.

Both are used below. Don't mix them in UI copy without saying which is which.

---

## 1. Street-pattern traditions & eras

Format: one YAML-ish record per tradition. Slider values are recommended defaults for a generator "flavour", not measurements, with a one-line justification. `block` = `block_size_meters`, `district` = `district_size_meters`.

### Quick reference

| # | Tradition | Era | grid_organic | sprawl_compact | transit_car | historic_modern | block | district |
|---|---|---|---|---|---|---|---|---|
| 1 | Organic medieval | c. 900–1500 | 0.95 | 0.95 | 0.05 | 0.05 | 55 | 1000 |
| 2 | Roman castrum | c. 200 BCE–300 CE | 0.05 | 0.85 | 0.1 | 0.1 | 60 | 1000 |
| 3 | Greek Hippodamian | 5th c. BCE onward | 0.1 | 0.85 | 0.05 | 0.1 | 50 | 1000 |
| 4 | Islamic medina | c. 700–1800 | 1.0 | 1.0 | 0.05 | 0.05 | 50 | 1000 |
| 5 | Chinese ward / capital grid | 6th–13th c. (Sui/Tang to Yuan) | 0.05 | 0.6 | 0.1 | 0.2 | 120 | 1000 |
| 6 | Laws of the Indies plaza grid | 1500s–1700s | 0.1 | 0.7 | 0.2 | 0.25 | 120 | 1500 |
| 7 | Dutch canal ring | 1613–1660s | 0.35 | 0.9 | 0.1 | 0.1 | 80 | 1200 |
| 8 | Baroque radial / axial | c. 1585–1800 (DC 1791) | 0.3 | 0.7 | 0.3 | 0.5 | 110 | 2000 |
| 9 | Commissioners' Plan grid | 1811 onward | 0.05 | 0.95 | 0.1 | 0.8 | 80 | 1600 |
| 10 | Jeffersonian / Land Ordinance grid | 1785 onward | 0.1 | 0.15 | 0.85 | 0.7 | 200 | 1600 (mile) |
| 11 | Railroad town | c. 1850–1920 | 0.1 | 0.4 | 0.4 | 0.5 | 100 | 1000 |
| 12 | Haussmann boulevards | 1853–1870 | 0.45 | 0.95 | 0.2 | 0.85 | 100 | 2300 |
| 13 | Cerdà Eixample | 1859 onward | 0.05 | 0.95 | 0.2 | 0.6 | 133 | 1350 |
| 14 | Garden City | 1898 onward | 0.6 | 0.35 | 0.35 | 0.4 | 150 | 1500 |
| 15 | Streetcar suburb | c. 1870–1920 | 0.25 | 0.55 | 0.25 | 0.4 | 110 | 2000 |
| 16 | Radburn / cul-de-sac postwar suburb | 1929; mass 1945–1990s | 0.75 | 0.1 | 0.95 | 0.8 | 280 | 4500 |
| 17 | Modernist superblock | 1930s–1970s | 0.2 | 0.55 | 0.6 | 1.0 | 300 | 2500 |
| 18 | New Urbanism | 1980s onward | 0.3 | 0.65 | 0.45 | 0.5 | 90 | 1200 |
| 19 | Informal / self-built settlement | 20th–21st c. | 0.9 | 0.95 | 0.15 | 0.3 | 50 | 1000 |

---

### 1.1 Organic medieval

```yaml
id: organic_medieval
era: c. 900–1500 CE (fabric often older; Kostof's chapter "'Organic' Patterns")
region: Europe (also widespread elsewhere)
looks_like: >
  Irregular, winding streets of uneven width that converge on a market place,
  cathedral square or castle; triangular "street-market" widenings; narrow deep
  burgage plots fronting the main street; tight perimeter set by a defensive wall;
  later boulevards or ring roads where the wall stood.
why: >
  Incremental, plot-by-plot growth along pre-existing paths, field boundaries and
  contours; the need to fit inside a costly wall; land subdivided by many owners
  over centuries. Space syntax describes the emergent structure as a "deformed
  wheel": a few long, well-connected routes (spokes and rim) around a central
  hub, with quieter back streets in the interstices (Hillier & Hanson 1984).
  Kostof stresses that "organic" towns were often partly planned. The label
  describes the look, not the absence of decision-making.
examples: [Siena, Bologna's centro storico, Prague Old Town, the City of London, Rome's centro]
data:
  - "Rome: orientation-order φ = 0.005, among the 3 most disordered of 100 world cities; median segment 73.7 m (Boeing 2019)"
  - "Venice: median street segment 23.2 m, the finest-grained network in Boeing's 100-city sample"
sliders:
  grid_organic: 0.95       # near-maximal orientation entropy (Rome)
  sprawl_compact: 0.95     # walled, walkable, ~1–2 km across
  transit_car: 0.05        # pre-vehicular; walking city
  historic_modern: 0.05    # the value IS the inherited fabric
  block_size_meters: 55    # European historic cores measure ~50–75 m medians; Venice (23 m) is below slider min
  district_size_meters: 1000 # a whole medieval town is often ≤1.5 km across
```

### 1.2 Roman castrum / colonial grid

```yaml
id: roman_castrum
era: c. 200 BCE–300 CE
region: Roman Empire (Italy, Gaul, Britain, North Africa, Iberia)
looks_like: >
  A rectangular walled grid with two principal streets: the cardo (N–S) and the
  decumanus (E–W) crossing at the forum. Uniform square insulae, four gates.
why: >
  Military camp layout transplanted to colonies for speed of surveying and
  allotment to veterans; standard Roman land survey (centuriation) outside the walls.
examples:
  - "Timgad, Algeria: founded by Trajan c. 100 CE, a 355 m square with ~21 m (70 Roman ft) insulae (UNESCO; Dumbarton Oaks)"
  - "Turin (Augusta Taurinorum): Roman grid still legible in the centre"
  - "Florence, Chester, Cologne, Barcelona's Barri Gòtic (Barcino)"
sliders:
  grid_organic: 0.05       # orthogonal by design; medieval infill later bends it (raise to 0.3 for "aged castrum")
  sprawl_compact: 0.85     # walled and dense
  transit_car: 0.1
  historic_modern: 0.1
  block_size_meters: 60    # insula sizes varied widely; Timgad's ~21 m is unusually small (below slider min)
  district_size_meters: 1000 # entire colony often <1 km square
note: "Insula dimensions varied by colony; only Timgad's are verified here."
```

### 1.3 Greek "Hippodamian" grid

```yaml
id: hippodamian
era: 5th century BCE onward (named for Hippodamus of Miletus; Aristotle credits him with town planning)
region: Greek Aegean, Ionia, Magna Graecia; Hellenistic foundations
looks_like: >
  Long narrow rectangular blocks (insulae) of uniform size laid over sloping sites
  regardless of terrain, with the agora and temples as reserved blocks in the grid.
why: >
  Equal allotment for colonists and rebuilding after destruction (Miletus was
  replanned after the Persian sack of 494 BCE). Kostof and others note orthogonal
  planning predates Hippodamus, so "Hippodamian" is a convention, not an invention date.
examples: [Miletus, Priene (grid imposed on a steep hillside with stepped streets), Piraeus, Olynthus]
data:
  - "Priene residential insulae ~35 × 47 m (secondary; verify)"
  - "Miletus blocks ~30 × 52–60 m (sources vary; estimate)"
sliders:
  grid_organic: 0.1
  sprawl_compact: 0.85
  transit_car: 0.05
  historic_modern: 0.1
  block_size_meters: 50    # small rectangular insulae; slider minimum
  district_size_meters: 1000
generator_hint: "Priene is the canonical 'grid ignores the hill' ancient example: steps instead of switchbacks."
```

### 1.4 Islamic medina

```yaml
id: islamic_medina
era: c. 700–1800 CE (many medinas founded 8th–10th c.; Fez el-Bali founded 789)
region: North Africa, Middle East, Iberia (al-Andalus), Central Asia
looks_like: >
  A strong hierarchy: a few public through-streets linking gates to the great
  mosque and the suq (covered market); semi-public neighbourhood lanes; and
  private dead-end alleys (derbs) serving clusters of inward-facing courtyard
  houses. Very high coverage, few open squares, blank exterior walls.
why: >
  Privacy norms and Islamic jurisprudence on neighbour rights and rights of way;
  private derbs were treated as the joint property of the surrounding families
  (Besim Hakim, "Arabic-Islamic Cities", 1986). Hot climate favours shaded narrow lanes.
examples: [Fez el-Bali (Morocco), Marrakesh, Tunis, Old Damascus, Old Cairo, Aleppo]
sliders:
  grid_organic: 1.0        # no orthogonality; tree-like with many dead ends
  sprawl_compact: 1.0      # courtyard houses at near-total coverage
  transit_car: 0.05        # pedestrian/pack-animal lanes
  historic_modern: 0.05
  block_size_meters: 50    # irregular clusters; the slider minimum is the best fit
  district_size_meters: 1000 # quarters (hara/derb clusters) are small
generator_hint: "Use a high dead-end share (tree branching) and suppress 4-way intersections."
```

### 1.5 Chinese ward / imperial capital grid

```yaml
id: chinese_ward_grid
era: Sui–Tang Chang'an (founded 582 as Daxing) through Yuan Dadu/Beijing (1267–1293)
region: China; exported to Japan (Heijō-kyō/Nara 710, Heian-kyō/Kyoto 794) and Korea
looks_like: >
  A cardinal-oriented walled rectangle, palace at the north centre facing south,
  a monumental central N–S axis, and a chessboard of walled residential wards (fang)
  closed at night, with two walled markets. Later (Song/Yuan) the walls dissolved
  into open streets with parallel E–W alleys (hutongs).
why: >
  Cosmological ideal (Zhou Li / Kaogongji "nine-by-nine" capital), state control
  and curfew, and display of imperial order.
examples:
  - "Tang Chang'an: 108 residential wards + 2 markets; Zhuque Avenue ~150 m wide (Shaanxi govt.; Kyoto Univ.)"
  - "Heian-kyō (Kyoto): square blocks (chō) of 40 jō ≈ 121 m, subdivided into 32 house plots (JAANUS, Columbia)"
  - "Yuan Dadu (Beijing): hutong strips ~67.8 m deep + 9.24 m alleys, so alleys every ~77 m (TU Delft IPHS study)"
data:
  - "Kyoto still ranks among the most-ordered non-North-American cities (φ 0.357; Boeing 2019)"
  - "Beijing median street segment 177.5 m, Shanghai 233 m: the coarsest networks in the 100-city sample, reflecting modern superblocks"
sliders:
  grid_organic: 0.05
  sprawl_compact: 0.6      # vast walled area with gardens and farmland inside the walls
  transit_car: 0.1
  historic_modern: 0.2
  block_size_meters: 120   # Heian-kyō chō; Chang'an wards themselves were ~0.5–1 km (estimate)
  district_size_meters: 1000 # one walled ward ≈ one district
```

### 1.6 Spanish Laws of the Indies plaza grid

```yaml
id: laws_of_the_indies
era: codified 1573 (Philip II's ordinances); practice from 1520s (Mexico City traza, 1522–24)
region: Spanish America and the Philippines; US Southwest (Los Angeles, San Antonio, Santa Fe), Florida
looks_like: >
  A central Plaza Mayor (church, cabildo/town hall, arcades) with streets leaving
  from the plaza corners and centres; a regular checkerboard of square or near-square
  blocks (manzanas/cuadras) subdivided into solares; the grid continues outward
  indefinitely.
why: >
  Royal standardisation of colonial foundation: fast allocation of lots by rank,
  defence, and the plaza as civic and religious centre. Ordinances also addressed
  siting relative to prevailing winds.
spec: "Plaza no smaller than 200 × 300 ft and no larger than 800 × 532 ft; 600 × 400 ft recommended (1.5:1). Transcriptions vary between 530 and 532 ft (secondary)."
examples:
  - "Buenos Aires (Garay, 1580; traza drawn 1583): blocks of 140 varas ≈ 121 m; address numbers advance 100 per block"
  - "Mexico City (traza by Alonso García Bravo, 1522–24, on the Aztec grid of Tenochtitlan)"
  - "Lima (1535), Puebla (1531), Santiago de Chile (1541)"
data:
  - "Buenos Aires today has the highest share of 4-way intersections (0.576) and among the lowest circuity (1.011) of 100 cities (Boeing 2019)"
sliders:
  grid_organic: 0.1        # checkerboard, though multiple grids collide at the edges
  sprawl_compact: 0.7
  transit_car: 0.2
  historic_modern: 0.25
  block_size_meters: 120   # ~100–130 m cuadras are typical
  district_size_meters: 1500
generator_hint: "Always seed one plaza block at the centre; church faces plaza; grid aligned to wind or river rather than strictly N–S."
```

### 1.7 Dutch canal ring (Grachtengordel)

```yaml
id: dutch_canal_ring
era: Amsterdam expansion 1613–c.1660s; UNESCO World Heritage 2010
region: Netherlands (also Dutch colonial towns: Batavia/Jakarta, New Amsterdam's early canals)
looks_like: >
  Concentric half-rings of canals (Herengracht, Keizersgracht, Prinsengracht)
  around the medieval core, with radial cross-streets; long narrow plots of tall
  narrow houses fronting quays; working-class Jordaan with a different, denser grid.
why: >
  Planned extension on reclaimed marsh: canals provide drainage, fill material,
  defence and transport. Land speculation priced by frontage, giving narrow
  deep plots.
examples: [Amsterdam, Delft, Leiden, Utrecht (Oudegracht); compare Venice and Suzhou as "water cities"]
data:
  - "Amsterdam median street segment 65.8 m (Boeing 2019)"
  - "UNESCO core zone 198.2 ha"
sliders:
  grid_organic: 0.35       # geometric, but curved (polygonal arcs), not orthogonal
  sprawl_compact: 0.9
  transit_car: 0.1         # boats, walking; today bikes
  historic_modern: 0.1
  block_size_meters: 80
  district_size_meters: 1200
generator_hint: "Rings follow an offset of the old wall / coastline; cross streets radial; canals ARE the streets."
```

### 1.8 Baroque radial / axial ("Grand Manner")

```yaml
id: baroque_radial
era: c. 1585–1800 (Sixtus V's Rome 1585–90; Versailles; Karlsruhe 1715; St Petersburg; Washington 1791)
region: Europe, then exported (Washington DC, New Delhi 1911–31, Canberra 1912–13)
looks_like: >
  Long straight avenues radiating from rond-points, palaces or monuments (patte
  d'oie "goose-foot" tridents); vistas terminated by obelisks or domes; often
  superimposed on a grid (L'Enfant's diagonals over Ellicott's grid in DC).
why: >
  Display of absolutist or national power, ceremonial movement, military
  manoeuvre, and connecting pilgrimage nodes. Kostof's chapter "The Grand Manner".
examples: [Washington DC (L'Enfant 1791), Karlsruhe (streets fan from the palace), Versailles, Rome (Sixtus V), New Delhi, Canberra]
data:
  - "Washington φ 0.377, median segment 99.5 m (Boeing 2019)"
sliders:
  grid_organic: 0.3        # geometric but multi-directional (diagonals raise orientation entropy)
  sprawl_compact: 0.7
  transit_car: 0.3
  historic_modern: 0.5     # cut through or laid out fresh with authority
  block_size_meters: 110
  district_size_meters: 2000
generator_hint: "Place 2–5 landmark nodes on high ground; connect with straight diagonals; fill with grid; triangular leftover blocks at diagonals."
```

### 1.9 Commissioners' Plan grid (Manhattan, 1811)

```yaml
id: commissioners_grid
era: 1811 plan; built out north through the 19th century
region: Manhattan (model for many US grids)
looks_like: >
  12 numbered N–S avenues and 155 E–W cross streets in an unrelenting
  rectangular grid tilted ~29° to follow the island; blocks 200 ft (61 m) deep N–S
  and 600–920 ft (183–280 m) long E–W; very few parks (Central Park added 1850s).
why: >
  Speculative land market: rectangular lots are cheap to survey, buy, sell and
  build on ("straight-sided and right-angled houses are the most cheap to build"
  is the Commissioners' own argument). Topography was largely ignored and later
  graded.
examples: [Manhattan above Houston Street; Broadway is the pre-grid diagonal survivor]
data:
  - "Cross streets 60 ft; avenues 100 ft; blocks 200 ft N–S; 650 ft (1st–2nd Ave), 610 ft (2nd–3rd), 920 ft (3rd–5th) (MCNY 'The Greatest Grid')"
  - "Original lots ~20–25 × 100 ft; Sevtsuk et al. (2016) model the block as 256 × 60 m with 8 × 30 m plots, 97% of max pedestrian accessibility"
  - "Manhattan φ 0.669; 4-way share 0.572 (highest with Buenos Aires); median segment 82.2 m (Boeing 2019)"
sliders:
  grid_organic: 0.05
  sprawl_compact: 0.95
  transit_car: 0.1
  historic_modern: 0.8     # relentless redevelopment ("the city that tears itself down")
  block_size_meters: 80    # short-side center-line spacing (61 m block + 18 m street ≈ 79 m)
  district_size_meters: 1600
```

### 1.10 Jeffersonian / Land Ordinance grid

```yaml
id: jeffersonian_grid
era: Land Ordinance 1785 (Public Land Survey System); applied westward through 19th–20th c.
region: US Midwest, Plains, West (also Canada's Dominion Land Survey)
looks_like: >
  A continental checkerboard: 6-mile townships of 36 one-mile (640-acre) sections.
  In cities, section lines become arterial roads every mile (1.6 km), with
  half-mile collectors; the land inside each mile square fills with whatever
  pattern its era built (grid pre-1940, loops and cul-de-sacs after).
why: >
  Selling public land quickly and fairly by survey before settlement; farmers'
  roads followed section lines; cities later urbanised the farm grid.
examples: [Phoenix, Los Angeles basin, Detroit (Eight Mile Road), Denver, Oklahoma City, Salt Lake valley]
data:
  - "Phoenix φ 0.586, Las Vegas φ 0.542, but dead-end shares 0.186 and 0.230: ordered arterials around disconnected interiors (Boeing 2019 groups them as 'sprawling but low-entropy')"
sliders:
  grid_organic: 0.1        # arterials strictly cardinal; raise interior organic-ness for post-1945 infill
  sprawl_compact: 0.15
  transit_car: 0.85
  historic_modern: 0.7
  block_size_meters: 200   # interior blocks; the true arterial "superblock" is 1,609 m
  district_size_meters: 1600 # one section = one mile square
```

### 1.11 Railroad town

```yaml
id: railroad_town
era: c. 1850–1920 (peak platting on the Plains 1880–1920)
region: North American Plains and West; Australian and Argentine pampas towns
looks_like: >
  A small orthogonal grid platted by the railroad's townsite company, aligned to
  the tracks, not to the compass. Hudson (1985) identified the "T-town": tracks,
  depot and grain elevators form the bar of the T, and Main Street runs
  perpendicular from the depot. Other plans are symmetric, with the business
  street parallel to the tracks on both sides. Industrial uses line the tracks.
why: >
  Railroads created towns every ~7–10 miles as shipping points and sold the lots;
  identical template plats were reused down the line.
examples: [Plentywood MT (T-town), Cheyenne WY, hundreds of North Dakota towns (Hudson's study area had 500+ townsites platted 1880–1920)]
sliders:
  grid_organic: 0.1
  sprawl_compact: 0.4      # small, low-rise
  transit_car: 0.4         # rail-born, later car-dependent
  historic_modern: 0.5
  block_size_meters: 100   # 300-ish ft blocks typical (estimate)
  district_size_meters: 1000 # the whole town
generator_hint: "Rail line as the town's spine and edge; 'wrong side of the tracks' as a different district."
```

### 1.12 Haussmann's Paris

```yaml
id: haussmann
era: 1853–1870 (Second Empire, Napoleon III & Prefect Haussmann)
region: Paris; imitated in Brussels, Barcelona (Via Laietana), Buenos Aires (Avenida de Mayo), Mexico City (Reforma)
looks_like: >
  Straight tree-lined boulevards slicing diagonally through a dense medieval
  fabric, linking railway stations and monuments at star-shaped places (Étoile);
  uniform 5–7 storey apartment blocks with continuous cornice lines; triangular
  and trapezoidal blocks where boulevards cut the old grain; parks, sewers, aqueducts.
why: >
  Traffic circulation, sanitation (cholera), light and air, state control
  (troop movement), property speculation, and imperial prestige.
data:
  - "Numbers vary widely by source (e.g., 12,000–20,000+ buildings demolished; 80 km of new avenues per Wikipedia). Do not use a single figure as fact."
  - "Paris median segment 71.5 m; dead-end share only 0.050 (Boeing 2019)"
examples: [Paris, Lyon (rue de la République), Marseille (rue de la République)]
sliders:
  grid_organic: 0.45       # organic substrate + straight-line overlay
  sprawl_compact: 0.95
  transit_car: 0.2
  historic_modern: 0.85    # the archetype of top-down redevelopment
  block_size_meters: 100
  district_size_meters: 2300 # Paris's 20 arrondissements average ~5.3 km², ~2.3 km per side
generator_hint: "Generate organic first, then 'cut' straight boulevards between landmarks and remove intersected blocks."
```

### 1.13 Cerdà's Eixample (Barcelona)

```yaml
id: cerda_eixample
era: plan approved 1859–60; Cerdà's "Teoría general de la urbanización" 1867 (coined "urbanización")
region: Barcelona; influence on Latin American and Mediterranean extensions
looks_like: >
  A vast uniform grid of 113.3 m square blocks with 45° chamfered corners
  (xamfrans) making octagonal intersections; 20 m streets; two great diagonals
  (Diagonal, Meridiana) and Gran Via. Cerdà intended blocks built on only two or
  three sides with garden interiors, but most were later closed and densified.
why: >
  Hygiene and equality (Cerdà studied workers' living conditions), traffic
  (chamfers for turning steam trams), and unlimited expansion after the city
  walls were demolished (1854).
data:
  - "Block side 113.3 m; streets 20 m (major avenues 30–50 m+) (Cerdà Plan, CCCB)"
  - "Hierarchy: neighbourhood = 25 blocks; district = 100 blocks; sector = 400 blocks (Italian university course notes; secondary)"
  - "Barcelona whole-city median segment 78.1 m; φ 0.108 (diagonal grid plus old town) (Boeing 2019)"
examples: [Barcelona Eixample; the 2016+ "superilles" (superblocks) group 3×3 Eixample blocks to calm traffic]
sliders:
  grid_organic: 0.05
  sprawl_compact: 0.95
  transit_car: 0.2
  historic_modern: 0.6
  block_size_meters: 133   # 113.3 m block + 20 m street
  district_size_meters: 1350 # Cerdà's 100-block district ≈ 10 × 133 m
generator_hint: "Chamfer every block corner; optional 'superilla' flag merges 3×3 blocks into a calmed cell."
```

### 1.14 Garden City

```yaml
id: garden_city
era: Howard's "To-morrow" 1898 (reissued 1902 as "Garden Cities of To-morrow"); Letchworth 1903; Welwyn 1920
region: UK, then worldwide (Radburn, Canberra, Hellerau, Den-en-chōfu in Tokyo)
looks_like: >
  A town of limited size ringed by a permanent agricultural greenbelt; concentric
  rings with a central garden and civic buildings; six radial boulevards; curving
  tree-lined streets with low-density cottages; separate industrial zone by the railway.
why: >
  Escape from the overcrowded Victorian city while keeping town jobs and culture
  ("town-country magnet"); community land ownership to capture rising land values.
spec: >
  Howard: 32,000 people; the town covers 1,000 acres at the centre of a
  6,000-acre estate (the rest agricultural); six boulevards 120 ft wide; clusters
  of garden cities around a 58,000-person central city (Howard's text via
  sacred-texts.com; Wikipedia gives 9,000 acres in one place, so cite the book).
examples: [Letchworth Garden City, Welwyn Garden City, Hampstead Garden Suburb, Radburn NJ]
sliders:
  grid_organic: 0.6        # curving picturesque streets on a radial-concentric frame
  sprawl_compact: 0.35     # ~12 houses/acre ideal; low-rise
  transit_car: 0.35        # rail-linked, pre-car
  historic_modern: 0.4
  block_size_meters: 150
  district_size_meters: 1500 # whole town ≈ 2.5 km across (1,000 acres ≈ 4 km²)
generator_hint: "Hard green ring at a fixed radius; growth jumps to a NEW satellite rather than sprawling outward."
```

### 1.15 Streetcar suburb

```yaml
id: streetcar_suburb
era: horsecar c. 1850s; electric streetcar after Sprague's Richmond system (1888); peak c. 1890–1920
region: North America, Australia (Melbourne's tram suburbs), Europe
looks_like: >
  Linear "fingers" of development along radial streetcar lines: shops and
  apartments at stops and along the car line, with a grid of modest single-family
  and two/three-family houses on narrow lots within a ~5–10 minute walk.
  Undeveloped wedges remain between lines until the car era.
why: >
  Warner's "Streetcar Suburbs" (1962): Boston's ~2-mile-radius walking city of 1850
  exploded outward once cheap fares made 5–6 mile commutes possible. Private
  traction companies were often also land developers.
examples: [Dorchester, Roxbury and Brookline (Boston), Shaker Heights (Cleveland), Rockridge (Oakland), Toronto's Beaches, Melbourne's inner tram suburbs]
sliders:
  grid_organic: 0.25       # gridded infill with curvilinear premium subdivisions
  sprawl_compact: 0.55
  transit_car: 0.25
  historic_modern: 0.4
  block_size_meters: 110
  district_size_meters: 2000
generator_hint: "Grow along radial lines first (density peaks at stops), fill wedges later with lower-density, more car-oriented patterns."
```

### 1.16 Radburn idea & the cul-de-sac postwar suburb

```yaml
id: culdesac_suburb
era: Radburn NJ 1929 (Stein & Wright); FHA land-planning guidance 1930s; mass production 1945–1990s (Levittown 1947)
region: US, Canada, Australia, UK new towns
looks_like: >
  Superblocks bounded by arterials, entered by curving collectors feeding loops
  and cul-de-sacs ("loops and lollipops", "lollipops on a stick"). Few 4-way
  intersections, many dead ends, single-use residential pods, strip retail and
  malls on arterials. Radburn itself put houses' living rooms toward interior
  parks with underpasses separating pedestrians from cars. Most later imitators
  kept the cul-de-sac and dropped the park.
why: >
  Traffic safety and quiet, the automobile, FHA mortgage-insurance standards,
  ITE's 1965 "Recommended Practices for Subdivision Streets" (avoid 4-way
  intersections; use loops and cul-de-sacs), and cheap peripheral land.
eras: "Southworth & Ben-Joseph (1997): interconnected grids (c.1900s) → fragmented grids (1930s) → warped parallels (1940s–60s) → loops & lollipops (1960s–70s) → lollipops on a stick (1980s–90s) → neotraditional (2000s)"
data:
  - "Radburn: 149 acres incl. 23 acres of interior parks; hammerhead cul-de-sacs ~400 ft"
  - "Boeing (2020, JAPA): vs. pre-1940 US urban tracts, 1990s tracts have 163% more dead-ends, half the intersection density, and 20% (~25 m) longer street segments; the trend reversed after 2000"
  - "Charlotte: most orientation-disordered city of 100 (φ 0.002), segments ~50% longer than the average European city"
examples: [Radburn NJ, Levittown NY, Irvine CA, suburban Charlotte, Atlanta and Houston]
sliders:
  grid_organic: 0.75       # curvilinear and dendritic (but planned, not medieval)
  sprawl_compact: 0.1
  transit_car: 0.95
  historic_modern: 0.8
  block_size_meters: 280   # superblocks between collectors; slider near max
  district_size_meters: 4500 # Houston's 88 super neighbourhoods average ~19 km² (~4.3 km per side)
```

### 1.17 Modernist superblock ("towers in the park")

```yaml
id: modernist_superblock
era: Le Corbusier's Ville Radieuse 1930s; CIAM Athens Charter 1933; built 1945–1975
region: worldwide: Brasília, Chandigarh, Soviet mikrorayons, US public housing, Hong Kong/Singapore new towns
looks_like: >
  Very large blocks bounded by fast roads; free-standing slab or tower blocks set
  in open green space, often on pilotis; strict separation of functions (dwelling,
  work, recreation, circulation); hierarchical road network, few street frontages.
why: >
  Light, air and green for all; rational mass housing; car-era traffic separation;
  clearance of "slums"; state-led construction.
data:
  - "Brasília superquadra: 280 × 280 m; ~11 residential slabs on pilotis, max 6 storeys (Lúcio Costa's 1957 plan; Docomomo Brasil)"
  - "Chandigarh sector: 800 × 1200 m (Le Corbusier, 1951+)"
  - "Moscow median segment 130.5 m, Kiev 125.1 m, Pyongyang 132.4 m; Boeing clusters Berlin, Moscow, Kiev, Warsaw, Prague, Pyongyang as a distinct 'socialist' cluster"
examples: [Brasília, Chandigarh, Moscow mikrorayons, Stuyvesant Town (NYC), Toulouse-Le Mirail]
sliders:
  grid_organic: 0.2        # usually geometric
  sprawl_compact: 0.55     # high-rise but low coverage: dense people, sparse fabric
  transit_car: 0.6         # car-scaled roads, though Soviet versions relied on transit
  historic_modern: 1.0     # tabula rasa
  block_size_meters: 300   # slider max (Brasília 280 m; Chandigarh 800+ m exceeds the range)
  district_size_meters: 2500
```

### 1.18 New Urbanism / Traditional Neighbourhood Development

```yaml
id: new_urbanism
era: Seaside FL 1980s (Duany Plater-Zyberk); Kentlands 1988; Congress for the New Urbanism founded 1993; Charter 1996
region: US, UK (Poundbury 1993+), worldwide
looks_like: >
  Interconnected modified grid of short blocks; a mixed-use town centre within a
  ~5-minute (~400 m) "pedestrian shed"; varied house types including rowhouses
  and accessory units; alleys, front porches, terminated vistas; form-based codes.
why: >
  Reaction against postwar sprawl; revival of pre-1940 patterns (Perry's
  neighbourhood unit, Unwin, streetcar suburbs).
data:
  - "Boeing (2020): US tracts built in the 2000s are 13% more gridded than 1990s tracts, with 23% more 4-way intersections and 14% fewer dead ends"
  - "Perry's 1929 neighbourhood unit: quarter-mile radius, ~160 acres, sized to support one elementary school (~5,000 people) (APA PAS report 141)"
examples: [Seaside FL, Kentlands MD, Celebration FL, Poundbury UK, Mueller (Austin)]
sliders:
  grid_organic: 0.3
  sprawl_compact: 0.65
  transit_car: 0.45        # walkable centre, but residents still drive regionally
  historic_modern: 0.5     # new build in traditional dress
  block_size_meters: 90
  district_size_meters: 1200 # ~two pedestrian sheds
```

### 1.19 Informal / self-built settlement

```yaml
id: informal_settlement
era: mostly 20th–21st c. (rapid urbanisation); UN-Habitat estimates >1.1 billion people live in slums or informal settlements (World Cities Report 2026)
region: Global South: Latin America (favelas, villas, barrios), South Asia, Sub-Saharan Africa, Middle East
looks_like: >
  Very fine-grained incremental fabric: narrow footpaths and stairs, irregular
  plots, high coverage, buildings that grow vertically over time; on steep slopes,
  floodplains, rail and canal edges, or peripheral land. Some are surprisingly
  orthogonal where land was informally subdivided by a developer (e.g., Latin
  American "loteamentos"/"invasiones" with grid layouts).
why: >
  Housing demand outpacing formal supply; residents self-build on land formal
  markets can't use (steep, flood-prone) or where tenure is contested.
  Upgrading over decades often consolidates them into permanent districts.
examples: [Rocinha (Rio), Dharavi (Mumbai), Kibera (Nairobi), Orangi (Karachi), Comuna 13 (Medellín)]
data:
  - "Port-au-Prince median segment 55.0 m, dead-end share 0.295 (Boeing 2019)"
sliders:
  grid_organic: 0.9        # can drop to ~0.3 for informal grid subdivisions
  sprawl_compact: 0.95
  transit_car: 0.15        # walking, minibuses, motorbike taxis
  historic_modern: 0.3     # constantly rebuilt but by accretion, not clearance
  block_size_meters: 50
  district_size_meters: 1000
ux_note: "Name respectfully in UI ('Self-Built City', 'Hillside Barrio'), never 'slum'."
```

---

## 2. Real block dimensions

### 2.1 Planned/plat block dimensions (original grids)

Center-line = block + one street width. Converted at 1 ft = 0.3048 m, 1 chain = 66 ft = 20.12 m, 1 vara (Buenos Aires) ≈ 0.866 m.

| City (plan, year) | Block (face) | Center-line spacing | Street widths | Source / confidence |
|---|---|---|---|---|
| **Portland, OR** (1845) | 200 × 200 ft = **61 × 61 m** | ~79–85 m | 60 ft (18 m); some 80 ft | Sevtsuk et al. 2016 (60 × 60 m); Siksna 1997 (85 m mesh). `verified` |
| **Manhattan** (1811) | **200 ft (61 m) × 600–920 ft (183–280 m)** | ~79 m N–S × 200–300 m E–W | streets 60 ft, avenues 100 ft | MCNY "Greatest Grid"; Sevtsuk 2016 models 256 × 60 m. `verified` |
| **Barcelona Eixample** (1859) | **113.3 × 113.3 m**, chamfered | **133.3 m** | 20 m (avenues 30–50 m+) | Cerdà Plan; CCCB. `verified` |
| **Salt Lake City** (1847) | 660 × 660 ft = **201 × 201 m** (10 acres) | ~241 m | 132 ft (40 m) | AIA Utah Reflexion; NPS NRHP. `verified` |
| **Melbourne Hoddle Grid** (1837) | 10 chains = **201 × 201 m**, split by "Little" lanes | 231 × 116 m (Siksna) | 99 ft (30 m); little streets 33 ft (10 m) | Wikipedia Hoddle Grid; Siksna 1997. `verified` |
| **Adelaide** (1837) | **~520–554 × 130–155 m** (very coarse) | 554 × 155 m | wide | Sevtsuk 2016; Siksna 1997. `verified` |
| **Brisbane** | ~200 × 90 m | 221 × 111 m | 20 m | Sevtsuk 2016; Siksna 1997. `verified` |
| **Chicago** (1830 plat) | original ~96 × 115 m; city grid later 330 × 660 ft (**100 × 200 m**), 8 blocks/mile E–W, 16/mile N–S | 122 × 140 m (Siksna, original) | 25 m | Sevtsuk 2016; Siksna 1997. `verified` (city grid: `secondary`) |
| **Indianapolis** (1821) | ~126 × 128 m | 158 × 158 m | 30 m | Sevtsuk 2016; Siksna 1997. `verified` |
| **Seattle** | ~ 75–110 m | 93–130 × 98 m | | Siksna 1997. `verified` |
| **Toronto** | | 201 × 140 m | | Siksna 1997. `verified` |
| **Perth** | >300 m long | 332 × 141 m | | Siksna 1997. `verified` |
| **Savannah** (Oglethorpe, 1733) | ward ≈ 10 acres; tything lots 60 × 90 ft; squares ~315 × 270 ft (original six) | 110 × 79 m (Siksna) | 45–120 ft; lanes 22.5 ft | Wikipedia Oglethorpe Plan; Siksna 1997; Georgia Encyclopedia. `verified` (ward dims vary) |
| **Houston** (Allen brothers, 1836) | **250 × 250 ft = 76 × 76 m**, 12 lots each; grid angled to Buffalo Bayou | ~95 m (est.) | ~80 ft (est.) | Downtown Houston / founding histories. `secondary` |
| **Phoenix** (Hancock, 1870) | **~300 × 300 ft = 91 × 91 m**, 12 lots + E–W alley | ~110–115 m (est.) | 60–80 ft (sources conflict); 100 ft main streets | Phoenix city history; Arizona Highways. `secondary` |
| **Philadelphia** (Holme, 1682–83) | large blocks up to ~400 × 500 ft (**~120 × 150 m**), later cut by alleys | | Broad & High (Market) 100 ft; riverfront 60 ft; others 50 ft | MCNY lesson plan; ASCE landmark page. `secondary` |
| **Kyoto / Heian-kyō** (794) | 40 jō ≈ **121 × 121 m** (chō), 32 house plots | | major avenues very wide | JAANUS (Columbia). `verified` |
| **Beijing / Yuan Dadu** (1267) | hutong strips 67.8 m deep | alleys every ~77 m | hutong 9.24 m | TU Delft IPHS paper. `secondary` |
| **Buenos Aires** (Garay 1580/1583) | 140 varas ≈ **121 m** | ~121–130 m | narrow (~10 m historic) | Garay traza studies; GCBA. `secondary` (some cite 150 varas = 129.9 m) |
| **Timgad** (c. 100 CE) | ~70 × 70 Roman ft ≈ **21 × 21 m** | ~25–30 m (est.) | | Dumbarton Oaks; UNESCO. `secondary` |
| **Brasília** superquadra (1957) | **280 × 280 m** | | | Docomomo Brasil. `secondary` |
| **Chandigarh** sector (1951) | **800 × 1200 m** | | | multiple. `secondary` |
| **Edinburgh New Town** (Craig, 1767) | long blocks (~200–250 m) between Princes/George/Queen St, halved by mews lanes (Rose St, Thistle St) into ~70–90 m deep strips | | George St ~115 ft | Wikipedia; aboutscotland. Block dims are `estimate` |
| **Mexico City traza** (1522–24) | elongated E–W rectangular blocks of ~10 square solares | | | Historia Mexicana / García Bravo studies. Dimensions `not verified` |
| **Paris / Tokyo** | no single "plat" block; irregular | see §2.2 measured grain | | |

### 2.2 Measured network grain (Boeing 2019, Applied Network Science 4:67, Table 1)

φ = orientation order (0 = uniform in all directions, 1 = one perfect grid). l̃ = median street segment length (m). ς = circuity. Pde = dead-end share. P4w = 4-way-intersection share. **Whole-municipality** networks (Manhattan = borough only).

| City | φ | l̃ (m) | ς | Pde | P4w | Reading |
|---|---|---|---|---|---|---|
| Chicago | **0.899** | 105.3 | 1.016 | 0.074 | 0.507 | most ordered of 100 |
| Miami | 0.811 | 96.7 | 1.023 | 0.069 | 0.407 | |
| Minneapolis | 0.749 | 115.4 | 1.023 | 0.053 | 0.521 | |
| Vancouver | 0.749 | 103.7 | 1.022 | 0.073 | 0.455 | |
| Seattle | 0.723 | 97.2 | 1.028 | 0.136 | 0.369 | |
| Portland | 0.679 | 82.1 | 1.041 | 0.146 | 0.327 | |
| Manhattan | 0.669 | 82.2 | 1.017 | 0.027 | **0.572** | |
| Phoenix | 0.586 | 97.1 | 1.073 | 0.186 | 0.171 | ordered arterials, disconnected interiors |
| Las Vegas | 0.542 | 86.1 | 1.079 | 0.230 | 0.166 | |
| Houston | 0.425 | 96.2 | 1.045 | 0.127 | 0.307 | |
| Washington | 0.377 | 99.5 | 1.038 | 0.065 | 0.370 | grid + diagonals |
| Kyoto | 0.357 | 49.6 | 1.090 | 0.134 | 0.157 | most-ordered outside N. America (with Mogadishu, Melbourne) |
| Melbourne | 0.340 | 51.9 | 1.037 | 0.060 | 0.332 | |
| Philadelphia | 0.312 | 83.9 | 1.030 | 0.047 | 0.398 | |
| San Francisco | 0.278 | 94.4 | 1.033 | 0.087 | 0.454 | colliding grids, hills |
| Mexico City | 0.154 | 69.9 | 1.043 | 0.146 | 0.264 | |
| Buenos Aires | 0.151 | 104.8 | **1.011** | **0.027** | **0.576** | many grids at angles, so low φ but very grid-like |
| Barcelona | 0.108 | 78.1 | 1.052 | 0.078 | 0.303 | |
| Amsterdam | 0.071 | 65.8 | 1.080 | 0.146 | 0.205 | |
| Tokyo | 0.050 | **49.6** | 1.046 | 0.119 | 0.186 | fine-grained, multi-directional |
| Boston | 0.026 | 77.0 | 1.039 | 0.135 | 0.211 | |
| Paris | 0.016 | 71.5 | 1.023 | 0.050 | 0.240 | |
| London | 0.015 | 70.3 | 1.061 | 0.251 | 0.070 | |
| Rome | 0.005 | 73.7 | 1.070 | 0.161 | 0.145 | |
| Charlotte | **0.002** | 117.2 | 1.067 | 0.288 | 0.139 | most disordered: curvilinear sprawl |
| Venice | 0.017 | **23.2** | 1.090 | 0.300 | 0.073 | finest-grained |
| Moscow | 0.007 | 130.5 | 1.055 | 0.074 | 0.170 | coarse (mikrorayons) |
| Beijing | 0.335 | 177.5 | 1.053 | 0.135 | 0.241 | very coarse |
| Shanghai | 0.121 | **233.0** | 1.040 | 0.156 | 0.317 | coarsest |

Key findings (Boeing 2019):
- All 16 lowest-entropy cities are in the US/Canada. US/Canadian cities have, on average, a φ nearly **13×** that of European cities and nearly double the share of 4-way intersections. European streets are **42% more circuitous**.
- Shortest median segments: Venice, Mogadishu, Helsinki, Jerusalem, Casablanca. Longest: Kiev, Moscow, Pyongyang, Beijing, Shanghai.
- Chicago, the model city of the Chicago School's concentric-zone theory, is an *extreme outlier* in order.

### 2.3 What block size "should" be (normative studies)

- **Siksna (1997, Urban Morphology 1:19–33):** across 12 US/Australian CBDs, small square blocks of about **60–80 m** performed best. Circulation meshes at **80–110 m** spacing are optimal for combined pedestrian and vehicle needs; **50–70 m** in intensive pedestrian areas. Large blocks get retrofitted: Adelaide's 554 × 154 m mesh has been reduced to 60 × 70 m in its retail core via inserted lanes and arcades, and Melbourne's 200 m blocks to 46–80 m mesh via laneways. Portland/Seattle-size blocks (3,600–6,400 m²) suit most large buildings.
- **Sevtsuk, Kalvo & Ekmekci (2016, Urban Morphology 20(2):89–106):** pedestrian accessibility is **non-linear** in block length, so smaller is *not* always better. Manhattan and Indianapolis achieve ~97% of the theoretical optimum given their plots and streets. Portland would gain ~8.6% with *longer* blocks. Adelaide would gain 12% with shorter ones.
- **Jane Jacobs (1961, p.150):** "most blocks must be short; that is, streets and opportunities to turn corners must be frequent" (she criticised Manhattan's long E–W blocks).
- **Allan Jacobs (1993, Great Streets, p.302):** streets with an entry every ~300 ft (90 m) are easy to find.

### 2.4 District-size anchors (for `district_size_meters`)

| Unit | Approx. side length | Basis |
|---|---|---|
| Perry neighbourhood unit (1929) | ~800 m (¼-mile radius; 160 acres) | APA PAS 141 |
| New Urbanist pedestrian shed | ~800 m (5-min / 400 m radius) | CNU practice |
| Cerdà district (100 blocks) | ~1.33 km | §1.13 |
| Chandigarh sector | 0.8 × 1.2 km | §1.17 |
| Jeffersonian section (arterial grid) | 1.61 km | Land Ordinance 1785 |
| Manhattan community district (12 in ~59 km²) | ~2.2 km | `estimate` |
| Paris arrondissement (20 in 105 km²) | ~2.3 km | `estimate` |
| Chicago community area (77 in ~606 km²) | ~2.8 km | `estimate` |
| Barcelona district (10 in ~101 km²) | ~3.2 km | `estimate` |
| Houston super neighbourhood (88 in ~1,650 km²) | ~4.3 km | `estimate` |
| Walking city radius (Boston 1850, per Warner) | ~2 mi (3.2 km) radius | Warner 1962 |

### 2.5 Implications for City Doodle's current presets (observations, not changes)

- **"Portland" preset uses `block_size_meters: 100`**, but Portland's famous blocks are **61 m** (≈79–85 m center-line). If the preset is meant to evoke Portland's signature small blocks, **~65–80** is more faithful.
- **"Houston" preset uses 200 m blocks.** Houston's downtown blocks are actually small (**76 m**, 250 ft). Houston's sprawl comes from coarse suburban superblocks and arterials (whole-city l̃ 96 m, dead-end share 0.127), low density and car dependence, not from big downtown blocks. 200 m is defensible as a *suburban* value. Description copy shouldn't claim Houston has large blocks downtown.
- **"Manhattan" 80 m** matches the short-side center-line (61 m + 18 m street). Long side is ~200–300 m. If the generator only supports square blocks, consider an aspect-ratio parameter later (Manhattan ≈ 1:3.5, Adelaide ≈ 1:3.6, Eixample 1:1).
- **"European" 70 m** fits measured European medians (Paris 71.5, London 70.3, Rome 73.7).
- **Slider range 50–300**: Venice (23 m) and Timgad (21 m) fall below. Brasília (280) fits; Chandigarh (800+), Adelaide's long side (554) and Shanghai-style superblocks exceed it. That's fine for gameplay, but LLM output must clamp.

---

## 3. How terrain shapes street pattern & growth

### 3.1 Grids vs. terrain

```yaml
principle: grids_bend_to_water
summary: >
  Planned grids are usually aligned to the dominant waterfront or valley axis,
  not to the compass. Multiple grids meet at angles where shorelines or rivers
  bend, producing "seams" of triangular blocks.
examples:
  - "Manhattan's grid runs ~29° off true north to follow the island (Boeing 2019)"
  - "Houston's 1836 grid is angled to Buffalo Bayou (E–W streets at N 55° W)"
  - "New Orleans: streets fan around the river crescent, following French long-lot (arpent) property lines that ran perpendicular to the Mississippi"
  - "Melbourne's Hoddle Grid is aligned to the Yarra, not N–S"
  - "Pittsburgh (φ 0.018): multiple small grids at the river confluence plus hills, among the least-ordered US cities"
  - "Buenos Aires: many cardinal-ish grids at slightly different angles, so φ is only 0.15 though the city is almost entirely gridded"
counter_examples:
  - "Cosmologically oriented capitals (Chang'an, Heian-kyō, Beijing) and the Land Ordinance grid hold strict cardinal orientation regardless of terrain"
generator_rule: "Align each district's grid to the nearest major coastline/river tangent; allow 2–4 grid orientations per city; insert diagonal 'seam' streets."
```

```yaml
principle: hills_contours_vs_defiance
summary: >
  On hills, cities either (a) follow contours with winding streets, switchbacks,
  stairs and funiculars, or (b) impose the grid and accept steep grades.
examples_follow:
  - "Genoa: dense layered city on a narrow coastal strip, with stepped lanes (crêuze/caruggi) and lifts"
  - "Lisbon (Alfama), Valparaíso (funiculars), Naples, hill towns of Tuscany and Umbria; Edinburgh New Town ran its main axis (George St) along a ridge"
  - "Priene shows the opposite: a Greek grid laid straight over a steep slope with stepped streets"
examples_ignore:
  - "San Francisco: O'Farrell's 1847 survey extended a rectilinear grid over the hills with little deference to terrain. Accounts say landowners blocked contour-following alignments, and 'planners thought SF was flat' is folklore. Some blocks are so steep they are stairs (Filbert Street steps)"
  - "Seattle regraded its hills (Denny Regrade, 1898–1930) to keep its grid working"
generator_rule: >
  Use slope thresholds: below ~5–8% grade keep the grid; ~8–15% bend streets
  toward contours or switch to stairs for pedestrian-only links; above ~15–20%
  leave it unbuilt (parks, greenbelts, informal housing, or elite villas).
  These thresholds are design rules of thumb, not sourced constants; tune in-game.
note: "Boeing (2020) found the average elevation range (IQR) of US urban tracts rose 57% from 1940s to 1990s vintage: later suburbs climbed into the hills, which also bends their streets."
```

```yaml
principle: high_ground_and_social_geography
summary: >
  Hoyt (1939) observed that high-rent sectors grow toward high ground, along
  waterfronts not used by industry, and along fast transport routes. Industry
  follows flat land, rail and water. In many Latin American cities the pattern
  inverts: informal settlements occupy steep hillsides (Rio's favelas) while
  elites hold the flat coastal strip.
generator_rule: "Bias wealthy/low-density districts to views and high ground; industry to flat land beside rail and harbour; flag steep central slopes as candidates for self-built districts."
```

### 3.2 Waterfront lifecycle, landfill, bridges

```yaml
principle: waterfront_lifecycle
summary: >
  Port-city waterfronts move through stages: (1) the original port at the city
  core; (2) expanding wharves and warehouses; (3) industrial port with rail
  yards; (4) container era: the port moves to deep water and the old waterfront
  is abandoned; (5) redevelopment into parks, housing and culture
  (Hoyle 1989, "The port–city interface", Geoforum 20(4)).
examples:
  - "Baltimore Inner Harbor (1970s–80s), London Docklands/Canary Wharf (1980s+), Barcelona's 1992 Olympic waterfront, Hudson River Park NYC, HafenCity Hamburg"
  - "Seoul's Cheonggyecheon (2005): an elevated highway removed to restore a stream"
generator_rule: "Era slider: early = working harbour/industrial; late or historic_modern high = parks, promenades, towers on old piers."
```

```yaml
principle: landfill_and_reclamation
summary: Cities manufacture flat land at their edges, which almost always becomes a new GRID.
examples:
  - "Boston Back Bay: tidal flats filled from 1857 to ~1882 (with gravel brought by rail from Needham), laid out as a formal grid of boulevards (Commonwealth Ave) that contrasts with the old peninsula's winding streets"
  - "Manhattan's shoreline extended repeatedly; Battery Park City built on fill from 1970s excavations"
  - "Amsterdam's canal ring, Mexico City on drained Lake Texcoco, Tokyo Bay, Hong Kong, Singapore, Mumbai (seven islands joined)"
generator_rule: "Reclaimed areas = flat, regular, newer blocks with crisp straight shoreline edges."
```

```yaml
principle: bridges_and_crossings_as_growth_vectors
summary: >
  A new bridge or tunnel unlocks the far shore, and growth jumps across. Cities
  originate at fords and lowest bridging points; later bridges create new
  "bridgehead" centres.
examples:
  - "Brooklyn Bridge (1883) preceded the consolidation of Greater New York (1898)"
  - "Sydney Harbour Bridge (1932) opened the North Shore; Golden Gate (1937) and Bay Bridge (1936) did the same for Marin and the East Bay"
  - "London grew at the lowest bridgeable point on the Thames"
generator_rule: "Seed the original core at the narrowest river crossing; each later bridge spawns a secondary node on the opposite bank."
```

### 3.3 Rings, corridors and growth models

```yaml
principle: walls_to_rings
summary: >
  When walls are demolished, their line becomes a ring boulevard, and the old
  glacis or moat a belt of parks and institutions. Conzen (1960, Alnwick) calls
  this the "fringe belt": a belt of large-plot uses (parks, cemeteries,
  hospitals, barracks, rail yards) left wherever growth pauses at an edge.
examples:
  - "Vienna Ringstrasse (walls demolished after Franz Joseph's decree of December 1857; boulevard opened 1865)"
  - "Barcelona: walls demolished 1854, making room for the Eixample"
  - "Paris Boulevard Périphérique (completed 1973) along the line of the 1840s Thiers fortifications; Beijing's 2nd Ring Road on the line of the Ming city wall; Moscow's Garden Ring on an earthen rampart"
  - "Modern beltways (e.g., Washington's Capital Beltway, 1964) become magnets for edge cities"
generator_rule: "Every growth pause leaves a ring: when the core outgrows its wall radius, convert the wall to a boulevard and place parks or institutions in the belt."
```

```yaml
principle: transit_corridors_fingers
summary: >
  Fixed rail produces star-shaped (radial finger) growth with density at stations;
  the car fills the wedges between fingers.
examples:
  - "Boston (Warner 1962): walking city ~2 mi radius in 1850; horsecars, then electric streetcars (from 1888), stretched commutes to ~4–6 mi"
  - "Copenhagen Finger Plan (1947): urban growth channelled along five S-train rail fingers with green wedges between them; still the backbone of regional planning"
  - "Los Angeles: Pacific Electric 'Red Car' lines seeded many suburbs before the freeway era"
  - "Marchetti's constant (Marchetti 1994): people budget ~1 hour/day of travel. Faster transport expands the city's radius rather than shortening trips, so a walking city is ~2–3 km across and a streetcar city ~10 km"
generator_rule: "transit_car low → grow along radial lines with station nodes; transit_car high → isotropic sprawl filling wedges, plus beltway nodes."
```

```yaml
model: burgess_concentric_zone
source: "Burgess, 'The Growth of the City', in Park, Burgess & McKenzie, The City (1925), based on Chicago"
zones: [1 Central Business District (Loop), 2 Zone in transition (factories, slums, immigrants), 3 Working-class homes, 4 Residential zone (middle class), 5 Commuter zone]
mechanism: "Invasion and succession: each zone expands into the next as the city grows."
caveat: "Fits flat, monocentric, grid cities with no terrain. Chicago is itself an outlier (most ordered of 100 cities)."
generator_use: "Default radial density decay from a single core when terrain is flat and sprawl_compact is mid."
```

```yaml
model: hoyt_sector
source: "Hoyt, The Structure and Growth of Residential Neighborhoods in American Cities (FHA, 1939)"
idea: >
  Land uses form wedges radiating along transport routes. Once a high-rent sector
  starts, it keeps growing outward in the same direction (toward high ground,
  amenity waterfronts, and the homes of leaders). Industry forms sectors along
  rail and rivers.
generator_use: "Pick 1–2 'prestige' directions (toward hills or amenity coast) and 1 'industrial' direction (toward port/rail); extend land uses as wedges."
```

```yaml
model: harris_ullman_multiple_nuclei
source: "Harris & Ullman, 'The Nature of Cities', Annals of the American Academy of Political and Social Science 242 (1945)"
idea: >
  Cities grow around several discrete nuclei (CBD, wholesale and light industry,
  heavy industry, outlying business districts, suburbs and satellites) because
  activities need specialised sites, cluster for mutual benefit, repel
  incompatible uses, and some can't afford central rents. The car-era extension
  is Garreau's "Edge City" (1991).
generator_use: "Car-dependent or large cities: seed secondary centres at highway or bridge junctions, airports, ports, old village cores swallowed by growth."
```

```yaml
model: conzen_town_plan_analysis
source: "M.R.G. Conzen, Alnwick, Northumberland: A Study in Town-Plan Analysis (1960)"
ideas:
  - "Plan elements: streets, plots, buildings. Streets persist longest, plots next, buildings change fastest (this justifies historic_modern acting mainly on buildings, not streets)"
  - "Burgage cycle: long narrow plots fill up with back-buildings until cleared and redeveloped"
  - "Fringe belts mark former edges of growth (see walls_to_rings)"
```

```yaml
lens: lynch_image_of_the_city
source: "Kevin Lynch, The Image of the City (1960); A Theory of Good City Form (1981)"
elements: [paths, edges, districts, nodes, landmarks]
normative_models_1981: ["cosmic (city of faith: axes, cardinal order, e.g., Beijing)", "machine (practical, modular grid, e.g., Land Ordinance towns)", "organic (city as organism: bounded, cellular, e.g., Garden City)"]
use: "Good vocabulary for the LLM to describe a generated city, and to make sure each city has memorable edges (water, rail, ring) and landmarks."
```

---

## 4. Growth-story cards for Step 2 ("How did it grow?")

Each card gives a catchy name, a one-line pitch, a real example, slider values, best-fit terrain, and the generator's growth rule. Values are consistent with §1. Example facts were verified above.

```yaml
- id: gridiron_boomtown
  name: "Gridiron Boomtown"
  pitch: "Surveyors got here first: every street ruler-straight, every lot for sale."
  example: "Chicago: platted 1830, the most grid-ordered of 100 world cities (Boeing 2019)"
  sliders: {grid_organic: 0.05, sprawl_compact: 0.6, transit_car: 0.4, historic_modern: 0.7, block_size_meters: 100, district_size_meters: 2800}
  terrain_fit: [flat plains, lakeshore, river]
  growth: "Concentric expansion of a single cardinal grid; rail yards and industry along the river (Burgess rings)."

- id: medieval_tangle
  name: "Medieval Tangle"
  pitch: "A thousand years of footpaths, all leading to the market square."
  example: "Siena or Rome's centro (Rome φ 0.005, one of the 3 least-ordered big cities)"
  sliders: {grid_organic: 0.95, sprawl_compact: 0.95, transit_car: 0.05, historic_modern: 0.05, block_size_meters: 55, district_size_meters: 1000}
  terrain_fit: [hilltop, river bend, defensible spur]
  growth: "Organic infill inside a wall; when it bursts, the wall becomes a ring boulevard and suburbs spill along the roads out of each gate."

- id: legion_camp
  name: "Legion Camp"
  pitch: "Two crossing streets, four gates, one forum: a Roman fort that never left."
  example: "Timgad (c. 100 CE, 355 m square); Turin and Florence still show the castrum"
  sliders: {grid_organic: 0.2, sprawl_compact: 0.85, transit_car: 0.1, historic_modern: 0.15, block_size_meters: 60, district_size_meters: 1000}
  terrain_fit: [river crossing, flat valley]
  growth: "Tight orthogonal core; later medieval growth outside the walls turns organic."

- id: plaza_and_grid
  name: "Plaza & Grid"
  pitch: "Start with a plaza, a church and a royal decree, then repeat the block forever."
  example: "Buenos Aires (blocks of 140 varas ≈ 121 m; 4-way intersections 57.6%, highest of 100 cities)"
  sliders: {grid_organic: 0.1, sprawl_compact: 0.7, transit_car: 0.3, historic_modern: 0.35, block_size_meters: 120, district_size_meters: 1500}
  terrain_fit: [coastal plain, river estuary, highland basin]
  growth: "Uniform checkerboard radiating from the Plaza Mayor; new grids at new angles where the coast turns."

- id: canal_city
  name: "Canal City"
  pitch: "Dig a canal, build a house on its bank, repeat in rings."
  example: "Amsterdam's Grachtengordel (from 1613; UNESCO 2010)"
  sliders: {grid_organic: 0.35, sprawl_compact: 0.9, transit_car: 0.1, historic_modern: 0.1, block_size_meters: 80, district_size_meters: 1200}
  terrain_fit: [delta, marsh, low coast]
  growth: "Concentric half-rings of canals around the old core; reclaimed land added in planned phases."

- id: planned_capital
  name: "Planned Capital"
  pitch: "Grand avenues fan out from the halls of power: every view ends at a monument."
  example: "Washington DC (L'Enfant 1791): diagonal avenues over a grid; also Canberra, New Delhi"
  sliders: {grid_organic: 0.3, sprawl_compact: 0.7, transit_car: 0.35, historic_modern: 0.5, block_size_meters: 110, district_size_meters: 2000}
  terrain_fit: [river plain with a hill or two for monuments]
  growth: "Monuments on high points, straight diagonals between them, grid infill, a ceremonial mall to the water."

- id: hill_town
  name: "Hill Town"
  pitch: "Streets wind with the contours; stairs and funiculars do the rest."
  example: "Genoa, Lisbon, Valparaíso (contrast: San Francisco drove its grid straight up the hills)"
  sliders: {grid_organic: 0.85, sprawl_compact: 0.85, transit_car: 0.3, historic_modern: 0.25, block_size_meters: 60, district_size_meters: 1200}
  terrain_fit: [steep coast, mountains, river gorge]
  growth: "Dense along the flat waterfront first, then switchbacks climbing; steepest slopes stay green or become self-built neighbourhoods."
  variant: {name: "Grid Over the Hills", example: "San Francisco", grid_organic: 0.15}

- id: boulevard_makeover
  name: "Boulevard Makeover"
  pitch: "Out with the alleys: a prefect with a ruler carves boulevards through the old town."
  example: "Haussmann's Paris (1853–1870)"
  sliders: {grid_organic: 0.45, sprawl_compact: 0.95, transit_car: 0.2, historic_modern: 0.85, block_size_meters: 100, district_size_meters: 2300}
  terrain_fit: [river basin]
  growth: "Organic core first, then straight boulevards punched between stations and monuments, star-shaped places at junctions."

- id: railroad_whistle_stop
  name: "Whistle-Stop Town"
  pitch: "The railroad drew the town on a napkin: depot at the top, Main Street down the middle."
  example: "Hudson's Plains 'T-towns', e.g. Plentywood, Montana"
  sliders: {grid_organic: 0.1, sprawl_compact: 0.4, transit_car: 0.5, historic_modern: 0.5, block_size_meters: 100, district_size_meters: 1000}
  terrain_fit: [prairie, valley floor]
  growth: "Grid aligned to the tracks; industry and grain elevators line the rail; the 'other side of the tracks' grows differently."

- id: streetcar_suburb
  name: "Streetcar Suburb"
  pitch: "Follow the trolley line: shops at every stop, porches on every street."
  example: "Boston's Dorchester and Brookline (Warner, 'Streetcar Suburbs', 1962)"
  sliders: {grid_organic: 0.25, sprawl_compact: 0.55, transit_car: 0.25, historic_modern: 0.4, block_size_meters: 110, district_size_meters: 2000}
  terrain_fit: [any; best with a compact old core]
  growth: "Radial fingers along transit lines, dense at stops; wedges between them fill in later."

- id: garden_city
  name: "Garden City"
  pitch: "A town with a green belt. When it's full, you build the next one."
  example: "Letchworth (1903) and Welwyn (1920), after Howard's 32,000-person ideal"
  sliders: {grid_organic: 0.6, sprawl_compact: 0.35, transit_car: 0.35, historic_modern: 0.4, block_size_meters: 150, district_size_meters: 1500}
  terrain_fit: [gentle countryside near a rail line]
  growth: "Concentric town to a fixed limit, a permanent greenbelt, and growth by new satellites linked by rail."

- id: motor_city_sprawl
  name: "Motor City Sprawl"
  pitch: "Mile-square arterials, cul-de-sacs within, and a strip mall at every corner."
  example: "Houston, Phoenix, Atlanta, Charlotte (Charlotte: most orientation-disordered city of 100)"
  sliders: {grid_organic: 0.7, sprawl_compact: 0.1, transit_car: 0.95, historic_modern: 0.85, block_size_meters: 250, district_size_meters: 4500}
  terrain_fit: [flat plain, desert, rolling hills]
  growth: "Arterial grid (1.6 km), loops and lollipops inside; multiple nuclei at highway junctions; beltway rings."

- id: tower_park
  name: "Towers in the Park"
  pitch: "Clear the slate: superblocks, green lawns, and slabs on stilts."
  example: "Brasília's 280 × 280 m superquadras (1957–60); Chandigarh's sectors"
  sliders: {grid_organic: 0.2, sprawl_compact: 0.55, transit_car: 0.6, historic_modern: 1.0, block_size_meters: 300, district_size_meters: 2500}
  terrain_fit: [open plateau]
  growth: "Built all at once on a master plan; highways between superblocks; growth via satellite towns."

- id: self_built_city
  name: "Self-Built City"
  pitch: "No plan, a million builders: lanes, stairs and rooftops added one room at a time."
  example: "Rocinha (Rio), Comuna 13 (Medellín), Dharavi (Mumbai)"
  sliders: {grid_organic: 0.9, sprawl_compact: 0.95, transit_car: 0.15, historic_modern: 0.3, block_size_meters: 50, district_size_meters: 1000}
  terrain_fit: [steep hillsides, floodplain edges, rail and canal margins]
  growth: "Incremental accretion on land formal development skipped; slow consolidation and upgrading over decades."
  ux_note: "Respectful framing; avoid 'slum'."
```

Suggested shortlist for 8 cards: Gridiron Boomtown, Medieval Tangle, Plaza & Grid, Canal City, Planned Capital, Hill Town, Streetcar Suburb, Motor City Sprawl. Add Garden City and Boulevard Makeover if 10 are allowed.

---

## 5. Notes for the World Brief LLM (corpus guidance)

### 5.1 Keyword → slider nudges (heuristics)

| User says… | Nudge |
|---|---|
| "old", "ancient", "medieval", "walled", "winding", "cobblestone" | grid_organic ↑ (0.8–1.0), historic_modern ↓, block 50–70 |
| "grid", "planned", "American", "boomtown", "numbered streets" | grid_organic ↓ (0–0.15) |
| "boulevards", "Paris-like", "grand avenues" | grid_organic 0.4–0.5, historic_modern ↑, add radial diagonals |
| "suburbs", "cul-de-sacs", "car", "strip malls", "sunbelt" | sprawl_compact ↓, transit_car ↑, block 200–300, district 4000+ |
| "trams", "streetcar", "subway", "walkable" | transit_car ↓, sprawl_compact ↑ |
| "hills", "mountain", "steep" | grid_organic ↑ (unless "San Francisco-style"), compact core on the flat |
| "canals", "delta", "lagoon" | canal_city flavour, grid_organic 0.3–0.5, block 60–90 |
| "colonial Spanish", "plaza", "Latin American" | plaza_and_grid, block ~120 |
| "Soviet", "brutalist", "modernist" | modernist_superblock, block 250–300, historic_modern 1.0 |
| "Japanese", "Tokyo-like" | fine grain (Tokyo l̃ 49.6 m), φ low, transit_car ~0.1, block 50–60 |

### 5.2 Accuracy guardrails (common myths)

- **Hippodamus did not invent the grid.** Orthogonal towns predate him (e.g., Indus Valley, earlier Greek colonies). He is the figure Aristotle credits with planning theory.
- **San Francisco "planners thought it was flat"** is folklore. O'Farrell's 1847 survey extended the existing rectilinear plan, and landowner interests resisted contour alignments.
- **Houston has no zoning, but it has deed restrictions and setback/lot rules.** Its sprawl isn't caused by big downtown blocks (those are 76 m).
- **"Organic" ≠ "unplanned"** (Kostof). Many medieval towns were laid out by lords; organic pattern comes from incremental growth and terrain.
- **Haussmann statistics vary wildly between sources.** Avoid exact demolition counts in UI copy.
- **Garden City acreage:** Howard's text says a 1,000-acre town on a 6,000-acre estate. Some summaries say 9,000.
- **Laws of the Indies** were codified in **1573**. Many earlier grids (Santo Domingo 1502, Mexico City 1522) informed them.
- **φ (orientation order) is not "griddedness" by itself.** Buenos Aires has φ 0.15 yet is almost fully gridded at multiple angles. Use φ together with circuity, node degree and 4-way share.

### 5.3 Kostof framing quote (useful for tone)

> "We 'read' form correctly only to the extent that we are familiar with the precise cultural conditions that generated it." Spiro Kostof, *The City Shaped* (1991), p.10, as quoted in Boeing 2019.

Kostof's chapters map neatly onto Step 2 choices: "Organic" Patterns, The Grid, The City as Diagram (ideal and radial cities), The Grand Manner (Baroque, Haussmann, capitals), The Urban Skyline.

---

