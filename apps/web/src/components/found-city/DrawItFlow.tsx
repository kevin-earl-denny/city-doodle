/**
 * "Draw it" mode of the Found-a-city modal: land → growth story → name.
 */

import { useMemo, useState } from "react";
import { DEFAULT_WORLD_SETTINGS, type GeographicSetting, type WorldSettings } from "../../api/types";
import { generateCityName, generateCityNameSuggestions } from "../../utils";
import { ARCHETYPES } from "./archetypes";
import { FlowFooter, FlowForm, PillButton, PrimaryButton, RouteSteps } from "./FlowLayout";
import { GROWTH_STORIES, getGrowthStory, type GrowthSettings, type GrowthStoryId } from "./growthStories";
import { DiceFourIcon } from "./icons";
import type { FoundCityModeProps } from "./FoundCityModal";
import { GrowthStep, type TweakableSetting } from "./steps/GrowthStep";
import { LandStep } from "./steps/LandStep";
import { NameStep } from "./steps/NameStep";

const STEP_LABELS = ["The land", "How it grew", "Name & found it"];

/** Street settings used until a growth story is picked. */
const DEFAULT_GROWTH: GrowthSettings = {
  grid_organic: DEFAULT_WORLD_SETTINGS.grid_organic,
  sprawl_compact: DEFAULT_WORLD_SETTINGS.sprawl_compact,
  transit_car: DEFAULT_WORLD_SETTINGS.transit_car,
  historic_modern: DEFAULT_WORLD_SETTINGS.historic_modern,
  block_size_meters: DEFAULT_WORLD_SETTINGS.block_size_meters,
  district_size_meters: DEFAULT_WORLD_SETTINGS.district_size_meters,
};

/** Prefill for Draw it, e.g. from a Describe-it brief ("Edit in Draw it"). */
export interface DrawItInitial {
  land: GeographicSetting;
  story: GrowthStoryId;
  /** Street settings; any that differ from the story show as tweaks. */
  settings: GrowthSettings;
  name: string;
}

function pick<T>(items: readonly T[]): T {
  return items[Math.floor(Math.random() * items.length)];
}

/** The fields of `settings` that differ from `base`. */
function diffSettings(settings: GrowthSettings, base: GrowthSettings): Partial<GrowthSettings> {
  const out: Partial<GrowthSettings> = {};
  for (const key of Object.keys(base) as (keyof GrowthSettings)[]) {
    if (settings[key] !== base[key]) out[key] = settings[key];
  }
  return out;
}

function newName(land: GeographicSetting): string {
  return generateCityName({ seed: Date.now(), geographicSetting: land });
}

export function DrawItFlow({
  seedText,
  onSeedChange,
  seedError,
  onClose,
  onFound,
  isFounding,
  foundError,
  panelId,
  tabId,
  initial,
}: FoundCityModeProps & { initial?: DrawItInitial }) {
  // A prefilled flow opens on step 2 with every step reachable.
  const [step, setStep] = useState(initial ? 2 : 1);
  const [reached, setReached] = useState(initial ? 3 : 1);
  const [land, setLand] = useState<GeographicSetting>(initial?.land ?? DEFAULT_WORLD_SETTINGS.geographic_setting);
  const [story, setStory] = useState<GrowthStoryId | null>(initial?.story ?? null);
  const [tweaks, setTweaks] = useState<Partial<GrowthSettings>>(() =>
    initial ? diffSettings(initial.settings, getGrowthStory(initial.story).settings) : {},
  );
  const [name, setName] = useState(() => initial?.name ?? newName(DEFAULT_WORLD_SETTINGS.geographic_setting));
  const [suggestionSeed, setSuggestionSeed] = useState(() => Date.now());

  const storyValues = story ? getGrowthStory(story).settings : DEFAULT_GROWTH;
  const values: GrowthSettings = { ...storyValues, ...tweaks };
  const tweaked =
    story !== null && (Object.keys(tweaks) as (keyof GrowthSettings)[]).some((k) => tweaks[k] !== storyValues[k]);

  const suggestions = useMemo(
    () =>
      generateCityNameSuggestions(6, suggestionSeed, land)
        .filter((n) => n !== name)
        .slice(0, 4),
    [suggestionSeed, land, name],
  );

  const goTo = (n: number) => {
    setStep(n);
    setReached((r) => Math.max(r, n));
  };

  const handleLandChange = (next: GeographicSetting) => {
    if (next === land) return;
    setLand(next);
    // CITY-544: the name follows the geography.
    setName(newName(next));
    setSuggestionSeed(Date.now());
  };

  const handleStoryChange = (next: GrowthStoryId) => {
    setStory(next);
    setTweaks({});
  };

  const handleTweak = (setting: TweakableSetting, value: number) => {
    setTweaks((t) => ({ ...t, [setting]: value }));
  };

  const handleReroll = () => {
    setName(newName(land));
    setSuggestionSeed(Date.now());
  };

  const handleSurprise = () => {
    const nextLand = pick(ARCHETYPES).value;
    setLand(nextLand);
    setStory(pick(GROWTH_STORIES).id);
    setTweaks({});
    setName(newName(nextLand));
    setSuggestionSeed(Date.now());
    goTo(3);
  };

  const handleSubmit = () => {
    if (step < 3) {
      goTo(step + 1);
      return;
    }
    const settings: Partial<WorldSettings> = { geographic_setting: land, ...values };
    void onFound(name, settings);
  };

  const trimmedName = name.trim();
  const primaryLabel = step === 1 ? "Next: how it grew" : step === 2 ? "Next: name it" : `Found ${trimmedName || "it"}`;

  return (
    <FlowForm
      panelId={panelId}
      tabId={tabId}
      step={step}
      onSubmit={handleSubmit}
      footer={
        <FlowFooter
          onCancel={onClose}
          cancelDisabled={isFounding}
          left={
            step === 1 ? (
              <PillButton variant="dashed" icon={<DiceFourIcon />} onClick={handleSurprise}>
                Surprise me
              </PillButton>
            ) : (
              <PillButton onClick={() => setStep(step - 1)} disabled={isFounding}>
                Back
              </PillButton>
            )
          }
          primary={
            <PrimaryButton pending={isFounding} size={step === 3 ? "large" : "normal"}>
              {primaryLabel}
            </PrimaryButton>
          }
        />
      }
    >
      <RouteSteps labels={STEP_LABELS} current={step} reached={isFounding ? step : reached} onSelect={setStep} />
      {step === 1 && (
        <LandStep
          land={land}
          onLandChange={handleLandChange}
          placeName={name}
          districtSizeMeters={values.district_size_meters}
        />
      )}
      {step === 2 && (
        <GrowthStep
          land={land}
          placeName={trimmedName || "your city"}
          story={story}
          onStoryChange={handleStoryChange}
          tweaked={tweaked}
          values={values}
          onTweak={handleTweak}
        />
      )}
      {step === 3 && (
        <NameStep
          name={name}
          onNameChange={setName}
          onReroll={handleReroll}
          suggestions={suggestions}
          seedText={seedText}
          onSeedChange={onSeedChange}
          seedError={seedError}
          land={land}
          story={story}
          values={values}
          error={foundError}
        />
      )}
    </FlowForm>
  );
}
