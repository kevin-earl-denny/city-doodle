/**
 * Inline SVG illustrations for the "Found a city" flow (CITY-658), ported
 * from the Paper design:
 *
 * - LandMiniMap: the 121×78 terrain thumbnails on the step-1 cards
 * - StoryThumbnail: the 167×64 street-pattern thumbnails on the step-2 cards
 * - LandPlateArt: the big preview drawn inside <Plate> (396×268 user units),
 *   the mini-map scaled up on graph paper, plus the chosen street pattern
 *   clipped to the land
 */

import { useId, type ReactNode } from "react";
import type { GeographicSetting } from "../../api/types";
import type { GrowthStoryId } from "./growthStories";
import { PLATE_HEIGHT, PLATE_WIDTH } from "./Plate";

/** Palette as CSS variables (defined in index.css @theme). */
const C = {
  ink: "var(--color-ink)",
  water: "var(--color-water)",
  river: "var(--color-river)",
  coast: "var(--color-coast)",
  deepWater: "var(--color-deep-water)",
  contour: "var(--color-contour)",
  sand: "var(--color-sand)",
  parchment: "var(--color-parchment)",
  beach: "var(--color-beach)",
  lake: "var(--color-lake)",
  gridLine: "var(--color-grid-line)",
  surveyLine: "var(--color-survey-line)",
  grove: "var(--color-grove)",
  marsh: "var(--color-marsh)",
};

// ============================================================================
// Land mini-maps (121×78)
// ============================================================================

const MINI_W = 121;
const MINI_H = 78;

interface LandArt {
  /** Fills: background and water/land masses. `rx` rounds the background. */
  ground: (rx: number) => ReactNode;
  /** Strokes: coasts, contours, rivers. `k` scales stroke widths. */
  lines: (k: number) => ReactNode;
  /** Mask content (white = land) in the same coordinate space. */
  land: ReactNode;
}

const COASTAL_COAST = "M84 0 C 76 14, 90 26, 80 40 C 72 54, 88 64, 82 78";
const BAY_COAST =
  "M121 44 C 104 42, 98 30, 84 26 C 66 20, 46 30, 48 46 C 50 60, 70 62, 80 70 C 86 74, 88 78, 90 78";
const LAKE_SHORE = "M121 22 C 100 30, 84 20, 64 28 C 44 36, 24 26, 0 32";
const VALLEY_RIVER =
  "M0 46 C 18 30, 30 52, 48 40 C 66 28, 74 50, 92 38 C 104 30, 112 36, 121 32";
const ISLAND_LAND =
  "M34 38 C 33 25, 52 16, 66 21 C 80 26, 93 23, 94 37 C 95 50, 80 59, 62 56 C 46 54, 35 51, 34 38 Z";
const PENINSULA_LAND =
  "M0 78 L0 44 C 20 40, 40 34, 58 24 C 72 16, 88 14, 96 22 C 102 30, 92 40, 78 46 C 60 54, 46 66, 40 78 Z";
const DELTA_COAST =
  "M121 34 C 113 36, 106 40, 103 47 C 100 55, 95 60, 89 57 C 85 55, 82 60, 79 66 C 76 72, 70 74, 66 69 C 63 73, 57 76, 52 73 C 48 70, 47 64, 42 64 C 36 64, 30 68, 25 62 C 21 57, 22 50, 16 45 C 11 41, 5 40, 0 40";
const DELTA_LAND = `M0 0 H121 V34 ${DELTA_COAST.replace(/^M121 34 /, "")} Z`;

const allLand = <rect width={MINI_W} height={MINI_H} fill="white" />;

