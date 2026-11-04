/**
 * Step 3 of "Draw it": name the city, check the survey number, found it.
 */

import { useEffect, useId, useState } from "react";
import type { GeographicSetting } from "../../../api/types";
import { getArchetype } from "../archetypes";
import { FOCUS_RING, FlowColumns, StepHeading } from "../FlowLayout";
import { densityWord, getGrowthStory, transitCharter, type GrowthSettings, type GrowthStoryId } from "../growthStories";
import { CheckIcon, CopyIcon, DiceThreeIcon } from "../icons";
import { LandPlateArt } from "../illustrations";
import { FieldNote, Plate } from "../Plate";

/** Small tilts so the name chips look stamped by hand. */
const CHIP_TILTS = [-2, 1.5, -1, 2];

interface NameStepProps {
  name: string;
  onNameChange: (name: string) => void;
  onReroll: () => void;
  suggestions: string[];
  seedText: string;
  onSeedChange: (seedText: string) => void;
  seedError: string | null;
  land: GeographicSetting;
  story: GrowthStoryId | null;
  values: GrowthSettings;
  error: string | null;
}

function charter(land: GeographicSetting, story: GrowthStoryId | null, values: GrowthSettings): string {
  const plan = story ? getGrowthStory(story).charter : "streets left to find their own way";
  return `A ${getArchetype(land).charterNoun} with ${plan}, ${values.block_size_meters} m blocks, ${densityWord(
    values.sprawl_compact,
  )} streets, and ${transitCharter(values.transit_car)}.`;
}

export function NameStep({
  name,
  onNameChange,
  onReroll,
  suggestions,
  seedText,
  onSeedChange,
  seedError,
  land,
  story,
  values,
  error,
}: NameStepProps) {
  const nameId = useId();
  const seedId = useId();
  const seedHintId = useId();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(t);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(seedText);
      setCopied(true);
    } catch {
      // Clipboard can be unavailable (insecure context, denied permission); the number stays selectable.
    }
  };

  return (
    <FlowColumns
      stepKey="name"
      leftGap="loose"
      left={
        <>
          <StepHeading title="Name it, and it's yours." aside="every name on a map was somebody's idea once…" />

          <div className="flex items-end gap-[14px] border-b-[3px] border-ink pt-2 pb-2.5">
            <label htmlFor={nameId} className="sr-only">
              City name
            </label>
            <input
              id={nameId}
              type="text"
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              maxLength={60}
              autoComplete="off"
              spellCheck={false}
              className="min-w-0 flex-1 border-0 bg-transparent p-0 font-display text-[clamp(36px,6vw,60px)] leading-[66px] font-bold tracking-[-0.02em] text-ink italic caret-coast outline-none placeholder:text-contour"
              placeholder="Unnamed"
            />
            <button
              type="button"
              onClick={onReroll}
              aria-label="Roll a new name"
              title="Roll a new name"
              className={`mb-1 flex size-12 shrink-0 rotate-[8deg] cursor-pointer items-center justify-center rounded-[10px] border-2 border-ink bg-white shadow-[3px_3px_0_var(--color-ink)] transition-[rotate] duration-150 hover:rotate-[-6deg] motion-reduce:transition-none ${FOCUS_RING}`}
            >
              <DiceThreeIcon />
            </button>
          </div>

          <div className="flex flex-col gap-2.5">
            <h3 className="m-0 font-plex text-[11px] leading-[14px] font-semibold tracking-[0.12em] text-coast">
              OTHER NAMES ON THE SURVEYOR'S LIST
            </h3>
            <ul className="m-0 flex list-none flex-wrap gap-2.5 p-0">
              {suggestions.map((suggestion, i) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    onClick={() => onNameChange(suggestion)}
                    style={{ rotate: `${CHIP_TILTS[i % CHIP_TILTS.length]}deg` }}
                    className={`cursor-pointer rounded-[4px] border-[1.5px] border-deep-water bg-transparent px-[14px] py-1.5 font-display text-[17px] leading-[22px] font-semibold text-deep-water italic transition-transform duration-150 hover:-translate-y-0.5 hover:bg-white motion-reduce:transition-none ${FOCUS_RING}`}
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-3 rounded-[6px] bg-parchment-dim px-4 py-3">
              <label
                htmlFor={seedId}
                className="flex items-center font-plex text-[13px] leading-4 font-semibold tracking-[0.06em] text-ink"
              >
                SURVEY Nº&nbsp;
                <input
                  id={seedId}
                  type="text"
                  inputMode="numeric"
                  value={seedText}
                  onChange={(e) => onSeedChange(e.target.value.replace(/\D/g, ""))}
                  aria-invalid={seedError ? true : undefined}
                  aria-describedby={seedHintId}
                  style={{ width: `${Math.max(seedText.length, 1) * 1.06 + 0.4}ch` }}
                  className="h-4 border-0 border-b border-dashed border-pencil bg-transparent p-0 font-plex text-[13px] leading-4 font-semibold tracking-[0.06em] text-ink outline-none focus-visible:border-coast"
                />
              </label>
              <span id={seedHintId} className="min-w-[12rem] flex-1 font-ui text-[13px] leading-4 text-body">
                Same number + same choices = the same land, every time.
              </span>
              <button
                type="button"
                onClick={handleCopy}
                aria-label={copied ? "Survey number copied" : "Copy survey number"}
                title="Copy survey number"
                className={`-m-1 flex size-6 cursor-pointer items-center justify-center rounded-[4px] bg-transparent hover:bg-paper ${FOCUS_RING}`}
              >
                {copied ? <CheckIcon color="var(--color-coast)" /> : <CopyIcon />}
              </button>
              <span className="sr-only" role="status">
                {copied ? "Copied" : ""}
              </span>
            </div>
            {seedError && (
              <p className="m-0 font-ui text-[13px] leading-4 text-red-700" role="alert">
                {seedError}
              </p>
            )}
          </div>

          {error && (
            <p className="m-0 rounded-[6px] border-[1.5px] border-red-700/40 bg-red-50 px-4 py-3 font-ui text-[14px] leading-5 text-red-800" role="alert">
              {error}
            </p>
          )}
        </>
      }
      right={
        <>
          <Plate crop="short" label={`Survey plate for ${name || "your city"}`}>
            <LandPlateArt land={land} story={story} placeName={name} />
          </Plate>
          <FieldNote title="The charter" aside="you can change all of this later">
            {charter(land, story, values)}
          </FieldNote>
        </>
      }
    />
  );
}
