/**
 * Step 2 of "Describe it": read the survey back as a map legend. Each row
 * can be swapped from a short list, and the refine bar takes free text;
 * both send a refinement of the current brief.
 */

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import type { WorldBriefResponse } from "../../../api/types";
import { FOCUS_RING, FlowColumns, StepHeading } from "../FlowLayout";
import {
  LEGEND_OPTIONS,
  REFINEMENT_MAX,
  archetypeLabel,
  storyLabel,
  type LegendField,
  type LegendOption,
} from "../describeOptions";
import { ArrowUpIcon, SparkleIcon, SwapIcon } from "../icons";
import { LandPlateArt } from "../illustrations";
import { FieldNote, Plate } from "../Plate";
import { SurveyingOverlay } from "../Surveying";
import { BriefErrorNote, type BriefError } from "./BriefErrorNote";

type RowId = LegendField | "feels_like";

interface LegendRow {
  id: RowId;
  label: string;
  value: string;
  /** Current enum value, for marking the checked option. */
  current?: string;
}

interface SurveyStepProps {
  result: WorldBriefResponse;
  /** A refinement is in flight: the plate shows the surveyor, rows are locked. */
  refining: boolean;
  error: BriefError | null;
  onRefine: (refinement: string) => void;
  refineText: string;
  onRefineTextChange: (text: string) => void;
  onEditInDrawIt: () => void;
  onTryDrawIt: () => void;
}

function legendRows({ brief }: WorldBriefResponse): LegendRow[] {
  const story = storyLabel(brief.growth_story);
  const streets = brief.legend.streets || story;
  return [
    { id: "land", label: "LAND", value: archetypeLabel(brief.archetype), current: brief.archetype },
    { id: "water", label: "WATER", value: brief.legend.water, current: brief.water_side },
    { id: "river", label: "RIVER", value: brief.legend.river, current: brief.river.course },
    { id: "ground", label: "GROUND", value: brief.legend.ground, current: brief.relief },
    {
      id: "streets",
      label: "STREETS",
      // Name the growth story too when the legend phrase doesn't.
      value: streets.toLowerCase().includes(story.toLowerCase()) ? streets : `${streets} (${story})`,
      current: brief.growth_story,
    },
    { id: "feels_like", label: "FEELS LIKE", value: brief.feels_like.join(" · ") },
  ];
}