const LAND_ART: Record<GeographicSetting, LandArt> = {
  coastal: {
    ground: (rx) => (
      <>
        <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.parchment} />
        <path d={`${COASTAL_COAST} L121 78 L121 0 Z`} fill={C.water} />
      </>
    ),
    lines: (k) => (
      <>
        <path d={COASTAL_COAST} fill="none" stroke={C.coast} strokeWidth={1.5 * k} />
        <path d={COASTAL_COAST} transform="translate(-4 0)" fill="none" stroke={C.beach} strokeWidth={4 * k} />
        <path d="M10 22 C 28 16, 44 28, 62 22 M8 50 C 28 44, 46 58, 66 50" fill="none" stroke={C.contour} strokeWidth={k} />
      </>
    ),
    land: (
      <>
        {allLand}
        <path d={`${COASTAL_COAST} L121 78 L121 0 Z`} fill="black" />
      </>
    ),
  },
  bay_harbor: {
    ground: (rx) => (
      <>
        <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.parchment} />
        <path d={`${BAY_COAST} L121 78 Z`} fill={C.water} />
      </>
    ),
    lines: (k) => (
      <>
        <path d={BAY_COAST} fill="none" stroke={C.coast} strokeWidth={1.5 * k} />
        <path d="M10 14 C 30 8, 50 18, 72 10 M6 64 C 18 58, 30 70, 40 66" fill="none" stroke={C.contour} strokeWidth={k} />
      </>
    ),
    land: (
      <>
        {allLand}
        <path d={`${BAY_COAST} L121 78 Z`} fill="black" />
      </>
    ),
  },
  river_valley: {
    ground: (rx) => <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.parchment} />,
    lines: (k) => (
      <>
        <path
          d="M4 12 C 24 6, 40 18, 60 12 C 80 6, 96 16, 117 10 M4 22 C 26 16, 44 28, 62 22 C 82 16, 98 26, 117 20 M4 58 C 24 52, 42 64, 62 58 C 82 52, 98 62, 117 56 M4 68 C 26 62, 44 74, 64 68 C 84 62, 100 72, 117 66"
          fill="none"
          stroke={C.contour}
          strokeWidth={k}
        />
        <path d={VALLEY_RIVER} fill="none" stroke={C.river} strokeWidth={4 * k} strokeLinecap="round" />
      </>
    ),
    land: (
      <>
        {allLand}
        <path d={VALLEY_RIVER} fill="none" stroke="black" strokeWidth={5} />
      </>
    ),
  },
  lakefront: {
    ground: (rx) => (
      <>
        <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.parchment} />
        <path d={`M0 0 L121 0 L121 22 ${LAKE_SHORE.replace(/^M121 22 /, "")} Z`} fill={C.lake} />
      </>
    ),
    lines: (k) => (
      <>
        <path d={LAKE_SHORE} fill="none" stroke={C.coast} strokeWidth={1.5 * k} />
        <path d="M6 52 C 26 46, 46 58, 70 50 C 88 44, 104 54, 117 48 M10 66 C 30 60, 52 72, 80 64" fill="none" stroke={C.contour} strokeWidth={k} />
        <path d="M40 78 C 44 60, 52 46, 58 32" fill="none" stroke={C.river} strokeWidth={2 * k} strokeLinecap="round" />
      </>
    ),
    land: (
      <>
        {allLand}
        <path d={`M0 0 L121 0 L121 22 ${LAKE_SHORE.replace(/^M121 22 /, "")} Z`} fill="black" />
      </>
    ),
  },
  inland: {
    ground: (rx) => <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.parchment} />,
    lines: (k) => (
      <>
        <path d="M0 20 H121 M0 46 H121 M0 72 H121 M24 0 V78 M56 0 V78 M88 0 V78" fill="none" stroke={C.surveyLine} strokeWidth={k} strokeDasharray="4 3" />
        <path d="M4 34 C 30 28, 60 40, 90 32 C 104 28, 114 32, 121 30 M0 60 C 34 54, 70 66, 121 58" fill="none" stroke={C.contour} strokeWidth={k} />
        <path
          d="M0 52 C 14 50, 18 40, 32 42 C 46 44, 50 56, 66 52 C 80 48, 82 36, 98 38 C 108 40, 114 34, 121 30"
          fill="none"
          stroke={C.river}
          strokeWidth={2 * k}
          strokeLinecap="round"
        />
        <circle cx="70" cy="18" r="2" fill={C.grove} />
        <circle cx="76" cy="22" r="2" fill={C.grove} />
        <circle cx="16" cy="68" r="2" fill={C.grove} />
        <circle cx="104" cy="66" r="2" fill={C.grove} />
      </>
    ),
    land: allLand,
  },
  island: {
    ground: (rx) => (
      <>
        <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.water} />
        <path
          d="M30 38 C 28 22, 50 12, 66 18 C 82 24, 96 20, 98 36 C 100 52, 82 64, 62 60 C 44 58, 32 54, 30 38 Z"
          fill={C.beach}
        />
        <path d={ISLAND_LAND} fill={C.parchment} />
      </>
    ),
    lines: (k) => (
      <>
        <path d={ISLAND_LAND} fill="none" stroke={C.coast} strokeWidth={1.5 * k} />
        <ellipse cx="64" cy="38" rx="14" ry="8" fill="none" stroke={C.contour} strokeWidth={k} />
      </>
    ),
    land: <path d={ISLAND_LAND} fill="white" />,
  },
  peninsula: {
    ground: (rx) => (
      <>
        <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.water} />
        <path d={PENINSULA_LAND} fill={C.parchment} />
      </>
    ),
    lines: (k) => (
      <>
        <path d={PENINSULA_LAND} fill="none" stroke={C.coast} strokeWidth={1.5 * k} />
        <path d="M12 62 C 30 54, 48 44, 70 32" fill="none" stroke={C.contour} strokeWidth={k} />
      </>
    ),
    land: <path d={PENINSULA_LAND} fill="white" />,
  },
  delta: {
    ground: (rx) => (
      <>
        <rect width={MINI_W} height={MINI_H} rx={rx} fill={C.water} />
        <path d={DELTA_LAND} fill={C.parchment} />
      </>
    ),
    lines: (k) => (
      <>
        <path d={DELTA_COAST} fill="none" stroke={C.coast} strokeWidth={1.5 * k} />
        <path d="M58 0 C 52 10, 64 18, 58 30" fill="none" stroke={C.river} strokeWidth={3 * k} strokeLinecap="round" />
        <path
          d="M58 30 C 50 38, 36 44, 30 58 M58 30 C 54 42, 58 54, 52 70 M58 30 C 64 40, 66 54, 70 68 M58 30 C 70 36, 84 40, 94 52"
          fill="none"
          stroke={C.river}
          strokeWidth={1.8 * k}
          strokeLinecap="round"
        />
        <path
          d="M40 52 h5 M42 49 v-2 M44 49 v-2 M76 50 h5 M78 47 v-2 M80 47 v-2 M60 60 h4 M61.5 57 v-2"
          fill="none"
          stroke={C.marsh}
          strokeWidth={k}
          strokeLinecap="round"
        />
        <path d="M8 18 C 26 12, 40 22, 50 16 M70 14 C 84 8, 98 18, 116 12" fill="none" stroke={C.contour} strokeWidth={k} />
      </>
    ),
    land: <path d={DELTA_LAND} fill="white" />,
  },
};

