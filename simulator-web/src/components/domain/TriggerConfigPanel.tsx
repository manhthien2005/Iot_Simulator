import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Card } from "../ui/Card";
import type { SimulatorSettingsResponse } from "../../types/settings";

// ---------------------------------------------------------------------------
// TriggerConfigPanel — Module F.10 (moved from `SettingsPage` to
// `/diagnostics`).
//
// Renders the rule and fall pipeline JSON configs the simulator picked up
// at startup.  Read-only — the JSON is the source of truth on disk; the
// editor lives in the `pre_model_trigger/` package, not the UI.
// ---------------------------------------------------------------------------

interface TriggerConfigPanelProps {
  data: SimulatorSettingsResponse;
}

export function TriggerConfigPanel({ data }: TriggerConfigPanelProps) {
  const [rulesOpen, setRulesOpen] = useState(false);
  const [fallOpen, setFallOpen] = useState(false);

  return (
    <Card header={<strong>Pre-Model Trigger Config (read-only)</strong>}>
      <p style={{ margin: "0 0 10px 0", fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
        File JSON mà <code>pre_model_trigger</code> nạp lúc khởi động — sửa file rồi restart simulator để
        thay đổi. Hiển thị đầy đủ tại đây để operator kiểm tra rule/fall logic mà không cần SSH vào host.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <CollapsibleJson
          label="Rules Config"
          json={data.rules_config}
          isOpen={rulesOpen}
          onToggle={() => setRulesOpen(!rulesOpen)}
        />
        <CollapsibleJson
          label="Fall Pipeline Config"
          json={data.fall_config}
          isOpen={fallOpen}
          onToggle={() => setFallOpen(!fallOpen)}
        />
      </div>
    </Card>
  );
}

function CollapsibleJson({
  label,
  json,
  isOpen,
  onToggle,
}: {
  label: string;
  json: Record<string, unknown> | null;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        style={{
          background: "none",
          border: "none",
          color: "var(--text-primary)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "4px 0",
          fontSize: "13px",
          fontWeight: 500,
        }}
      >
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {label}
        {json === null && (
          <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(không tìm thấy file)</span>
        )}
      </button>
      {isOpen && json !== null && (
        <pre
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            padding: "12px",
            fontSize: "12px",
            fontFamily: "var(--font-mono)",
            overflow: "auto",
            maxHeight: "400px",
            marginTop: "4px",
          }}
        >
          {JSON.stringify(json, null, 2)}
        </pre>
      )}
    </div>
  );
}
