/**
 * A native range input dressed up as a map scale bar: alternating ink and
 * blank segments with a round blue thumb. Thumb styles live in index.css
 * (.scale-bar-range) because they need vendor pseudo-elements.
 */

import { useId } from "react";

interface ScaleBarSliderProps {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
  /** Readout next to the bar, also used as aria-valuetext. */
  valueText: string;
  /** "mono" for measurements ("100 m"), "hand" for word labels ("snug"). */
  valueStyle?: "mono" | "hand";
}

const SEGMENTS = [true, false, true, false, true];

export function ScaleBarSlider({
  label,
  min,
  max,
  step,
  value,
  onChange,
  valueText,
  valueStyle = "mono",
}: ScaleBarSliderProps) {
  const id = useId();
  return (
    <div className="flex items-center gap-3">
      <label htmlFor={id} className="w-16 shrink-0 font-ui text-[13px] leading-4 font-medium text-ink">
        {label}
      </label>
      <div className="relative h-4 min-w-0 flex-1 min-[900px]:w-[220px] min-[900px]:flex-none">
        <div
          className="pointer-events-none absolute inset-x-0 top-1 flex h-2 border-[1.2px] border-ink"
          aria-hidden="true"
        >
          {SEGMENTS.map((filled, i) => (
            <div key={i} className={`flex-1 ${filled ? "bg-ink" : ""}`} />
          ))}
        </div>
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          aria-valuetext={valueText}
          onChange={(e) => onChange(Number(e.target.value))}
          className="scale-bar-range absolute inset-0 m-0 h-4 w-full"
        />
      </div>
      <output
        htmlFor={id}
        className={
          valueStyle === "mono"
            ? "font-plex text-[12px] leading-4 text-body"
            : "font-hand text-[18px] leading-[22px] font-semibold text-body"
        }
      >
        {valueText}
      </output>
    </div>
  );
}