export function LandMiniMap({ id, className }: { id: GeographicSetting; className?: string }) {
  const art = LAND_ART[id];
  return (
    <svg
      viewBox={`0 0 ${MINI_W} ${MINI_H}`}
      className={className}
      aria-hidden="true"
      preserveAspectRatio="xMidYMid slice"
    >
      {art.ground(3)}
      {art.lines(1)}
    </svg>
  );
}

// ============================================================================
// Growth-story thumbnails (167×64)
// ============================================================================

const STORY_W = 167;
const STORY_H = 64;

/** Medieval town blocks inside an oval wall, around a market square. */
function MedievalTown() {
  const blocks = [
    "M24 30 L38 17 L60 13 L63 24 L48 30 Z",
    "M67 11 L96 9 L99 20 L82 25 L69 22 Z",
    "M103 10 L130 14 L141 26 L118 28 L105 22 Z",
    "M22 38 L46 35 L58 44 L44 56 L28 50 Z",
    "M62 42 L74 39 L80 45 L79 58 L61 55 Z",
    "M88 41 L104 38 L112 50 L100 58 L86 56 Z",
    "M110 32 L144 31 L140 45 L118 47 Z",
    "M117 52 L135 49 L130 58 Z",
  ];
  return (
    <>
      {blocks.map((d) => (
        <path key={d} d={d} fill={C.sand} stroke={C.ink} strokeLinejoin="round" />
      ))}
      <path
        d="M14 34 C 12 14, 50 4, 86 4 C 124 4, 156 14, 154 34 C 152 54, 120 62, 84 62 C 48 62, 16 54, 14 34 Z"
        fill="none"
        stroke={C.ink}
        strokeWidth="2.4"
      />
      <circle cx="85" cy="32" r="3.2" fill={C.water} stroke={C.ink} />
    </>
  );
}

