import type { ReactNode } from "react";

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
  return (
    <section
      className="surface-card"
      style={{
        padding: paddingMap[padding],
        transition:
          "border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default)",
        transform: hoverable ? "translateY(0)" : "none",
      }}
      onMouseEnter={(event) => {
        if (hoverable) {
          event.currentTarget.style.borderColor = "var(--border-subtle)";
          event.currentTarget.style.boxShadow = "var(--shadow-md)";
          event.currentTarget.style.transform = "translateY(-1px)";
        }
      }}
      onMouseLeave={(event) => {
        if (hoverable) {
          event.currentTarget.style.borderColor = "var(--border-default)";
          event.currentTarget.style.boxShadow = "var(--shadow-sm)";
          event.currentTarget.style.transform = "translateY(0)";
        }
      }}
    >
      {header ? <header style={{ marginBottom: "12px" }}>{header}</header> : null}
      <div>{children}</div>
      {footer ? <footer style={{ marginTop: "12px" }}>{footer}</footer> : null}
    </section>
  );
}

