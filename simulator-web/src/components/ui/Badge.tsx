import type { ReactNode } from "react";

type Severity = "normal" | "warning" | "critical" | "offline" | "info";

interface BadgeProps {
  children: ReactNode;
  severity?: Severity;
  dot?: boolean;
  pulse?: boolean;
}

const palette: Record<Severity, { bg: string; text: string; border: string }> = {
  normal: { bg: "rgba(34,197,94,0.2)", text: "#22c55e", border: "rgba(34,197,94,0.3)" },
  warning: { bg: "rgba(217,119,6,0.2)", text: "#f59e0b", border: "rgba(245,158,11,0.3)" },
  critical: { bg: "rgba(220,38,38,0.2)", text: "#ef4444", border: "rgba(239,68,68,0.3)" },
  offline: { bg: "rgba(75,85,99,0.2)", text: "#9ca3af", border: "rgba(107,114,128,0.3)" },
  info: { bg: "rgba(37,99,235,0.2)", text: "#60a5fa", border: "rgba(59,130,246,0.3)" },
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
          style={
            pulse
              ? undefined
              : { width: "7px", height: "7px", borderRadius: "50%", background: colors.text, display: "inline-block" }
          }
        />
      ) : null}
      {children}
    </span>
  );
}

