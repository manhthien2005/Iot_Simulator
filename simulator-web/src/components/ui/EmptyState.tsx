import type { LucideIcon } from "lucide-react";
import { Button } from "./Button";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div
      style={{
        border: "1px dashed var(--border-subtle)",
        borderRadius: "var(--radius-lg)",
        padding: "24px",
        textAlign: "center",
        color: "var(--text-secondary)",
      }}
    >
      <Icon size={28} style={{ marginBottom: "8px", color: "var(--text-muted)" }} />
      <h3 style={{ margin: "0 0 8px", color: "var(--text-primary)" }}>{title}</h3>
      {description ? <p style={{ margin: "0 0 16px" }}>{description}</p> : null}
      {action ? <Button onClick={action.onClick}>{action.label}</Button> : null}
    </div>
  );
}

