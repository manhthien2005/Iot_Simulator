import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";

interface ErrorCardProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorCard({ message, onRetry }: ErrorCardProps) {
  return (
    <div
      style={{
        background: "rgba(127,29,29,0.25)",
        border: "1px solid rgba(239,68,68,0.35)",
        borderRadius: "var(--radius-lg)",
        padding: "16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <AlertTriangle size={18} color="var(--severity-critical)" />
        <span style={{ color: "var(--text-primary)" }}>{message}</span>
      </div>
      {onRetry ? <Button variant="outline" onClick={onRetry}>Thử lại</Button> : null}
    </div>
  );
}
