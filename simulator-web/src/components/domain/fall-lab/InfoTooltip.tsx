import { Info } from "lucide-react";
import { Tooltip } from "../../ui/Tooltip";
import { FALL_LAB_TOOLTIPS, type FallLabTooltipKey } from "./fallLabTooltips";

// ---------------------------------------------------------------------------
// InfoTooltip — Module FA Phase 4 helper.
//
// Tiny wrapper that pairs the centralised Vietnamese tooltip copy with an
// `(i)` info icon trigger.  Used inline next to a metric label so the
// layout stays compact.
//
// Why a wrapper instead of using `<Tooltip/>` directly per call site:
//   * Removes 6 lines of import + JSX boilerplate per metric.
//   * Forces all Fall Lab tooltip copy to flow through `fallLabTooltips.ts`
//     (one file to iterate copy / localise later).
//   * Single icon style + size so the page reads consistently.
//
// Usage:
//   <span>Đỉnh |a|</span> <InfoTooltip k="motionPeak" />
// ---------------------------------------------------------------------------

interface Props {
  /** Tooltip copy key in `FALL_LAB_TOOLTIPS`. */
  k: FallLabTooltipKey;
  /** Icon size in px (default 12 — sized for inline metric labels). */
  size?: number;
  /** Override aria-label when the surrounding text already conveys context. */
  ariaLabel?: string;
}

export function InfoTooltip({ k, size = 12, ariaLabel }: Props) {
  const content = FALL_LAB_TOOLTIPS[k];
  return (
    <Tooltip content={content} placement="top">
      <span
        role="button"
        tabIndex={0}
        aria-label={ariaLabel ?? "Xem giải thích"}
        style={{
          display: "inline-flex",
          alignItems: "center",
          marginLeft: "4px",
          color: "var(--text-muted)",
          cursor: "help",
          verticalAlign: "middle",
        }}
      >
        <Info size={size} />
      </span>
    </Tooltip>
  );
}
