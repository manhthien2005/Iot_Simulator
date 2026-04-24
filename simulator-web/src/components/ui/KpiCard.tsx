import { Card } from "./Card";

export interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle: string;
}

export function KpiCard({ title, value, subtitle }: KpiCardProps) {
  return (
    <Card>
      <small style={{ color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{title}</small>
      <div style={{ marginTop: "8px", fontSize: "30px", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{value}</div>
      <small style={{ color: "var(--text-muted)" }}>{subtitle}</small>
    </Card>
  );
}
