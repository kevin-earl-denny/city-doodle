/**
 * Step 1 of "Describe it": the player describes the land in their own words.
 */

import { useId, type KeyboardEvent } from "react";
import { FOCUS_RING, FlowColumns, StepHeading } from "../FlowLayout";
import { BigPencilIcon } from "../icons";
import { FieldNote, Plate } from "../Plate";
import { SurveyingOverlay } from "../Surveying";
import { PROMPT_MAX } from "../describeOptions";
import { BriefErrorNote, type BriefError } from "./BriefErrorNote";

/** Small tilts so the example chips look hand-placed. */
const CHIP_TILTS = [-1, 0.8, -0.6, 1.2];

interface PromptStepProps {
  prompt: string;
  onPromptChange: (prompt: string) => void;
  /** Survey the current prompt (Enter in the textarea). */
  onSurvey: () => void;
  examples: string[];
  surveying: boolean;
  error: BriefError | null;
  onTryDrawIt: () => void;
}

export function PromptStep({
  prompt,
  onPromptChange,
  onSurvey,
  examples,
  surveying,
  error,
  onTryDrawIt,
}: PromptStepProps) {
  const promptId = useId();
  const counterId = useId();

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter surveys; Shift+Enter is a newline. Ignore Enter while composing (IME).
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      onSurvey();
    }
  };

  return (
    <FlowColumns
      stepKey="prompt"
      left={
        <>
          <StepHeading title="Describe the land." aside="talk like a traveler — I'll draw like a surveyor" />

          <div className="flex flex-col gap-2.5">
            <div className="flex flex-col overflow-clip rounded-[6px] border-2 border-ink bg-white shadow-[4px_4px_0_var(--color-water)] focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-coast">
              <label htmlFor={promptId} className="sr-only">
                Describe the land
              </label>
              <textarea
                id={promptId}
                value={prompt}
                onChange={(e) => onPromptChange(e.target.value)}
                onKeyDown={handleKeyDown}
                maxLength={PROMPT_MAX}
                readOnly={surveying}
                aria-describedby={counterId}
                rows={4}
                placeholder="A hilly port where a river spills into a sheltered bay…"
                className="min-h-[150px] resize-none border-0 bg-[repeating-linear-gradient(transparent_0px,transparent_31px,var(--color-grid-line)_31px,var(--color-grid-line)_32px)] [background-attachment:local] [background-position:0_12px] px-5 pt-[18px] pb-2 font-display text-[20px] leading-8 text-ink caret-coast outline-none placeholder:text-pencil read-only:text-ink-soft"
              />
              <div className="flex items-center justify-between border-t-[1.5px] border-grid-line bg-paper py-2.5 pr-3 pl-5">
                <span id={counterId} className="font-plex text-[12px] leading-4 text-muted">
                  {prompt.length} / {PROMPT_MAX}
                  <span className="sr-only"> characters. Press Enter to survey, Shift+Enter for a new line.</span>
                </span>
                <span className="font-ui text-[13px] leading-4 text-muted" aria-hidden="true">
                  ⏎ to survey
                </span>
              </div>
            </div>
            {error && <BriefErrorNote error={error} onTryDrawIt={onTryDrawIt} />}
          </div>

          <div className="flex flex-col gap-2.5">
            <h3 className="m-0 font-plex text-[11px] leading-[14px] font-semibold tracking-[0.12em] text-coast">
              OR STEAL ONE
            </h3>
            <ul className="m-0 flex list-none flex-wrap gap-2.5 p-0">
              {examples.map((example, i) => (
                <li key={example}>
                  <button
                    type="button"
                    disabled={surveying}
                    onClick={() => onPromptChange(example)}
                    style={{ rotate: `${CHIP_TILTS[i % CHIP_TILTS.length]}deg` }}
                    className={`cursor-pointer rounded-full border-[1.5px] border-ink bg-white px-[14px] py-2 font-ui text-[14px] leading-[18px] font-medium text-ink transition-transform duration-150 hover:-translate-y-0.5 disabled:cursor-wait disabled:opacity-60 motion-reduce:transition-none ${FOCUS_RING}`}
                  >
                    {example}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </>
      }
      right={
        <>
          <Plate
            variant="empty"
            label={surveying ? "Surveying the land" : "Blank survey plate"}
            overlay={
              surveying ? (
                <SurveyingOverlay />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5" aria-hidden="true">
                  <BigPencilIcon />
                  <span className="font-hand text-[24px] leading-[30px] font-semibold text-muted">your map gets drawn here</span>
                </div>
              )
            }
          />
          <FieldNote title="What I listen for" aside="anything I can't draw yet, I'll tell you" loose>
            Where the water is, which way rivers run, how steep the ground gets, and which real cities it reminds you
            of. Streets and era are welcome too.
          </FieldNote>
        </>
      }
    />
  );
}
