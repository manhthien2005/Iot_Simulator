import type { ReactNode } from "react";

type Severity = "normal" | "warning" | "critical" | "offline" | "info";

interface BadgeProps {
  children: ReactNode;
  severity?: Severity;
  dot?: boolean;
  pulse?: boolean;
}

const palette: Record<Severity, { bg: string; text: string; border: string }> = {
  normal:   { bg: "var(--severity-normal-bg)",   text: "var(--severity-normal)",   border: "var(--severity-normal-border)" },
  warning:  { bg: "var(--severity-warning-bg)",  text: "var(--severity-warning)",  border: "var(--severity-warning-border)" },
  critical: { bg: "var(--severity-critical-bg)", text: "var(--severity-critical)", border: "var(--severity-critical-border)" },
  offline:  { bg: "var(--severity-offline-bg)",  text: "var(--severity-offline)",  border: "var(--severity-offline-border)" },
  info:     { bg: "var(--severity-info-bg)",      text: "var(--severity-info)",     border: "var(--severity-info-border)" },
};

export function Badge({ children, severity = "info", dot = false, pulse = false }: BadgeProps) {
  const colors = palette[severity];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "2px 8px",
        borderRadius: "var(--radius-full)",
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        color: colors.text,
        fontSize: "11px",
        letterSpacing: "0.04em",
        textTransform: "uppercase",
      }}
    >
      {dot ? (
        <span
          className={pulse ? "live-dot" : undefined}
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: colors.text,
            display: "inline-block",
            animation: pulse ? "live-pulse 2s infinite" : undefined,
          }}
        />
      ) : null}
      {children}
    </span>
  );
}