const STORY_THUMBS: Record<GrowthStoryId, ReactNode> = {
  medieval_tangle: <MedievalTown />,
  boomtown_grid: (
    <>
      <path
        d="M12 0 V64 M34 0 V64 M56 0 V64 M78 0 V64 M100 0 V64 M122 0 V64 M144 0 V64 M0 10 H167 M0 26 H167 M0 42 H167 M0 58 H167"
        fill="none"
        stroke={C.ink}
        strokeWidth="1.1"
      />
      <path d="M0 0 L167 64" fill="none" stroke={C.ink} strokeWidth="2" />
    </>
  ),
  grand_boulevards: (
    <>
      <path d="M14 0 V64 M34 0 V64 M54 0 V64 M114 0 V64 M134 0 V64 M154 0 V64 M0 14 H167 M0 50 H167" fill="none" stroke={C.contour} />
      <path
        d="M84 32 L0 0 M84 32 L167 0 M84 32 L0 64 M84 32 L167 64 M84 32 H0 M84 32 H167 M84 32 V0 M84 32 V64"
        fill="none"
        stroke={C.ink}
        strokeWidth="1.6"
      />
      <circle cx="84" cy="32" r="9" fill={C.parchment} stroke={C.ink} strokeWidth="1.6" />
    </>
  ),
  hill_town: (
    <>
      <path
        d="M18 58 C 8 40, 40 10, 86 7 C 132 4, 162 26, 152 46 C 144 62, 62 68, 18 58 Z M42 49 C 36 34, 62 17, 89 15 C 117 13, 134 29, 127 42 C 119 55, 66 57, 42 49 Z M66 40 C 63 30, 77 23, 90 23 C 104 23, 111 31, 107 38 C 101 46, 74 46, 66 40 Z"
        fill="none"
        stroke={C.contour}
      />
      <path
        d="M30 54 C 24 38, 52 15, 88 11 C 124 8, 152 28, 140 46 M54 45 C 50 33, 70 20, 89 19 C 110 18, 124 30, 117 41"
        fill="none"
        stroke={C.ink}
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path d="M88 11 V24 M46 50 L58 42 M140 46 L121 38" fill="none" stroke={C.ink} strokeWidth="2.6" strokeDasharray="1.2 1.6" />
      <rect x="83" y="28" width="12" height="9" fill={C.water} stroke={C.ink} strokeWidth="1.2" />
    </>
  ),
  streetcar_suburb: (
    <>
      <path d="M0 32 H167 M40 0 V64 M120 0 V64" fill="none" stroke={C.ink} strokeWidth="2.2" />
      <path d="M0 32 H167 M40 0 V64 M120 0 V64" fill="none" stroke={C.parchment} strokeWidth="0.8" strokeDasharray="3 3" />
      <path
        d="M8 8 H72 M8 20 H72 M8 44 H72 M8 56 H72 M88 8 H158 M88 20 H158 M88 44 H158 M88 56 H158 M24 4 V60 M56 4 V60 M104 4 V60 M140 4 V60"
        fill="none"
        stroke={C.contour}
      />
    </>
  ),
  motor_sprawl: (
    <>
      <path d="M0 18 H167" fill="none" stroke={C.ink} strokeWidth="4.5" />
      <path d="M0 18 H167" fill="none" stroke={C.parchment} strokeWidth="1.3" />
      <path d="M56 0 V64" fill="none" stroke={C.ink} strokeWidth="2.2" />
      {[
        [50, 12],
        [62, 12],
        [50, 24],
        [62, 24],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="5" fill="none" stroke={C.ink} strokeWidth="1.1" />
      ))}
      <path d="M56 42 C 80 40, 98 50, 120 47 C 140 44, 150 54, 167 58 M56 46 C 40 46, 28 52, 14 60" fill="none" stroke={C.ink} strokeWidth="1.4" />
      <path d="M84 42 L84 33 M106 49 L107 58 M128 46 L130 35 M150 53 L146 61 M40 47 L38 37 M27 53 L30 61" fill="none" stroke={C.ink} strokeWidth="1.1" />
      {[
        [84, 31],
        [107, 60],
        [130, 33],
        [38, 35],
        [30, 63],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.6" fill={C.parchment} stroke={C.ink} strokeWidth="1.1" />
      ))}
      <rect x="100" y="26" width="40" height="12" fill="none" stroke={C.contour} />
      <rect x="104" y="28" width="14" height="8" fill={C.ink} />
      <path d="M124 28 V36 M128 28 V36 M132 28 V36 M136 28 V36" fill="none" stroke={C.contour} strokeWidth="0.8" />
    </>
  ),
};

