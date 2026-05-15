import type { CSSProperties, ReactNode } from "react";
import { Sparkline } from "../../ui/Sparkline";
import { Tooltip } from "../../ui/Tooltip";

// ---------------------------------------------------------------------------
// MetricTile — compact KPI tile for the Cockpit dashboard.
//
// Replaces the legacy `KpiCard` (uppercase title + long subtitle) on the
// dashboard.  Differences:
//   * Icon-prefixed title, single short label below the value.
//   * Sparkline rendered at the bottom — visual trend > prose subtitle.
//   * Optional hover tooltip carries the long-form rationale so we don't
//     waste vertical space in the tile body.
//
// Density target: 4 tiles fit in a 2x2 grid inside the metrics column on
// a 1440px viewport.
// ---------------------------------------------------------------------------

export type MetricSeverity = "ok" | "warning" | "critical" | "neutral";

interface MetricTileProps {
  /** Lucide icon node (sized 16, color inherited). */
  icon: ReactNode;
  /** Short label e.g. "Thiết bị". */
  label: string;
  /** Display value e.g. 12 or "142ms". */
  value: string | number;
  /** Severity tints the value color + sparkline stroke. */
  severity?: MetricSeverity;
  /** Recent history for the sparkline (max ~20 samples). */
  history?: number[];
  /** Optional hover detail — long form. */
  tooltip?: string;
}

const severityAccent: Record<MetricSeverity, string> = {
  ok: "var(--text-primary)",
  neutral: "var(--text-primary)",
  warning: "var(--severity-warning)",
  critical: "var(--severity-critical)",
};

const severityStroke: Record<MetricSeverity, string> = {
  ok: "var(--accent-cyan)",
  neutral: "var(--accent-cyan)",
  warning: "var(--severity-warning)",
  critical: "var(--severity-critical)",
};

export function MetricTile({
  icon,
  label,
  value,
  severity = "neutral",
  history = [],
  tooltip,
}: MetricTileProps) {
  const tile = (
    <div style={tileStyle}>
      {/* Header: icon + label */}
      <div style={headerStyle}>
        <span style={{ display: "inline-flex", color: "var(--text-secondary)" }}>{icon}</span>
        <span
          style={{
            fontSize: "11px",
            fontWeight: 500,
            color: "var(--text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {label}
        </span>
      </div>

      {/* Value */}
      <div
        style={{
          fontSize: "26px",
          fontWeight: 700,
          fontFamily: "var(--font-mono)",
          color: severityAccent[severity],
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          marginTop: "6px",
        }}
      >
        {value}
      </div>

      {/* Sparkline pinned at the bottom, fills tile width */}
      <div style={{ marginTop: "auto", paddingTop: "10px", height: "36px" }}>
        <Sparkline
          values={history}
          width={200}
          height={32}
          stroke={severityStroke[severity]}
          ariaLabel={`${label} trend`}
          fluid
        />
      </div>
    </div>
  );

  if (tooltip) {
    return (
      <Tooltip content={tooltip} placement="top">
        {tile}
      </Tooltip>
    );
  }
  return tile;
}

// ── Styles ──────────────────────────────────────────────────────────────

const tileStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "14px 16px",
  borderRadius: "var(--radius-lg)",
  background: "var(--bg-elevated)",
  border: "1px solid rgba(255, 255, 255, 0.06)",
  boxShadow: "var(--shadow-card)",
  height: "140px",
  transition: "border-color 150ms ease, transform 150ms ease",
  cursor: "default",
};

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
};
