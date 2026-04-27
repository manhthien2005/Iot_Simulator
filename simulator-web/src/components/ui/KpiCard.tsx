import type { CSSProperties, ReactNode } from "react";
import { Card } from "./Card";

export type KpiSeverity = "ok" | "warning" | "critical" | "neutral";

export interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  /**
   * Visual severity that mirrors the truth model in `docs/ux/...ledger.md`.
   * - `ok` keeps the default neutral look so a healthy dashboard stays calm.
   * - `warning` adds an amber accent strip + value tint.
   * - `critical` adds a red accent strip + value tint.
   * - `neutral` (default) is identical to `ok`; use it when the metric has
   *   no meaningful severity dimension (counts, version strings, etc.).
   */
  severity?: KpiSeverity;
  /** Optional trailing slot rendered next to `subtitle` (badge, icon, …). */
  trailing?: ReactNode;
}

const severityAccent: Record<KpiSeverity, { bar: string; value: string }> = {
  ok: { bar: "transparent", value: "var(--text-primary)" },
  neutral: { bar: "transparent", value: "var(--text-primary)" },
  warning: { bar: "var(--severity-warning)", value: "var(--severity-warning)" },
  critical: { bar: "var(--severity-critical)", value: "var(--severity-critical)" },
};

export function KpiCard({
  title,
  value,
  subtitle,
  severity = "neutral",
  trailing,
}: KpiCardProps) {
  const accent = severityAccent[severity];
  const wrapStyle: CSSProperties = {
    position: "relative",
    paddingLeft: severity === "warning" || severity === "critical" ? "10px" : 0,
    transition: "color var(--duration-fast) var(--ease-default)",
  };
  const subtitleRowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
  };

  return (
    <Card>
      <div style={wrapStyle}>
        {accent.bar !== "transparent" ? (
          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              left: 0,
              top: "4px",
              bottom: "4px",
              width: "3px",
              borderRadius: "2px",
              background: accent.bar,
            }}
          />
        ) : null}
        <small style={{ color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          {title}
        </small>
        <div
          style={{
            marginTop: "8px",
            fontSize: "30px",
            fontWeight: 700,
            fontFamily: "var(--font-mono)",
            color: accent.value,
          }}
        >
          {value}
        </div>
        <div style={subtitleRowStyle}>
          <small style={{ color: "var(--text-muted)" }}>{subtitle}</small>
          {trailing ? <span style={{ display: "inline-flex" }}>{trailing}</span> : null}
        </div>
      </div>
    </Card>
  );
}