export function StoryThumbnail({ id, className }: { id: GrowthStoryId; className?: string }) {
  return (
    <svg
      viewBox={`0 0 ${STORY_W} ${STORY_H}`}
      className={className}
      aria-hidden="true"
      preserveAspectRatio="xMidYMid slice"
    >
      <rect width={STORY_W} height={STORY_H} rx="3" fill={C.parchment} />
      {STORY_THUMBS[id]}
    </svg>
  );
}

// ============================================================================
// Plate art (396×268)
// ============================================================================

interface PlateLabel {
  x: number;
  y: number;
  text: (stem: string) => string;
  size?: "lg" | "sm";
  anchor?: "start" | "middle" | "end";
  /** Degrees around (x, y), e.g. -90 to run a label up a narrow strip of water. */
  rotate?: number;
}

interface PlateLand {
  ground: ReactNode;
  lines: ReactNode;
  /** Mask for the graph-paper grid (white = land). */
  land: ReactNode;
  /** Mask for the street overlay; defaults to `land`. */
  streets?: ReactNode;
  /** Where the old town sits, for story overlays centred on it. */
  core: [number, number];
  labels: PlateLabel[];
}

/** Uniform scale that fills the plate with a mini-map (cropping the sides). */
const PLATE_SCALE = PLATE_HEIGHT / MINI_H;
const PLATE_SHIFT = (PLATE_WIDTH - MINI_W * PLATE_SCALE) / 2;
const MINI_TO_PLATE = `translate(${PLATE_SHIFT.toFixed(2)} 0) scale(${PLATE_SCALE.toFixed(4)})`;
/** Stroke multiplier for scaled mini-maps (strokes don't scale, see below). */
const PLATE_STROKE = 1.25;

function scaledMini(id: GeographicSetting, core: [number, number], labels: PlateLabel[]): PlateLand {
  const art = LAND_ART[id];
  return {
    ground: <g transform={MINI_TO_PLATE}>{art.ground(0)}</g>,
    lines: (
      <g transform={MINI_TO_PLATE} className="[&_*]:[vector-effect:non-scaling-stroke]">
        {art.lines(PLATE_STROKE)}
      </g>
    ),
    land: <g transform={MINI_TO_PLATE}>{art.land}</g>,
    core,
    labels,
  };
}

const BAY_PLATE_COAST =
  "M396 150 C 350 146, 330 104, 286 92 C 230 76, 168 104, 174 156 C 180 202, 240 210, 268 236 C 280 248, 284 268, 290 268";

