/**
 * Growth stories for step 2 of the "Found a city" flow (CITY-658).
 *
 * Each story is a preset for the street-layout sliders. The values come
 * from urban-morphology research and may be tuned later, so keep them here.
 */

import type { WorldSettings } from "../../api/types";

export type GrowthStoryId =
  | "medieval_tangle"
  | "boomtown_grid"
  | "grand_boulevards"
  | "hill_town"
  | "streetcar_suburb"
  | "motor_sprawl";

export type GrowthSettings = Pick<
  WorldSettings,
  | "grid_organic"
  | "sprawl_compact"
  | "transit_car"
  | "historic_modern"
  | "block_size_meters"
  | "district_size_meters"
>;

export interface GrowthStory {
  id: GrowthStoryId;
  label: string;
  /** Card copy, shown before the examples. */
  blurb: string;
  examples: [string, string];
  /** Sentence for "THE STORY SO FAR". */
  pitch?: string;
  /** Caveat "expect: …" line. */
  expect: string;
  /** Short phrase for the charter, e.g. "a railroad grid". */
  charter: string;
  settings: GrowthSettings;
}

function settings(
  grid_organic: number,
  sprawl_compact: number,
  transit_car: number,
  historic_modern: number,
  block_size_meters: number,
  district_size_meters: number,
): GrowthSettings {
  return {
    grid_organic,
    sprawl_compact,
    transit_car,
    historic_modern,
    block_size_meters,
    district_size_meters,
  };
}

export const GROWTH_STORIES: readonly GrowthStory[] = [
  {
    id: "medieval_tangle",
    label: "Medieval Tangle",
    blurb: "Lanes wander out from a market square.",
    examples: ["Siena", "Fez"],
    pitch: "A thousand years of footpaths, all leading to the market square.",
    expect: "crooked lanes, a town wall, one big square",
    charter: "a tangle of medieval lanes",
    settings: settings(0.95, 0.95, 0.05, 0.05, 55, 1000),
  },
  {
    id: "boomtown_grid",
    label: "Boomtown Grid",
    blurb: "Surveyed fast, sold by the lot.",
    examples: ["Chicago", "Salt Lake"],
    pitch: "Surveyors got here first: every street ruler-straight, every lot for sale.",
    expect: "long avenues, a grid that bends",
    charter: "a railroad grid",
    settings: settings(0.05, 0.6, 0.4, 0.7, 100, 2800),
  },
  {
    id: "grand_boulevards",
    label: "Grand Boulevards",
    blurb: "Avenues radiate from monuments.",
    examples: ["Washington", "Canberra"],
    pitch: "Grand avenues fan out from the halls of power; every view ends at a monument.",
    expect: "roundabouts, long sightlines, a grand axis",
    charter: "grand radiating boulevards",
    settings: settings(0.3, 0.7, 0.35, 0.5, 110, 2000),
  },
  {
    id: "hill_town",
    label: "Hill Town",
    blurb: "Streets hug the contours, stairs cut between.",
    examples: ["Lisbon", "Genoa"],
    pitch: "Streets wind with the contours; stairs and funiculars do the rest.",
    expect: "switchbacks, stairways, lookouts",
    charter: "streets that hug the hills",
    settings: settings(0.85, 0.85, 0.3, 0.25, 60, 1200),
  },
  {
    id: "streetcar_suburb",
    label: "Streetcar Suburb",
    blurb: "Main streets grow along the tracks.",
    examples: ["Toronto", "Boston"],
    pitch: "Follow the trolley line: shops at every stop, porches on every street.",
    expect: "main streets, corner shops, porches",
    charter: "main streets along the tram lines",
    settings: settings(0.25, 0.55, 0.25, 0.4, 110, 2000),
  },
  {
    id: "motor_sprawl",
    label: "Motor Sprawl",
    blurb: "Freeways, cul-de-sacs, big lots.",
    examples: ["Houston", "Phoenix"],
    pitch: "Mile-square arterials, cul-de-sacs within, and a strip mall at every corner.",
    expect: "freeways, cul-de-sacs, parking lots",
    charter: "freeways and cul-de-sacs",
    settings: settings(0.7, 0.1, 0.95, 0.85, 250, 4500),
  },
];

export function getGrowthStory(id: GrowthStoryId): GrowthStory {
  const story = GROWTH_STORIES.find((s) => s.id === id);
  if (!story) throw new Error(`Unknown growth story: ${id}`);
  return story;
}

/** Caveat word label for the Density slider (sprawl_compact). */
export function densityWord(sprawlCompact: number): string {
  if (sprawlCompact < 0.25) return "sprawling";
  if (sprawlCompact < 0.5) return "roomy";
  if (sprawlCompact < 0.75) return "snug";
  return "packed";
}

/**
 * Caveat word label for the Transit slider. The slider shows transit-ness,
 * i.e. 1 - transit_car, so higher means more trams.
 */
export function transitWord(transitCar: number): string {
  const transitness = 1 - transitCar;
  if (transitness >= 0.7) return "trams!";
  if (transitness >= 0.5) return "buses";
  if (transitness >= 0.3) return "mixed";
  return "cars";
}

/** Charter phrase for the transit level. */
export function transitCharter(transitCar: number): string {
  switch (transitWord(transitCar)) {
    case "trams!":
      return "trams on the main avenues";
    case "buses":
      return "buses on the main roads";
    case "mixed":
      return "a mix of transit and cars";
    default:
      return "a car in every driveway";
  }
}
