import { useState, type ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  header?: ReactNode;
  footer?: ReactNode;
  padding?: "sm" | "md" | "lg" | "none";
  hoverable?: boolean;
}

const paddingMap = {
  none: "0",
  sm: "12px",
  md: "16px",
  lg: "20px",
};

export function Card({ children, header, footer, padding = "md", hoverable = false }: CardProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <section
      className="surface-card"
      style={{
        padding: paddingMap[padding],
        transition:
          "border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default)",
        transform: hoverable && hovered ? "translateY(-1px)" : hoverable ? "translateY(0)" : "none",
        borderColor: hoverable && hovered ? "var(--border-subtle)" : undefined,
        boxShadow: hoverable && hovered ? "var(--shadow-md)" : undefined,
      }}
      onMouseEnter={hoverable ? () => setHovered(true) : undefined}
      onMouseLeave={hoverable ? () => setHovered(false) : undefined}
    >
      {header ? <header style={{ marginBottom: "12px" }}>{header}</header> : null}
      <div>{children}</div>
      {footer ? <footer style={{ marginTop: "12px" }}>{footer}</footer> : null}
    </section>
  );
}