const PLATE_LANDS: Record<GeographicSetting, PlateLand> = {
  coastal: scaledMini("coastal", [140, 110], [{ x: 352, y: 110, text: (s) => `${s} Sound`, rotate: -90 }]),
  // The bay plate is drawn separately in Paper (with Mill Creek).
  bay_harbor: {
    ground: <path d={`${BAY_PLATE_COAST} L396 268 Z`} fill={C.water} />,
    lines: (
      <>
        <path d={BAY_PLATE_COAST} fill="none" stroke={C.beach} strokeWidth="6" />
        <path d={BAY_PLATE_COAST} fill="none" stroke={C.coast} strokeWidth="2" />
        <path
          d="M20 40 C 70 24, 120 50, 170 36 C 210 26, 240 40, 270 30 M14 70 C 60 56, 110 80, 150 66 M30 214 C 60 200, 90 222, 130 210 M20 244 C 60 232, 100 252, 150 240"
          fill="none"
          stroke={C.contour}
          strokeWidth="1.2"
        />
        <path d="M0 120 C 40 112, 80 132, 120 124 C 150 118, 164 130, 176 140" fill="none" stroke={C.river} strokeWidth="3.5" strokeLinecap="round" />
      </>
    ),
    land: (
      <>
        <rect width={PLATE_WIDTH} height={PLATE_HEIGHT} fill="white" />
        <path d={`${BAY_PLATE_COAST} L396 268 Z`} fill="black" />
      </>
    ),
    streets: (
      <path
        d="M0 0 L396 0 L396 142 C 350 138, 330 96, 286 84 C 230 68, 160 98, 166 156 C 172 206, 236 216, 262 240 C 272 250, 276 268, 280 268 L0 268 Z"
        fill="white"
      />
    ),
    core: [100, 120],
    labels: [
      { x: 226, y: 156, text: (s) => `${s} Bay`, anchor: "start" },
      { x: 40, y: 106, text: () => "Mill Creek", size: "sm", anchor: "start" },
    ],
  },
  river_valley: scaledMini("river_valley", [196, 100], [{ x: 300, y: 108, text: (s) => `${s} River` }]),
  lakefront: scaledMini("lakefront", [200, 160], [{ x: 200, y: 44, text: (s) => `Lake ${s}` }]),
  inland: scaledMini("inland", [200, 120], [{ x: 40, y: 140, text: (s) => `${s} Creek`, size: "sm", anchor: "start" }]),
  island: scaledMini("island", [210, 130], [{ x: 24, y: 30, text: (s) => `${s} Sound`, anchor: "start" }]),
  peninsula: scaledMini("peninsula", [225, 110], [{ x: 330, y: 40, text: (s) => `${s} Bay` }]),
  delta: scaledMini("delta", [190, 70], [{ x: 390, y: 206, text: (s) => `${s} Gulf`, size: "sm", anchor: "end" }]),
};

const NAME_PREFIXES = new Set([
  "port", "new", "fort", "saint", "st.", "san", "santa", "mount", "lake", "east", "west",
  "north", "south", "old", "upper", "lower", "little", "great", "the", "el", "la", "le", "los", "las",
]);

/** "Port Wren" -> "Wren", "Gull Harbor" -> "Gull": the word plate labels are named after. */
function placeStem(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "Mill";
  return words.find((w) => !NAME_PREFIXES.has(w.toLowerCase())) ?? words[words.length - 1];
}

function range(start: number, end: number, step: number): number[] {
  const out: number[] = [];
  for (let v = start; v <= end; v += step) out.push(v);
  return out;
}

