/**
 * Step 2 of "Draw it": pick a growth story, then fine-tune it.
 */

import { useId } from "react";
import type { GeographicSetting } from "../../../api/types";
import { getArchetype } from "../archetypes";
import { CardRadioGroup, FlowColumns, StepHeading } from "../FlowLayout";
import {
  GROWTH_STORIES,
  densityWord,
  getGrowthStory,
  transitWord,
  type GrowthSettings,
  type GrowthStoryId,
} from "../growthStories";
import { LandPlateArt, StoryThumbnail } from "../illustrations";
import { FieldNote, Plate } from "../Plate";
import { ScaleBarSlider } from "../ScaleBarSlider";

const STORY_OPTIONS = GROWTH_STORIES.map((s) => s.id);

/** The settings the FINE-TUNE sliders control. */
export type TweakableSetting = "block_size_meters" | "sprawl_compact" | "transit_car";

interface GrowthStepProps {
  land: GeographicSetting;
  placeName: string;
  story: GrowthStoryId | null;
  onStoryChange: (story: GrowthStoryId) => void;
  /** True once a slider has moved away from the story's values. */
  tweaked: boolean;
  values: GrowthSettings;
  onTweak: (setting: TweakableSetting, value: number) => void;
}

function storySoFar(placeName: string, land: GeographicSetting, story: GrowthStoryId | null): string {
  const heart = getArchetype(land).heart;
  if (!story) {
    return `${placeName} is still a spot on the map near ${heart}. Pick how it grew, or skip ahead and let the streets work themselves out.`;
  }
  const s = getGrowthStory(story);
  return `${placeName} started at ${heart}. ${s.pitch ?? s.blurb}`;
}

export function GrowthStep({ land, placeName, story, onStoryChange, tweaked, values, onTweak }: GrowthStepProps) {
  const title = `How did ${placeName} grow?`;
  const selected = story ? getGrowthStory(story) : null;
  const fineTuneId = useId();

  return (
    <FlowColumns
      stepKey="growth"
      left={
        <>
          <StepHeading title={title} aside="streets remember the century they were drawn in…" />
          <CardRadioGroup
            label="How it grew"
            options={STORY_OPTIONS}
            value={story}
            onChange={onStoryChange}
            className="grid grid-cols-2 gap-3 min-[900px]:grid-cols-3"
            tilt={1}
            padding={["gap-1.5 p-2.5", "gap-1.5 p-[9.5px]"]}
            optionLabel={(id) => {
              const s = getGrowthStory(id);
              return `${s.label}${id === story && tweaked ? " (tweaked)" : ""}: ${s.blurb} ${s.examples.join(", ")}.`;
            }}
            renderCard={(id, checked) => {
              const s = getGrowthStory(id);
              return (
                <>
                  <StoryThumbnail id={id} className="block aspect-[167/64] max-h-20 w-full min-[900px]:max-h-none" />
                  <span className="font-display text-[17px] leading-[22px] font-bold text-ink">{s.label}</span>
                  <span className="font-ui text-[13px] leading-[18px] text-body">
                    {s.blurb} {s.examples.join(", ")}.
                  </span>
                  {checked && tweaked && (
                    <span
                      aria-hidden="true"
                      className="absolute right-2 bottom-1 rotate-[-4deg] font-hand text-[18px] leading-[22px] font-semibold text-coast"
                    >
                      tweaked
                    </span>
                  )}
                </>
              );
            }}
          />
        </>
      }
      right={
        <>
          <Plate crop="short" label={`Survey plate: ${getArchetype(land).label}${selected ? ` with ${selected.label} streets` : ""}`}>
            <LandPlateArt land={land} story={story} placeName={placeName} />
          </Plate>
          <FieldNote title="The story so far" aside={selected ? `expect: ${selected.expect}` : undefined}>
            {storySoFar(placeName, land, story)}
          </FieldNote>
          <div
            role="group"
            aria-labelledby={fineTuneId}
            className="flex flex-col gap-3 rounded-[6px] border-[1.5px] border-dashed border-contour px-4 py-[14px]"
          >
            <h3 id={fineTuneId} className="m-0 font-plex text-[11px] leading-[14px] font-semibold tracking-[0.12em] text-coast">
              FINE-TUNE
            </h3>
            <ScaleBarSlider
              label="Blocks"
              min={50}
              max={300}
              step={5}
              value={values.block_size_meters}
              onChange={(v) => onTweak("block_size_meters", v)}
              valueText={`${values.block_size_meters} m`}
            />
            <ScaleBarSlider
              label="Density"
              min={0}
              max={1}
              step={0.05}
              value={values.sprawl_compact}
              onChange={(v) => onTweak("sprawl_compact", v)}
              valueText={densityWord(values.sprawl_compact)}
              valueStyle="hand"
            />
            {/* The slider reads as "how much transit", so it shows 1 - transit_car. */}
            <ScaleBarSlider
              label="Transit"
              min={0}
              max={1}
              step={0.05}
              value={Math.round((1 - values.transit_car) * 100) / 100}
              onChange={(v) => onTweak("transit_car", Math.round((1 - v) * 100) / 100)}
              valueText={transitWord(values.transit_car)}
              valueStyle="hand"
            />
          </div>
        </>
      }
    />
  );
}
