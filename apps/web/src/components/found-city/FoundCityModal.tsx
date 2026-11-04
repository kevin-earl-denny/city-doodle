/**
 * "Found a city" modal (CITY-658): the shell around the city-creation modes.
 *
 * The shell owns the header (wordmark, survey number, mode tabs, close),
 * the survey number (seed), focus handling and the create-world call.
 * Each mode is a component that receives FoundCityModeProps and renders its
 * own route steps, body and footer with the pieces in FlowLayout.tsx.
 */

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ComponentType,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useCreateWorld } from "../../api";
import type { WorldSettings } from "../../api/types";
import { DrawItFlow } from "./DrawItFlow";
import { FOCUS_RING } from "./FlowLayout";
import { CloseIcon, PencilIcon, SparkleIcon } from "./icons";

/** What every mode gets from the shell. */
export interface FoundCityModeProps {
  /** Survey number as typed (digits only); the seed sent to the API. */
  seedText: string;
  onSeedChange: (seedText: string) => void;
  /** Validation message for seedText, if invalid. */
  seedError: string | null;
  onClose: () => void;
  /** Create the world. The shell validates, calls the API and reports errors. */
  onFound: (name: string, settings: Partial<WorldSettings>) => Promise<void>;
  isFounding: boolean;
  foundError: string | null;
  /** Ids linking the mode's panel to its tab. */
  panelId: string;
  tabId: string;
}

type ModeId = "draw" | "describe";

interface ModeDef {
  id: ModeId;
  label: string;
  icon: (active: boolean) => ReactNode;
  /** Undefined while the mode is not built yet: the tab shows "Coming soon". */
  component?: ComponentType<FoundCityModeProps>;
}

const MODES: ModeDef[] = [
  {
    id: "draw",
    label: "Draw it",
    icon: (active) => <PencilIcon color={active ? "var(--color-paper)" : "var(--color-ink)"} />,
    component: DrawItFlow,
  },
  {
    id: "describe",
    label: "Describe it",
    icon: (active) => <SparkleIcon color={active ? "var(--color-water)" : "var(--color-coast)"} />,
  },
];

const MAX_SEED = 2_147_483_647;

function randomSeed(): number {
  return 10_000 + Math.floor(Math.random() * 90_000);
}

