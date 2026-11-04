/**
 * Copy and option lists for the "Describe it" mode (CITY-660): example
 * prompts, surveying status lines, and the choices offered by each legend
 * row, with the refinement sentence each choice sends.
 */

import type { GeographicSetting, Relief, RiverCourse, WaterSide } from "../../api/types";
import { ARCHETYPES } from "./archetypes";
import { GROWTH_STORIES, type GrowthStoryId } from "./growthStories";

/** POST /worlds/brief prompt bounds. */
export const PROMPT_MIN = 3;
export const PROMPT_MAX = 600;
export const REFINEMENT_MAX = 300;

export const EXAMPLE_PROMPTS: readonly string[] = [
  "A fjord town with one road in",
  "Venice, but the lagoon is warm",
  "Two rivers meet below a bluff",
  "Chicago if the lake were an ocean",
  "A hilly port where a river spills into a sheltered bay",
  "A railroad town on flat prairie with a lazy creek",
  "An island fortress city with a crowded old harbor",
  "A desert crossroads that sprawled when the freeway came",
  "A delta city of canals that floods every spring",
  "A peninsula capital with grand boulevards",
  "A lakeside town of streetcars and front porches",
  "A medieval hill town above a winding river",
];

/** Rotating Caveat lines while the surveyor works. */
export const SURVEY_LINES: readonly string[] = [
  "measuring the tide…",
  "pacing out blocks…",
  "asking the fishermen…",
  "naming the creek…",
  "sharpening the pencil…",
  "counting the hills…",
  "checking which way the river runs…",
  "squinting at the horizon…",
];

export function shuffled<T>(items: readonly T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export type LegendField = "land" | "water" | "river" | "ground" | "streets";

export interface LegendOption {
  value: string;
  label: string;
  /** Sentence sent to the API as the refinement. */
  refinement: string;
}

const WATER_LABELS: Record<WaterSide, string> = {
  north: "north",
  north_east: "north-east",
  east: "east",
  south_east: "south-east",
  south: "south",
  south_west: "south-west",
  west: "west",
  north_west: "north-west",
  all_around: "all around",
  none: "no open water",
};

const RIVER_LABELS: Record<RiverCourse, string> = {
  none: "no river",
  straight: "straight",
  meandering: "meandering",
  braided: "braided",
};

const RELIEF_LABELS: Record<Relief, string> = {
  flat: "flat",
  rolling: "rolling",
  hilly: "hilly",
  mountainous: "mountainous",
};

/** The options each legend row offers, in display order. */
export const LEGEND_OPTIONS: Record<LegendField, LegendOption[]> = {
  land: ARCHETYPES.map((a) => ({
    value: a.value,
    label: a.label,
    refinement: `Change the land to ${a.label}`,
  })),
  water: (Object.keys(WATER_LABELS) as WaterSide[]).map((side) => ({
    value: side,
    label: WATER_LABELS[side],
    refinement:
      side === "none"
        ? "Remove the open water"
        : side === "all_around"
          ? "Put water all around"
          : `Change the water to the ${WATER_LABELS[side]}`,
  })),
  river: (Object.keys(RIVER_LABELS) as RiverCourse[]).map((course) => ({
    value: course,
    label: RIVER_LABELS[course],
    refinement: course === "none" ? "Remove the river" : `Make the river ${RIVER_LABELS[course]}`,
  })),
  ground: (Object.keys(RELIEF_LABELS) as Relief[]).map((relief) => ({
    value: relief,
    label: RELIEF_LABELS[relief],
    refinement: `Make the ground ${RELIEF_LABELS[relief]}`,
  })),
  streets: GROWTH_STORIES.map((s) => ({
    value: s.id,
    label: s.label,
    refinement: `Change the streets to ${s.label}`,
  })),
};

export function archetypeLabel(value: GeographicSetting): string {
  return ARCHETYPES.find((a) => a.value === value)?.label ?? value;
}

export function storyLabel(id: GrowthStoryId): string {
  return GROWTH_STORIES.find((s) => s.id === id)?.label ?? id;
}