/** Street pattern for each story, in plate units, drawn over the land. */
function storyOverlay(id: GrowthStoryId, [cx, cy]: [number, number]): ReactNode {
  const W = PLATE_WIDTH;
  const H = PLATE_HEIGHT;
  switch (id) {
    case "boomtown_grid": {
      // Ported from the Paper "Street overlay": a slightly rotated survey grid.
      const rows = range(10, 270, 20).map((y) => `M-20 ${y} H420`);
      const cols = range(10, 374, 26).map((x) => `M${x} -20 V300`);
      return (
        <g transform="rotate(-6 200 134)">
          <path d={[...rows, ...cols].join(" ")} fill="none" stroke={C.ink} strokeOpacity={0.55} />
          <path d="M-20 -10 L300 300" fill="none" stroke={C.ink} strokeWidth="2.4" />
          <path d="M-20 130 H420" fill="none" stroke={C.ink} strokeWidth="2.4" />
        </g>
      );
    }
    case "medieval_tangle":
      return (
        <>
          <path
            d={`M${cx - 104} ${cy} C ${cx - 140} ${cy - 10}, ${cx - 170} ${cy + 20}, ${cx - 220} ${cy + 6} M${cx + 104} ${cy - 6} C ${cx + 140} ${cy - 30}, ${cx + 170} ${cy - 10}, ${cx + 230} ${cy - 30} M${cx - 20} ${cy + 46} C ${cx - 30} ${cy + 80}, ${cx - 10} ${cy + 110}, ${cx - 24} ${cy + 160} M${cx + 30} ${cy - 46} C ${cx + 40} ${cy - 80}, ${cx + 20} ${cy - 110}, ${cx + 36} ${cy - 160}`}
            fill="none"
            stroke={C.ink}
            strokeWidth="1.4"
            strokeOpacity={0.7}
          />
          <g transform={`translate(${cx - 84 * 1.3} ${cy - 32 * 1.3}) scale(1.3)`}>
            <MedievalTown />
          </g>
        </>
      );
    case "grand_boulevards": {
      const grid = [...range(cx % 26, W, 26).map((x) => `M${x} 0 V${H}`), ...range(cy % 26, H, 26).map((y) => `M0 ${y} H${W}`)];
      const rays = [0, 35, 90, 145, 180, 215, 270, 325].map((deg) => {
        const r = (deg * Math.PI) / 180;
        return `M${cx} ${cy} L${(cx + Math.cos(r) * 520).toFixed(1)} ${(cy + Math.sin(r) * 520).toFixed(1)}`;
      });
      return (
        <>
          <path d={grid.join(" ")} fill="none" stroke={C.ink} strokeOpacity={0.3} />
          <path d={rays.join(" ")} fill="none" stroke={C.ink} strokeWidth="2.2" />
          <circle cx={cx} cy={cy} r="13" fill={C.parchment} stroke={C.ink} strokeWidth="2" />
        </>
      );
    }
    case "hill_town": {
      const radii = [36, 70, 104, 138, 172];
      const stairs = [-90, 30, 150].map((deg) => {
        const r = (deg * Math.PI) / 180;
        const pt = (rx: number) => `${(cx + Math.cos(r) * rx).toFixed(1)} ${(cy + Math.sin(r) * rx * 0.6).toFixed(1)}`;
        return `M${pt(36)} L${pt(138)}`;
      });
      return (
        <>
          {radii.map((rx, i) => (
            <ellipse
              key={rx}
              cx={cx}
              cy={cy}
              rx={rx}
              ry={rx * 0.6}
              fill="none"
              stroke={i % 2 === 0 ? C.ink : C.contour}
              strokeWidth={i % 2 === 0 ? 1.4 : 1}
            />
          ))}
          <path d={stairs.join(" ")} fill="none" stroke={C.ink} strokeWidth="3" strokeDasharray="1.4 2" />
          <rect x={cx - 8} y={cy - 6} width="16" height="12" fill={C.water} stroke={C.ink} strokeWidth="1.4" />
        </>
      );
    }
    case "streetcar_suburb": {
      const grid = [...range(cx % 22, W, 22).map((x) => `M${x} 0 V${H}`), ...range(cy % 22, H, 22).map((y) => `M0 ${y} H${W}`)];
      const tracks = `M0 ${cy} H${W} M${cx - 66} 0 V${H} M${cx + 88} 0 V${H}`;
      return (
        <>
          <path d={grid.join(" ")} fill="none" stroke={C.ink} strokeOpacity={0.3} />
          <path d={tracks} fill="none" stroke={C.ink} strokeWidth="3.4" />
          <path d={tracks} fill="none" stroke={C.parchment} strokeWidth="1" strokeDasharray="4 4" />
        </>
      );
    }
    case "motor_sprawl": {
      const fy = cy - 55;
      const arterials = [
        ...[-165, -55, 55, 165].map((dx) => `M${cx + dx} 0 V${H}`),
        `M0 ${cy + 55} H${W}`,
        `M0 ${cy + 165} H${W}`,
      ].join(" ");
      const pods = [
        [cx, cy],
        [cx - 110, cy],
        [cx + 110, cy],
        [cx, cy + 110],
        [cx - 110, cy - 110],
        [cx + 110, cy - 110],
        [cx - 110, cy + 110],
        [cx + 110, cy + 110],
      ];
      return (
        <>
          <path d={arterials} fill="none" stroke={C.ink} strokeWidth="2" />
          {pods.map(([x, y]) => (
            <g key={`${x}-${y}`} fill="none" stroke={C.ink} strokeWidth="1.3">
              <path d={`M${x - 55} ${y + 8} C ${x - 20} ${y - 12}, ${x + 18} ${y + 22}, ${x + 55} ${y + 2}`} />
              <path d={`M${x - 24} ${y + 2} L${x - 26} ${y - 22} M${x + 6} ${y + 6} L${x + 8} ${y + 30} M${x + 32} ${y + 6} L${x + 34} ${y - 20}`} />
              <circle cx={x - 26} cy={y - 26} r="4" fill={C.parchment} />
              <circle cx={x + 8} cy={y + 34} r="4" fill={C.parchment} />
              <circle cx={x + 34} cy={y - 24} r="4" fill={C.parchment} />
            </g>
          ))}
          <path d={`M0 ${fy} H${W}`} fill="none" stroke={C.ink} strokeWidth="6" />
          <path d={`M0 ${fy} H${W}`} fill="none" stroke={C.parchment} strokeWidth="1.8" />
          {[
            [-9, -9],
            [9, -9],
            [-9, 9],
            [9, 9],
          ].map(([dx, dy]) => (
            <circle key={`${dx}${dy}`} cx={cx - 55 + dx} cy={fy + dy} r="8" fill="none" stroke={C.ink} strokeWidth="1.3" />
          ))}
        </>
      );
    }
  }
}

