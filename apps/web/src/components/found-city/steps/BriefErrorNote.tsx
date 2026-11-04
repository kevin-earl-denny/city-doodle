/**
 * Inline error for a failed brief request. The API's `detail` is written for
 * players, so it is shown as-is. When the brief service isn't configured
 * (503), offer the manual flow instead.
 */

import { FOCUS_RING } from "../FlowLayout";

export interface BriefError {
  message: string;
  status?: number;
}

interface BriefErrorNoteProps {
  error: BriefError;
  onTryDrawIt: () => void;
}

export function BriefErrorNote({ error, onTryDrawIt }: BriefErrorNoteProps) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-[6px] border-[1.5px] border-red-700/40 bg-red-50 px-4 py-3 font-ui text-[14px] leading-5 text-red-800"
    >
      <span className="min-w-0 flex-1">{error.message}</span>
      {error.status === 503 && (
        <button
          type="button"
          onClick={onTryDrawIt}
          className={`cursor-pointer rounded-full border-[1.5px] border-ink bg-white px-3 py-1 font-ui text-[13px] leading-4 font-semibold text-ink hover:bg-paper ${FOCUS_RING}`}
        >
          Try Draw it instead
        </button>
      )}
    </div>
  );
}
