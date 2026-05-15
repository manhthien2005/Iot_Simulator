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
      className={`surface-card${hoverable ? " surface-card--hoverable" : ""}`}
      style={{ padding: paddingMap[padding] }}
    >
      {header ? <header style={{ marginBottom: "12px" }}>{header}</header> : null}
      <div>{children}</div>
      {footer ? <footer style={{ marginTop: "12px" }}>{footer}</footer> : null}
    </section>
  );
}