interface LandPlateArtProps {
  land: GeographicSetting;
  story?: GrowthStoryId | null;
  /** City name; plate labels are named after it ("Gull Harbor" -> "Gull Bay"). */
  placeName: string;
}

/** Content for <Plate>: land on graph paper, place labels, optional streets. */
export function LandPlateArt({ land, story, placeName }: LandPlateArtProps) {
  const uid = useId().replace(/:/g, "");
  const gridId = `plate-grid-${uid}`;
  const landId = `plate-land-${uid}`;
  const streetsId = `plate-streets-${uid}`;
  const plate = PLATE_LANDS[land];
  const stem = placeStem(placeName);

  return (
    <>
      <defs>
        <pattern id={gridId} width="22" height="22" patternUnits="userSpaceOnUse">
          <path d="M22 0 L0 0 L0 22" fill="none" stroke={C.gridLine} />
        </pattern>
        <mask id={landId} maskUnits="userSpaceOnUse" x="0" y="0" width={PLATE_WIDTH} height={PLATE_HEIGHT}>
          {plate.land}
        </mask>
        <mask id={streetsId} maskUnits="userSpaceOnUse" x="0" y="0" width={PLATE_WIDTH} height={PLATE_HEIGHT}>
          {plate.streets ?? plate.land}
        </mask>
      </defs>
      {plate.ground}
      <rect width={PLATE_WIDTH} height={PLATE_HEIGHT} fill={`url(#${gridId})`} mask={`url(#${landId})`} />
      {plate.lines}
      {story && <g mask={`url(#${streetsId})`}>{storyOverlay(story, plate.core)}</g>}
      {/* Labels sit above the streets with a paper-coloured halo, the usual
          cartographic trick for keeping names legible over linework. */}
      {plate.labels.map((label) => (
        <text
          key={`${label.x}-${label.y}`}
          x={label.x}
          y={label.y}
          textAnchor={label.anchor ?? "middle"}
          transform={label.rotate ? `rotate(${label.rotate} ${label.x} ${label.y})` : undefined}
          fill={C.deepWater}
          stroke={C.parchment}
          strokeWidth={3}
          strokeLinejoin="round"
          paintOrder="stroke"
          style={{ fontFamily: "var(--font-display)" }}
          fontStyle="italic"
          fontSize={label.size === "sm" ? 12 : 15}
          fontWeight={label.size === "sm" ? 400 : 500}
          letterSpacing={label.size === "sm" ? undefined : "0.02em"}
        >
          {label.text(stem)}
        </text>
      ))}
    </>
  );
}
