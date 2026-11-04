/**
 * The "surveyor at work" overlay for <Plate> while a brief request is in
 * flight (10–30 s): a pencil line traces the plate border and Caveat status
 * lines rotate. Motion stops under prefers-reduced-motion; the lines still
 * change so the wait doesn't look frozen.
 */

import { useEffect, useState } from "react";
import { SURVEY_LINES, shuffled } from "./describeOptions";
import { BigPencilIcon } from "./icons";
import { PLATE_HEIGHT, PLATE_WIDTH } from "./Plate";

const LINE_MS = 1500;

interface SurveyingOverlayProps {
  /** Laid over an existing drawing (refinement): wash it out behind the text. */
  overDrawing?: boolean;
}

export function SurveyingOverlay({ overDrawing = false }: SurveyingOverlayProps) {
  const [lines] = useState(() => shuffled(SURVEY_LINES));
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setIndex((i) => (i + 1) % lines.length), LINE_MS);
    return () => clearInterval(t);
  }, [lines.length]);

  return (
    <div
      className={`absolute inset-0 flex flex-col items-center justify-center gap-2.5 ${
        overDrawing ? "bg-parchment/85" : ""
      }`}
    >
      <svg
        viewBox={`0 0 ${PLATE_WIDTH} ${PLATE_HEIGHT}`}
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <rect
          x="4"
          y="4"
          width={PLATE_WIDTH - 8}
          height={PLATE_HEIGHT - 8}
          rx="3"
          pathLength={100}
          fill="none"
          stroke="var(--color-ink)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="100 100"
          vectorEffect="non-scaling-stroke"
          className="animate-survey-trace motion-reduce:animate-none motion-reduce:[stroke-dasharray:2_3]"
        />
      </svg>
      <BigPencilIcon className="animate-pencil-bob motion-reduce:animate-none" />
      <span className="sr-only" role="status">
        Surveying the land…
      </span>
      <p className="m-0 font-hand text-[24px] leading-[30px] font-semibold text-muted" aria-hidden="true">
        <span key={index} className="inline-block animate-fade-in motion-reduce:animate-none">
          {lines[index]}
        </span>
      </p>
      <p className="m-0 font-plex text-[11px] leading-[14px] tracking-[0.06em] text-muted" aria-hidden="true">
        THIS CAN TAKE HALF A MINUTE
      </p>
    </div>
  );
}
