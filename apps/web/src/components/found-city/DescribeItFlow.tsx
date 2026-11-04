/**
 * "Describe it" mode of the Found-a-city modal (CITY-660):
 * describe → read the survey (refine) → name & found.
 *
 * The brief endpoint turns the prompt into a WorldBrief plus compiled
 * WorldSettings. The settings go to create-world unchanged; the brief drives
 * the legend, the plate and the "Edit in Draw it" prefill.
 */

import { useMemo, useState } from "react";
import { ApiClientError, useWorldBrief } from "../../api";
import type { WorldBriefRequest, WorldBriefResponse } from "../../api/types";
import { generateCityName } from "../../utils";
import { EXAMPLE_PROMPTS, PROMPT_MIN, shuffled } from "./describeOptions";
import { FlowFooter, FlowForm, PillButton, PrimaryButton, RouteSteps } from "./FlowLayout";
import type { FoundCityModeProps } from "./FoundCityModal";
import { DiceFourIcon, PencilIcon } from "./icons";
import type { BriefError } from "./steps/BriefErrorNote";
import { NameStep } from "./steps/NameStep";
import { PromptStep } from "./steps/PromptStep";
import { SurveyStep } from "./steps/SurveyStep";

const STEP_LABELS = ["Describe", "Read the survey", "Found it"];

function toBriefError(err: unknown): BriefError {
  if (err instanceof ApiClientError) {
    // A 422 whose detail is a list is request validation, not a refusal. Its
    // messages are developer-facing, so swap in player copy.
    const body = err.detail as { detail?: unknown } | undefined;
    if (err.status === 422 && Array.isArray(body?.detail)) {
      return {
        message: "That survey got too tangled to tweak. Try describing the land again.",
        status: err.status,
      };
    }
    return { message: err.message, status: err.status };
  }
  if (err instanceof Error) return { message: err.message };
  return { message: "The surveyor couldn't read that. Please try again." };
}

export function DescribeItFlow({
  seedText,
  onSeedChange,
  seedError,
  onClose,
  onFound,
  isFounding,
  foundError,
  panelId,
  tabId,
  onSwitchToDraw,
}: FoundCityModeProps) {
  const [step, setStep] = useState(1);
  const [reached, setReached] = useState(1);
  const [prompt, setPrompt] = useState("");
  const [examples] = useState(() => shuffled(EXAMPLE_PROMPTS).slice(0, 4));
  /** The prompt the current result was surveyed from; re-sent with refinements. */
  const [surveyedPrompt, setSurveyedPrompt] = useState("");
  const [result, setResult] = useState<WorldBriefResponse | null>(null);
  const [error, setError] = useState<BriefError | null>(null);
  const [refineText, setRefineText] = useState("");
  const [name, setName] = useState("");
  const brief = useWorldBrief();
  const busy = brief.isPending;
  // Which kind of request is in flight decides where the surveyor shows up.
  const [pendingKind, setPendingKind] = useState<"survey" | "refine" | null>(null);

  const goTo = (n: number) => {
    setStep(n);
    setReached((r) => Math.max(r, n));
  };

  const request = async (body: WorldBriefRequest, kind: "survey" | "refine") => {
    setError(null);
    setPendingKind(kind);
    try {
      const response = await brief.mutateAsync(body);
      setResult(response);
      setSurveyedPrompt(body.prompt);
      setName(response.brief.name);
      if (kind === "refine") setRefineText("");
      // A fresh survey invalidates anything past the legend.
      setStep(2);
      setReached(2);
    } catch (err) {
      setError(toBriefError(err));
    } finally {
      setPendingKind(null);
    }
  };

  const survey = (text = prompt) => {
    if (busy) return;
    const trimmed = text.trim();
    if (trimmed.length < PROMPT_MIN) {
      setError({ message: "Tell me a little about the land first: a few words is plenty." });
      return;
    }
    void request({ prompt: trimmed }, "survey");
  };

  const refine = (refinement: string) => {
    if (!result || busy) return;
    void request({ prompt: surveyedPrompt, previous: result.brief, refinement }, "refine");
  };

  const rollPrompt = () => {
    const next = shuffled(EXAMPLE_PROMPTS).find((p) => p !== prompt) ?? EXAMPLE_PROMPTS[0];
    setPrompt(next);
    survey(next);
  };

  const editInDrawIt = () => {
    if (!result) return;
    const { settings } = result;
    onSwitchToDraw({
      land: result.brief.archetype,
      story: result.brief.growth_story,
      settings: {
        grid_organic: settings.grid_organic,
        sprawl_compact: settings.sprawl_compact,
        transit_car: settings.transit_car,
        historic_modern: settings.historic_modern,
        block_size_meters: settings.block_size_meters,
        district_size_meters: settings.district_size_meters,
      },
      name: name.trim() || result.brief.name,
    });
  };

  const suggestions = useMemo(
    () => (result ? result.brief.name_suggestions.filter((n) => n !== name).slice(0, 4) : []),
    [result, name],
  );

  const handleSubmit = () => {
    if (busy) return;
    if (step === 1) survey();
    else if (step === 2 && result) goTo(3);
    else if (step === 3 && result) void onFound(name, result.settings);
  };

  const trimmedName = name.trim();
  const surveying = busy && pendingKind === "survey";
  const refining = busy && pendingKind === "refine";

  const primary =
    step === 1 ? (
      <PrimaryButton pending={surveying} pendingLabel="Surveying…">
        Survey it
      </PrimaryButton>
    ) : step === 2 ? (
      <PrimaryButton>Next: name it</PrimaryButton>
    ) : (
      <PrimaryButton pending={isFounding} size="large">
        {`Found ${trimmedName || "it"}`}
      </PrimaryButton>
    );

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
              <PillButton variant="dashed" icon={<DiceFourIcon />} onClick={rollPrompt} disabled={busy}>
                Roll a prompt
              </PillButton>
            ) : step === 2 ? (
              <PillButton icon={<PencilIcon color="var(--color-ink)" />} onClick={() => setStep(1)} disabled={busy}>
                Edit prompt
              </PillButton>
            ) : (
              <PillButton onClick={() => setStep(2)} disabled={isFounding}>
                Back
              </PillButton>
            )
          }
          primary={primary}
        />
      }
    >
      <RouteSteps
        labels={STEP_LABELS}
        current={step}
        reached={busy || isFounding ? step : reached}
        onSelect={setStep}
      />
      {step === 1 && (
        <PromptStep
          prompt={prompt}
          onPromptChange={(p) => {
            setPrompt(p);
            if (error) setError(null);
          }}
          onSurvey={() => survey()}
          examples={examples}
          surveying={surveying}
          error={error}
          onTryDrawIt={() => onSwitchToDraw()}
        />
      )}
      {step === 2 && result && (
        <SurveyStep
          result={result}
          refining={refining}
          error={error}
          onRefine={refine}
          refineText={refineText}
          onRefineTextChange={setRefineText}
          onEditInDrawIt={editInDrawIt}
          onTryDrawIt={() => onSwitchToDraw()}
        />
      )}
      {step === 3 && result && (
        <NameStep
          name={name}
          onNameChange={setName}
          onReroll={() => setName(generateCityName({ seed: Date.now(), geographicSetting: result.brief.archetype }))}
          suggestions={suggestions}
          seedText={seedText}
          onSeedChange={onSeedChange}
          seedError={seedError}
          land={result.brief.archetype}
          story={result.brief.growth_story}
          values={result.settings}
          error={foundError}
        />
      )}
    </FlowForm>
  );
}
