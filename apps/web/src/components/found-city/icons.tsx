/**
 * Small line icons for the "Found a city" flow, ported from the Paper design.
 */

const C = {
  ink: "var(--color-ink)",
  paper: "var(--color-paper)",
  coast: "var(--color-coast)",
};

interface IconProps {
  className?: string;
  color?: string;
}

export function PencilIcon({ color = C.paper, className }: IconProps) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className={className}>
      <path d="M2 13 L10.5 4.5 L12 6 L3.5 14.5 L2 14.5 Z" fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M11 3.5 L12.5 2 L14 3.5 L12.5 5" fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

export function SparkleIcon({ color = C.coast, className }: IconProps) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className={className}>
      <path d="M8 1.5 L9.4 6.6 L14.5 8 L9.4 9.4 L8 14.5 L6.6 9.4 L1.5 8 L6.6 6.6 Z" fill={color} />
    </svg>
  );
}

export function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path d="M2 2 L12 12 M12 2 L2 12" stroke={C.ink} strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

export function ArrowIcon() {
  return (
    <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true" className="shrink-0">
      <path d="M1 6 H14 M9 1 L14 6 L9 11" fill="none" stroke={C.paper} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CheckIcon({ color = C.ink, className }: IconProps) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className={className}>
      <path d="M2 6.5 L5 9 L10 3" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Four-pip die, used by "Surprise me". */
export function DiceFourIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="shrink-0">
      <rect x="1.5" y="1.5" width="15" height="15" rx="3.5" fill="none" stroke={C.ink} strokeWidth="1.5" />
      <circle cx="6" cy="6" r="1.4" fill={C.ink} />
      <circle cx="12" cy="12" r="1.4" fill={C.ink} />
      <circle cx="12" cy="6" r="1.4" fill={C.ink} />
      <circle cx="6" cy="12" r="1.4" fill={C.ink} />
    </svg>
  );
}

/** Three-pip die, used by the name reroll button. */
export function DiceThreeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 18 18" aria-hidden="true">
      <rect x="1.5" y="1.5" width="15" height="15" rx="3.5" fill="none" stroke={C.ink} strokeWidth="1.5" />
      <circle cx="6" cy="6" r="1.4" fill={C.ink} />
      <circle cx="12" cy="12" r="1.4" fill={C.ink} />
      <circle cx="9" cy="9" r="1.4" fill={C.ink} />
    </svg>
  );
}

export function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="5" y="5" width="9" height="9" rx="1.5" fill="none" stroke={C.ink} strokeWidth="1.4" />
      <path d="M11 3 V2.5 A0.5 0.5 0 0 0 10.5 2 H3 A1 1 0 0 0 2 3 V10.5 A0.5 0.5 0 0 0 2.5 11 H3" fill="none" stroke={C.ink} strokeWidth="1.4" />
    </svg>
  );
}
