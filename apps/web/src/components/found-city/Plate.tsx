/**
 * The graph-paper preview frame on the right of the "Found a city" modal,
 * plus the field note that sits under it. Both modes (Draw it / Describe it)
 * use these, so they take SVG content and copy as props and know nothing
 * about the flow.
 */

import type { ReactNode } from "react";

/** SVG user units of the plate drawing. Children draw in this space. */
export const PLATE_WIDTH = 396;
export const PLATE_HEIGHT = 268;

interface PlateProps {
  /** SVG content drawn in a PLATE_WIDTH × PLATE_HEIGHT coordinate space. */
  children?: ReactNode;
  /**
   * "full" shows the whole drawing (step 1); "short" crops the bottom
   * (396×214) to make room for notes underneath (steps 2–3).
   */
  crop?: "full" | "short";
  /** Mono caption bottom-left, e.g. "PLATE I · 6.4 KM ACROSS". */
  caption?: string;
  /** Accessible description of the drawing. */
  label: string;
  className?: string;
}

export function Plate({ children, crop = "full", caption, label, className = "" }: PlateProps) {
  return (
    <figure
      className={`relative m-0 shrink-0 overflow-clip rounded-[4px] border-[1.5px] border-ink bg-parchment ${
        crop === "full" ? "aspect-[396/268]" : "aspect-[396/214]"
      } ${className}`}
    >
      <svg
        viewBox={`0 0 ${PLATE_WIDTH} ${PLATE_HEIGHT}`}
        className="absolute inset-x-0 top-0 block h-auto w-full"
        role="img"
        aria-label={label}
      >
        {children}
      </svg>
      <Compass />
      {caption && (
        <figcaption className="absolute bottom-[10px] left-[14px] font-plex text-[11px] leading-[14px] tracking-[0.06em] text-muted">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}

function Compass() {
  return (
    <div className="absolute top-3 right-[14px] flex flex-col items-center gap-0.5" aria-hidden="true">
      <span className="font-plex text-[11px] leading-[14px] font-semibold text-ink">N</span>
      <svg width="16" height="26" viewBox="0 0 16 26">
        <path d="M8 0 L14 24 L8 19 L2 24 Z" fill="var(--color-ink)" />
      </svg>
    </div>
  );
}

interface FieldNoteProps {
  /** Mono eyebrow, e.g. "WHY HERE?". */
  title: string;
  children: ReactNode;
  /** Handwritten aside under the body; an arrow is appended. */
  aside?: string;
  /** Step 1 spaces the note slightly more loosely than steps 2–3. */
  loose?: boolean;
}

export function FieldNote({ title, children, aside, loose = false }: FieldNoteProps) {
  return (
    <div className={`flex flex-col px-0.5 pt-0.5 ${loose ? "gap-1.5" : "gap-1"}`}>
      <h3 className="m-0 font-plex text-[11px] leading-[14px] font-semibold tracking-[0.12em] text-coast uppercase">
        {title}
      </h3>
      <p className="m-0 font-ui text-[15px] leading-[22px] text-ink-soft" aria-live="polite">
        {children}
      </p>
      {aside && (
        <p className="m-0 font-hand text-[20px] leading-[24px] font-semibold text-muted">{aside} ↗</p>
      )}
    </div>
  );
}