export function SurveyStep({
  result,
  refining,
  error,
  onRefine,
  refineText,
  onRefineTextChange,
  onEditInDrawIt,
  onTryDrawIt,
}: SurveyStepProps) {
  const { brief, warnings } = result;
  const [openRow, setOpenRow] = useState<LegendField | null>(null);
  const refineRef = useRef<HTMLInputElement>(null);
  const refineId = useId();

  const sendRefinement = () => {
    const text = refineText.trim();
    if (text && !refining) onRefine(text);
  };

  const handleRowClick = (row: LegendRow) => {
    if (refining) return;
    if (row.id === "feels_like") {
      // No fixed list for this one: start a sentence in the refine bar.
      onRefineTextChange("Make it feel more like ");
      refineRef.current?.focus();
      return;
    }
    setOpenRow((open) => (open === row.id ? null : (row.id as LegendField)));
  };

  const unsupported = brief.unsupported.map((item) => `“${item}” noted, but I can't draw that yet`);

  return (
    <FlowColumns
      stepKey="survey"
      leftGap="tight"
      left={
        <>
          <StepHeading title="Here's your survey." aside="tap anything that's off and I'll redraw it" />

          <ul className="m-0 list-none border-y-[1.5px] border-ink p-0" aria-label="Survey legend">
            {legendRows(result).map((row) => (
              <li key={row.id} className="relative border-b border-card-edge">
                {/* aria-disabled, not disabled: the row keeps focus while the plate redraws. */}
                <button
                  type="button"
                  aria-disabled={refining || undefined}
                  onClick={() => handleRowClick(row)}
                  aria-haspopup={row.id === "feels_like" ? undefined : "menu"}
                  aria-expanded={row.id === "feels_like" ? undefined : openRow === row.id}
                  aria-label={`${row.label}: ${row.value}. Change`}
                  className={`flex w-full cursor-pointer items-center gap-4 bg-transparent px-1 py-[11px] text-left hover:bg-white/70 aria-disabled:cursor-wait ${FOCUS_RING}`}
                >
                  <span className="w-24 shrink-0 font-plex text-[11px] leading-[14px] font-semibold tracking-[0.12em] text-muted">
                    {row.label}
                  </span>
                  <span className="min-w-0 flex-1 font-display text-[18px] leading-[22px] font-medium text-ink italic underline decoration-pencil decoration-dashed decoration-1 underline-offset-[5px]">
                    {row.value || "—"}
                  </span>
                  <SwapIcon />
                </button>
                {openRow === row.id && (
                  <OptionMenu
                    label={row.label}
                    options={LEGEND_OPTIONS[row.id as LegendField]}
                    current={row.current}
                    onPick={(option, menu) => {
                      // Hand focus back to the row before the menu unmounts.
                      (menu.previousElementSibling as HTMLElement | null)?.focus();
                      setOpenRow(null);
                      if (option.value !== row.current) onRefine(option.refinement);
                    }}
                    onClose={() => setOpenRow(null)}
                  />
                )}
              </li>
            ))}
          </ul>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-3 rounded-full border-[1.5px] border-contour bg-white py-2.5 pr-2.5 pl-4 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-coast">
              <SparkleIcon />
              <label htmlFor={refineId} className="sr-only">
                Anything to change?
              </label>
              <input
                ref={refineRef}
                id={refineId}
                type="text"
                value={refineText}
                onChange={(e) => onRefineTextChange(e.target.value)}
                onKeyDown={(e) => {
                  // An Enter that confirms an IME composition (CJK input) is not a submit.
                  if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                    // Don't submit the flow's form; this sends a refinement.
                    e.preventDefault();
                    sendRefinement();
                  }
                }}
                maxLength={REFINEMENT_MAX}
                readOnly={refining}
                autoComplete="off"
                placeholder={'Anything to change? "Put the river on the east side"'}
                className="min-w-0 flex-1 border-0 bg-transparent p-0 font-ui text-[15px] leading-[18px] text-ink outline-none placeholder:text-[#8a836f]"
              />
              <button
                type="button"
                onClick={sendRefinement}
                aria-disabled={refining || !refineText.trim() || undefined}
                aria-label="Redraw with this change"
                className={`flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-full bg-ink aria-disabled:cursor-not-allowed ${FOCUS_RING}`}
              >
                <ArrowUpIcon />
              </button>
            </div>
            {error && <BriefErrorNote error={error} onTryDrawIt={onTryDrawIt} />}
            <p className="m-0 px-1 font-ui text-[13px] leading-4 text-body">
              Rather fiddle with it yourself?{" "}
              <button
                type="button"
                onClick={() => !refining && onEditInDrawIt()}
                aria-disabled={refining || undefined}
                className={`cursor-pointer rounded-sm bg-transparent p-0 font-semibold text-deep-water underline decoration-1 underline-offset-2 hover:text-ink aria-disabled:cursor-wait ${FOCUS_RING}`}
              >
                Edit in Draw it
              </button>
            </p>
          </div>
        </>
      }
      right={
        <>
          <Plate
            label={`Survey plate: ${archetypeLabel(brief.archetype)} with ${storyLabel(brief.growth_story)} streets`}
            overlay={refining ? <SurveyingOverlay overDrawing /> : undefined}
          >
            <LandPlateArt
              land={brief.archetype}
              story={brief.growth_story}
              placeName={brief.name}
              annotations={{ ground: brief.legend.ground, streets: brief.legend.streets }}
            />
          </Plate>
          <FieldNote
            title="Founding story"
            aside={unsupported}
            loose
            footnote={
              warnings.length > 0 && (
                <ul className="m-0 mt-1 list-none p-0 font-ui text-[12px] leading-4 text-muted">
                  {warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )
            }
          >
            {brief.founding_story}
          </FieldNote>
        </>
      }
    />
  );
}

interface OptionMenuProps {
  label: string;
  options: LegendOption[];
  current?: string;
  onPick: (option: LegendOption, menu: HTMLElement) => void;
  onClose: () => void;
}

/** Small popover of a legend row's choices. Arrow keys move, Esc closes. */
function OptionMenu({ label, options, current, onPick, onClose }: OptionMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const items = menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]');
    const checked = menuRef.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]');
    (checked ?? items?.[0])?.focus();
  }, []);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]') ?? []);
    const index = items.findIndex((el) => el === document.activeElement);
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
      (menuRef.current?.previousElementSibling as HTMLElement | null)?.focus();
    } else if (e.key === "ArrowDown" || e.key === "ArrowRight") {
      e.preventDefault();
      items[(index + 1) % items.length]?.focus();
    } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
      e.preventDefault();
      items[(index - 1 + items.length) % items.length]?.focus();
    }
  };

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label={`Change ${label.toLowerCase()}`}
      onKeyDown={handleKeyDown}
      // Safari on macOS doesn't focus buttons on click, so a mouse press would blur
      // the focused option with relatedTarget = null and close the menu before the
      // option's onClick runs. Keeping focus where it is lets the click land.
      onMouseDown={(e) => e.preventDefault()}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onClose();
      }}
      className="absolute top-[calc(100%-4px)] left-[116px] z-30 flex max-w-[440px] flex-wrap gap-1.5 rounded-[6px] border-[1.5px] border-ink bg-white p-2 shadow-[3px_3px_0_var(--color-ink)]"
    >
      {options.map((option) => {
        const checked = option.value === current;
        return (
          <button
            key={option.value}
            type="button"
            role="menuitemradio"
            aria-checked={checked}
            onClick={() => menuRef.current && onPick(option, menuRef.current)}
            className={`cursor-pointer rounded-full border-[1.5px] px-3 py-1 font-display text-[15px] leading-5 italic ${FOCUS_RING} ${
              checked ? "border-ink bg-water text-ink" : "border-card-edge bg-transparent text-ink hover:border-ink"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
