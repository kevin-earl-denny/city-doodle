/**
 * Layout pieces shared by every mode of the "Found a city" modal: route
 * steps, the two-column step body, the footer, buttons and the sticker-card
 * radio group. A mode (Draw it, later Describe it) composes these.
 */

import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { ArrowIcon, CheckIcon } from "./icons";

export const FOCUS_RING =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coast";

// ============================================================================
// Route steps
// ============================================================================

interface RouteStepsProps {
  labels: string[];
  /** 1-based current step. */
  current: number;
  /** Furthest step reached; steps up to here are buttons (the current one does nothing). */
  reached: number;
  onSelect: (step: number) => void;
}

export function RouteSteps({ labels, current, reached, onSelect }: RouteStepsProps) {
  return (
    <nav aria-label="Steps" className="px-7 pt-[18px]">
      <ol className="m-0 flex list-none flex-wrap items-center gap-[14px] p-0">
        {labels.map((label, i) => {
          const n = i + 1;
          const state = n === current ? "current" : n < current ? "done" : "todo";
          // The current step stays a focusable button too, so clicking a step
          // never removes the element that holds focus.
          const isButton = n <= reached || n === current;
          const content = (
            <>
              <span
                className={`flex size-6 shrink-0 items-center justify-center rounded-full font-plex text-[12px] leading-4 font-semibold ${
                  state === "current"
                    ? "bg-ink text-paper"
                    : state === "done"
                      ? "border-[1.5px] border-ink bg-water text-ink"
                      : "border-[1.5px] border-pencil text-muted"
                }`}
              >
                {n}
              </span>
              <span
                className={`font-ui text-[14px] leading-[18px] ${
                  state === "current" ? "font-semibold text-ink" : state === "done" ? "font-medium text-ink" : "font-medium text-muted"
                }`}
              >
                {label}
              </span>
            </>
          );
          return (
            <li key={label} className="flex items-center gap-[14px]">
              {i > 0 && (
                <span
                  aria-hidden="true"
                  className={`h-0 w-14 shrink-0 border-t-2 ${n <= current ? "border-solid border-ink" : "border-dashed border-contour"}`}
                />
              )}
              {isButton ? (
                <button
                  type="button"
                  aria-current={state === "current" ? "step" : undefined}
                  onClick={() => n !== current && onSelect(n)}
                  className={`flex items-center gap-2 rounded-full bg-transparent p-0 ${
                    state === "current" ? "cursor-default" : "cursor-pointer hover:underline"
                  } ${FOCUS_RING}`}
                >
                  {content}
                  {state !== "current" && <span className="sr-only">(go to this step)</span>}
                </button>
              ) : (
                <span className="flex items-center gap-2">{content}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ============================================================================
// Step body
// ============================================================================

export function StepHeading({ title, aside }: { title: string; aside: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      {/* Focused by FlowForm when the step changes (tabIndex -1: not in the Tab order). */}
      <h2
        tabIndex={-1}
        data-step-heading=""
        className="m-0 font-display text-[44px] leading-[46px] font-extrabold tracking-[-0.025em] text-balance text-ink outline-none"
      >
        {title}
      </h2>
      <p className="m-0 font-hand text-[24px] leading-7 font-semibold text-coast">{aside}</p>
    </div>
  );
}

interface FlowColumnsProps {
  /** Changing this replays the step-in transition. */
  stepKey: string | number;
  left: ReactNode;
  right: ReactNode;
  /** Gap between heading and content in the left column: 18px, 22px (default) or 26px. */
  leftGap?: "tight" | "normal" | "loose";
}

export function FlowColumns({ stepKey, left, right, leftGap = "normal" }: FlowColumnsProps) {
  return (
    <div
      key={stepKey}
      className="grid animate-step-in grid-cols-1 gap-9 p-7 motion-reduce:animate-none min-[900px]:grid-cols-[592fr_396fr]"
    >
      <div
        className={`flex min-w-0 flex-col ${
          leftGap === "loose" ? "gap-[26px]" : leftGap === "tight" ? "gap-[18px]" : "gap-[22px]"
        }`}
      >
        {left}
      </div>
      <div className="flex min-w-0 flex-col gap-[14px]">{right}</div>
    </div>
  );
}

// ============================================================================
// Footer and buttons
// ============================================================================

interface FlowFooterProps {
  left?: ReactNode;
  primary: ReactNode;
  onCancel: () => void;
  cancelDisabled?: boolean;
}

export function FlowFooter({ left, primary, onCancel, cancelDisabled }: FlowFooterProps) {
  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t-[1.5px] border-contour bg-parchment-footer px-7 py-[18px]">
      <div>{left}</div>
      <div className="flex items-center gap-[18px]">
        <button
          type="button"
          onClick={onCancel}
          disabled={cancelDisabled}
          className={`cursor-pointer rounded-full bg-transparent px-1 font-ui text-[14px] leading-[18px] font-medium text-body hover:text-ink disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS_RING}`}
        >
          Cancel
        </button>
        {primary}
      </div>
    </div>
  );
}

interface PrimaryButtonProps {
  children: ReactNode;
  pending?: boolean;
  /** Step 3's "Found …" button is a touch roomier than "Next". */
  size?: "normal" | "large";
  /** Text to show while pending instead of the city loader. */
  pendingLabel?: string;
}

/**
 * Submits the flow's form. While pending it is aria-disabled rather than
 * disabled, so it keeps focus (a disabled button drops focus to <body>).
 */
export function PrimaryButton({ children, pending = false, size = "normal", pendingLabel }: PrimaryButtonProps) {
  return (
    <button
      type="submit"
      aria-disabled={pending || undefined}
      aria-busy={pending}
      onClick={(e) => {
        if (pending) e.preventDefault();
      }}
      className={`flex cursor-pointer items-center gap-2.5 rounded-full bg-ink font-ui text-[15px] leading-[18px] font-semibold text-paper shadow-[3px_3px_0_var(--color-water)] transition-transform duration-150 hover:-translate-y-px aria-disabled:cursor-wait motion-reduce:transition-none ${
        size === "large" ? "px-[26px] py-[13px]" : "px-[22px] py-3"
      } ${FOCUS_RING}`}
    >
      {pending ? (
        // Plain text: the animated CityLoader doesn't fit inside a pill button.
        <>
          {pendingLabel ?? "Founding…"}
          <span className="sr-only"> (working)</span>
        </>
      ) : (
        <>
          {children}
          <ArrowIcon />
        </>
      )}
    </button>
  );
}

interface PillButtonProps {
  children: ReactNode;
  onClick: () => void;
  icon?: ReactNode;
  /** "dashed" for playful actions (Surprise me), "solid" for Back. */
  variant?: "dashed" | "solid";
  disabled?: boolean;
}

/** aria-disabled rather than disabled, so a pill that was just clicked keeps focus. */
export function PillButton({ children, onClick, icon, variant = "solid", disabled }: PillButtonProps) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onClick()}
      aria-disabled={disabled || undefined}
      className={`flex cursor-pointer items-center gap-2.5 rounded-full border-[1.5px] bg-transparent px-4 py-2.5 font-ui text-[14px] leading-[18px] font-semibold text-ink hover:bg-paper aria-disabled:cursor-not-allowed aria-disabled:opacity-50 ${
        variant === "dashed" ? "border-dashed border-pencil" : "border-solid border-contour"
      } ${FOCUS_RING}`}
    >
      {icon}
      {children}
    </button>
  );
}

// ============================================================================
// Sticker-card radio group
// ============================================================================

interface CardRadioGroupProps<T extends string> {
  label: string;
  options: readonly T[];
  value: T | null;
  onChange: (value: T) => void;
  className?: string;
  renderCard: (option: T, checked: boolean) => ReactNode;
  /** Accessible name of each card. */
  optionLabel: (option: T) => string;
  /** Sticker tilt of the selected card, in degrees. */
  tilt: number;
  /** Inner padding class pair: [unchecked, checked] (the checked border is 0.5px thicker). */
  padding: [string, string];
}

/**
 * role="radiogroup" of cards with roving tabindex. Arrow keys move the
 * selection, like native radio buttons.
 */
export function CardRadioGroup<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
  renderCard,
  optionLabel,
  tilt,
  padding,
}: CardRadioGroupProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const focusIndex = value ? options.indexOf(value) : 0;

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    // Move from the focused card; with nothing selected that is the first card.
    const focused = refs.current.findIndex((el) => el === e.target);
    const current = focused >= 0 ? focused : value ? options.indexOf(value) : 0;
    let next: number;
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        next = (current + 1) % options.length;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        next = (current - 1 + options.length) % options.length;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = options.length - 1;
        break;
      default:
        return;
    }
    e.preventDefault();
    onChange(options[next]);
    refs.current[next]?.focus();
  };

  return (
    <div role="radiogroup" aria-label={label} className={className} onKeyDown={handleKeyDown}>
      {options.map((option, i) => {
        const checked = option === value;
        return (
          <button
            key={option}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={optionLabel(option)}
            tabIndex={i === focusIndex ? 0 : -1}
            onClick={() => onChange(option)}
            style={checked ? { rotate: `${tilt}deg` } : undefined}
            className={`relative flex min-w-0 cursor-pointer flex-col rounded-[6px] bg-white text-left transition-[translate] duration-150 hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0 ${FOCUS_RING} ${
              checked
                ? `z-10 border-2 border-ink shadow-[4px_4px_0_var(--color-ink)] ${padding[1]}`
                : `border-[1.5px] border-card-edge hover:border-contour ${padding[0]}`
            }`}
          >
            {renderCard(option, checked)}
            {checked && (
              <span
                aria-hidden="true"
                className="absolute -top-2.5 -right-2.5 flex size-[26px] items-center justify-center rounded-full border-2 border-ink bg-water"
              >
                <CheckIcon />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ============================================================================
// Form frame
// ============================================================================

interface FlowFormProps {
  /** Called on Enter or the primary button: advance a step or found the city. */
  onSubmit: () => void;
  /** Route steps and step body; this part scrolls. */
  children: ReactNode;
  footer: ReactNode;
  /** Wires the form up as the panel of the active mode tab. */
  panelId: string;
  tabId: string;
  /** Current step. When it changes, focus moves to the new step's heading. */
  step: number;
}

export function FlowForm({ onSubmit, children, footer, panelId, tabId, step }: FlowFormProps) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);

  // The control that changed the step (a route step, Back, Next) may have
  // unmounted. Put focus somewhere meaningful so keyboard users aren't
  // stranded on <body>, and start the new step scrolled to the top.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    bodyRef.current?.scrollTo?.({ top: 0 });
    bodyRef.current?.querySelector<HTMLElement>("[data-step-heading]")?.focus({ preventScroll: true });
  }, [step]);

  return (
    <form
      id={panelId}
      role="tabpanel"
      aria-labelledby={tabId}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div ref={bodyRef} className="min-h-0 flex-1 overflow-y-auto">
        {children}
      </div>
      {footer}
    </form>
  );
}
