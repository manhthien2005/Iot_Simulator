interface ReadOnlyFlagRowProps {
  envVar: string;
  checked: boolean;
  hint: string;
}

export function ReadOnlyFlagRow({ envVar, checked, hint }: ReadOnlyFlagRowProps) {
  return (
    <div
      style={{
        display: "grid",
        gap: "4px",
        padding: "8px 12px",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border-default)",
        background: "var(--bg-elevated)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span
          style={{
            fontSize: "11px",
            fontWeight: 700,
            padding: "2px 8px",
            borderRadius: "var(--radius-full)",
            color: checked ? "var(--severity-normal)" : "var(--text-secondary)",
            border: `1px solid ${checked ? "var(--severity-normal-border)" : "var(--border-default)"}`,
            background: checked ? "var(--severity-normal-bg)" : "transparent",
            textTransform: "uppercase" as const,
            letterSpacing: "0.05em",
          }}
        >
          {checked ? "ON" : "OFF"}
        </span>
        <code style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
          {envVar}
        </code>
      </div>
      <small style={{ color: "var(--text-secondary)", fontSize: "12px", lineHeight: 1.5 }}>
        {hint}
      </small>
    </div>
  );
}
