/**
 * Land archetypes for step 1 of the "Found a city" flow (CITY-658).
 *
 * Maps each geographic_setting to its card label, example cities and the
 * "WHY HERE?" note. UI copy calls `inland` "Plains"; the value stays `inland`.
 */

import type { GeographicSetting } from "../../api/types";

export interface Archetype {
  value: GeographicSetting;
  label: string;
  examples: string[];
  /** 1–2 sentences for "WHY HERE?". */
  whyHere: string;
  /** Caveat line, rendered as "expect: …". */
  expect: string;
  /** Where the town started, e.g. "the docks". Used in "THE STORY SO FAR". */
  heart: string;
  /** Charter noun, e.g. "bay-and-harbor town". */
  charterNoun: string;
}

/** Display order of the 4×2 grid. */
export const ARCHETYPES: readonly Archetype[] = [
  {
    value: "coastal",
    label: "Coastal",
    examples: ["Rio", "Tel Aviv", "Miami"],
    whyHere:
      "An open-sea port puts the whole world one voyage away. Ships unload at the harbor, and the rest of the shore turns into beaches and boardwalks.",
    expect: "a busy port, beaches, a seawall",
    heart: "the port",
    charterNoun: "seaside town",
  },
  {
    value: "bay_harbor",
    label: "Bay & Harbor",
    examples: ["Sydney", "Halifax"],
    whyHere:
      "A sheltered bay lets ships unload out of the wind. Docks come first, then warehouses, then a downtown climbing the hills behind them.",
    expect: "piers, a ferry, steep streets",
    heart: "the docks",
    charterNoun: "bay-and-harbor town",
  },
  {
    value: "river_valley",
    label: "River Valley",
    examples: ["Paris", "Budapest"],
    whyHere:
      "Towns start where a river can be forded, and later bridged. The floodplain's rich soil feeds the city as it spreads along both banks.",
    expect: "bridges, river quays, a market by the ford",
    heart: "the old ford",
    charterNoun: "river-valley town",
  },
  {
    value: "lakefront",
    label: "Lakefront",
    examples: ["Chicago", "Geneva"],
    whyHere:
      "A big freshwater lake is a shipping lane and a water supply in one. Freight crowds the harbor, and the rest of the shore becomes a long promenade.",
    expect: "grain piers, a lakeshore promenade",
    heart: "the harbor",
    charterNoun: "lakefront town",
  },
  {
    value: "inland",
    label: "Plains",
    examples: ["Dallas", "Calgary"],
    whyHere:
      "On open ground, cities start where trails cross and the railroad stops. Nothing hems them in, so they have room to sprawl in every direction.",
    expect: "a rail depot, crossroads, room to grow",
    heart: "the crossroads",
    charterNoun: "prairie town",
  },
  {
    value: "island",
    label: "Island",
    examples: ["Manhattan", "Malta"],
    whyHere:
      "Water on every side makes an island easy to defend and hard to outgrow. With no room to spread out, the city builds dense, then builds up.",
    expect: "tight blocks, towers, ferries and bridges",
    heart: "the ferry landing",
    charterNoun: "island town",
  },
  {
    value: "peninsula",
    label: "Peninsula",
    examples: ["Boston", "Istanbul"],
    whyHere:
      "Water on three sides and a narrow neck of land to guard. The old town fills the tip, and everything else squeezes in through the neck.",
    expect: "harbors on both shores, one road in",
    heart: "the tip",
    charterNoun: "peninsula town",
  },
  {
    value: "delta",
    label: "River Delta",
    examples: ["New Orleans", "Dhaka"],
    whyHere:
      "Where a river meets the sea, the soil is rich and every cargo passes through. The catch: the land sits low, and floods are part of life.",
    expect: "levees, canals, busy wharves",
    heart: "the river mouth",
    charterNoun: "delta town",
  },
];

export function getArchetype(value: GeographicSetting): Archetype {
  const archetype = ARCHETYPES.find((a) => a.value === value);
  if (!archetype) throw new Error(`Unknown geographic setting: ${value}`);
  return archetype;
}
