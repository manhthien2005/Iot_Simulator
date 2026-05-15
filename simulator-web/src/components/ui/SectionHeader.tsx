import type { ReactNode } from "react";

interface SectionHeaderProps {
  children: ReactNode;
}

export function SectionHeader({ children }: SectionHeaderProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div
        style={{
          width: "3px",
          height: "18px",
          borderRadius: "2px",
          background: "var(--accent-cyan)",
          flexShrink: 0,
        }}
      />
      <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>{children}</h2>
    </div>
  );
}