function seedProblem(seedText: string): string | null {
  if (!seedText) return "Every survey needs a number.";
  if (!/^\d+$/.test(seedText) || Number(seedText) > MAX_SEED) {
    return `Survey numbers are whole numbers up to ${MAX_SEED.toLocaleString("en-US")}.`;
  }
  return null;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface FoundCityModalProps {
  onClose: () => void;
  onCreated: (worldId: string) => void;
}

export function FoundCityModal({ onClose, onCreated }: FoundCityModalProps) {
  const [mode, setMode] = useState<ModeId>("draw");
  const [seedText, setSeedText] = useState(() => String(randomSeed()));
  const [foundError, setFoundError] = useState<string | null>(null);
  const createWorld = useCreateWorld();
  const isFounding = createWorld.isPending;

  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const baseId = useId();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const close = useCallback(() => {
    if (!isFounding) onClose();
  }, [isFounding, onClose]);

  // Focus the dialog on open and give focus back to the opener on close.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    return () => opener?.focus?.();
  }, []);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== "Tab" || !dialogRef.current) return;
    // Trap focus inside the dialog.
    const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement,
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || active === dialogRef.current)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const handleTabKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const index = tabRefs.current.findIndex((el) => el === document.activeElement);
    const next = (index + (e.key === "ArrowRight" ? 1 : -1) + MODES.length) % MODES.length;
    tabRefs.current[next]?.focus();
  };

  const handleFound = async (name: string, settings: Partial<WorldSettings>) => {
    setFoundError(null);
    const trimmed = name.trim();
    if (!trimmed) {
      setFoundError("Every city needs a name. Try the dice.");
      return;
    }
    const problem = seedProblem(seedText);
    if (problem) {
      setFoundError(problem);
      return;
    }
    try {
      const world = await createWorld.mutateAsync({ name: trimmed, seed: Number(seedText), settings });
      onCreated(world.id);
    } catch (err) {
      setFoundError(err instanceof Error ? err.message : "Failed to found the city. Please try again.");
    }
  };

  const active = MODES.find((m) => m.id === mode) ?? MODES[0];
  const Mode = active.component;
  const tabId = (id: ModeId) => `${baseId}-tab-${id}`;
  const panelId = `${baseId}-panel`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/42 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="flex max-h-[90vh] w-[1080px] max-w-full flex-col overflow-clip rounded-[6px] bg-paper font-ui text-ink shadow-[0_30px_80px_color-mix(in_srgb,var(--color-ink)_35%,transparent),0_0_0_1px_color-mix(in_srgb,var(--color-ink)_8%,transparent)] outline-none"
      >
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b-[1.5px] border-contour px-7 py-5">
          <div className="flex shrink-0 items-baseline gap-3 min-[900px]:w-[300px]">
            <h2 id={titleId} className="m-0 font-display text-[20px] leading-6 font-extrabold tracking-[-0.01em] text-ink">
              Found a city
            </h2>
            <span className="font-plex text-[12px] leading-4 tracking-[0.08em] text-muted" aria-label={`Survey number ${seedText}`}>
              SURVEY Nº {seedText || "—"}
            </span>
          </div>

          <div role="tablist" aria-label="How to found it" className="flex gap-1 rounded-full bg-parchment-dim p-1" onKeyDown={handleTabKeyDown}>
            {MODES.map((m, i) => {
              const selected = m.id === mode;
              const available = Boolean(m.component);
              const tipId = `${baseId}-tip-${m.id}`;
              return (
                <div key={m.id} className="group relative">
                  <button
                    ref={(el) => {
                      tabRefs.current[i] = el;
                    }}
                    id={tabId(m.id)}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    aria-controls={selected ? panelId : undefined}
                    aria-disabled={available ? undefined : true}
                    aria-describedby={available ? undefined : tipId}
                    tabIndex={selected ? 0 : -1}
                    onClick={() => available && setMode(m.id)}
                    className={`flex items-center gap-2 rounded-full px-[18px] py-2 font-ui text-[14px] leading-[18px] font-semibold ${FOCUS_RING} ${
                      selected ? "bg-ink text-paper" : "bg-transparent text-ink"
                    } ${available ? "cursor-pointer" : "cursor-not-allowed opacity-60"}`}
                  >
                    {m.icon(selected)}
                    {m.label}
                  </button>
                  {!available && (
                    <span
                      id={tipId}
                      role="tooltip"
                      className="pointer-events-none absolute top-full left-1/2 z-20 mt-2 -translate-x-1/2 rotate-[-2deg] rounded-[4px] bg-ink px-2.5 py-0.5 font-hand text-[18px] leading-6 font-semibold whitespace-nowrap text-paper opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100 motion-reduce:transition-none"
                    >
                      Coming soon
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          <div className="flex shrink-0 justify-end min-[900px]:w-[300px]">
            <button
              type="button"
              onClick={close}
              disabled={isFounding}
              aria-label="Close"
              className={`flex size-9 cursor-pointer items-center justify-center rounded-full border-[1.5px] border-contour bg-transparent hover:bg-white disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS_RING}`}
            >
              <CloseIcon />
            </button>
          </div>
        </header>

        {Mode && (
          <Mode
            seedText={seedText}
            onSeedChange={setSeedText}
            seedError={seedProblem(seedText)}
            onClose={close}
            onFound={handleFound}
            isFounding={isFounding}
            foundError={foundError}
            panelId={panelId}
            tabId={tabId(mode)}
          />
        )}
      </div>
    </div>
  );
}
