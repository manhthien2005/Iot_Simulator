import { Card } from "../../ui/Card";
import {
  sleepScenarioOptions,
  type SleepScenarioOption,
  type SleepScenarioTargets,
} from "../../../config/sleepScenarios";
import type { ScenarioSeverity } from "../../../types/scenario";

// ---------------------------------------------------------------------------
// SleepScenarioCard — sleep-domain twin of ScenarioSelector.
//
// Layout mirrors session/ScenarioSelector so operators can rely on muscle
// memory:
//   ┌─ Kịch bản giấc ngủ ───────────────────────────────────┐
//   │ [Dropdown chọn kịch bản]                              │
//   │ ─────────────────────────────────────────────────────  │
//   │ ## Tên kịch bản                                        │
//   │ Mức độ: ● severity_label                               │
//   │ Mô tả AASM-style                                       │
//   │ Bảng metric kỳ vọng (Efficiency / Deep / REM / Wake / SpO2 / AHI) │
//   │ Disorder tags chips                                    │
//   └────────────────────────────────────────────────────────┘
//
// Receives `value` + `onChange` so SleepLabPage owns the selection state.
// Pure presentation component; no data fetching.
// ---------------------------------------------------------------------------

const SEVERITY_LABEL: Record<ScenarioSeverity, string> = {
  normal: "Ổn định",
  warning: "Theo dõi",
  critical: "Nguy kịch",
};

const SEVERITY_DOT: Record<ScenarioSeverity, string> = {
  normal: "var(--severity-normal, #22c55e)",
  warning: "var(--severity-warning, #f59e0b)",
  critical: "var(--severity-critical, #ef4444)",
};

const SEVERITY_OPTION_EMOJI: Record<ScenarioSeverity, string> = {
  normal: "🟢",
  warning: "🟡",
  critical: "🔴",
};

interface SleepScenarioCardProps {
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}

export function SleepScenarioCard({ value, onChange, disabled = false }: SleepScenarioCardProps) {
  const selected = sleepScenarioOptions.find((option) => option.id === value) ?? null;

  return (
    <Card header={<strong>Kịch bản giấc ngủ</strong>}>
      <div style={{ display: "grid", gap: "16px" }}>
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          aria-label="Chọn kịch bản giấc ngủ"
          style={{
            width: "100%",
            background: "var(--bg-base)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            padding: "10px 12px",
            fontSize: "14px",
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
          }}
        >
          {sleepScenarioOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {SEVERITY_OPTION_EMOJI[option.severity]} {option.label}
            </option>
          ))}
        </select>

        {selected ? <ScenarioDetail scenario={selected} /> : null}
      </div>
    </Card>
  );
}

function ScenarioDetail({ scenario }: { scenario: SleepScenarioOption }) {
  const dotColor = SEVERITY_DOT[scenario.severity];

  return (
    <div
      style={{
        padding: "16px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-elevated)",
        border: "1px solid rgba(255,255,255,0.05)",
        display: "grid",
        gap: "12px",
      }}
    >
      <h3
        style={{
          margin: 0,
          fontSize: "18px",
          fontWeight: 700,
          color: "var(--text-primary)",
          letterSpacing: "-0.01em",
          lineHeight: 1.3,
        }}
      >
        {scenario.label}
      </h3>

      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
        <span style={{ color: "var(--text-secondary)" }}>Mức độ:</span>
        <span
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background: dotColor,
            flexShrink: 0,
          }}
        />
        <span style={{ color: dotColor, fontWeight: 700 }}>{SEVERITY_LABEL[scenario.severity]}</span>
      </div>

      <p
        style={{
          margin: 0,
          fontSize: "13.5px",
          color: "var(--text-secondary)",
          lineHeight: 1.6,
        }}
      >
        {scenario.description}
      </p>

      <TargetsTable targets={scenario.targets} />

      {scenario.disorderTags.length > 0 ? <TagsRow tags={scenario.disorderTags} severity={scenario.severity} /> : null}
    </div>
  );
}

function TargetsTable({ targets }: { targets: SleepScenarioTargets }) {
  const rows: Array<{ label: string; value: string }> = [
    { label: "Hiệu suất", value: `${(targets.efficiency * 100).toFixed(0)}%` },
    { label: "Deep", value: `${(targets.deepPct * 100).toFixed(0)}%` },
    { label: "REM", value: `${(targets.remPct * 100).toFixed(0)}%` },
    { label: "Light", value: `${(targets.lightPct * 100).toFixed(0)}%` },
    { label: "Awake", value: `${(targets.awakePct * 100).toFixed(0)}%` },
    { label: "Số lần thức", value: `${targets.wakeCount}` },
  ];
  if (targets.spo2Min !== undefined) {
    rows.push({ label: "SpO2 min", value: `${targets.spo2Min}%` });
  }
  if (targets.ahiHint) {
    rows.push({ label: "AHI", value: targets.ahiHint });
  }

  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <div
        style={{
          fontSize: "11.5px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          color: "var(--text-muted)",
        }}
      >
        Chỉ số kỳ vọng
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
          gap: "8px",
        }}
      >
        {rows.map((row) => (
          <div
            key={row.label}
            style={{
              padding: "8px 10px",
              borderRadius: "var(--radius-md)",
              background: "var(--bg-base)",
              border: "1px solid var(--border-default)",
              display: "grid",
              gap: "2px",
              minWidth: 0,
            }}
          >
            <span
              style={{
                fontSize: "10.5px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                color: "var(--text-muted)",
              }}
            >
              {row.label}
            </span>
            <span
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "var(--text-primary)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TagsRow({ tags, severity }: { tags: string[]; severity: ScenarioSeverity }) {
  const accentColor = SEVERITY_DOT[severity];
  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <div
        style={{
          fontSize: "11.5px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          color: "var(--text-muted)",
        }}
      >
        Disorder tags
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
        {tags.map((tag) => (
          <span
            key={tag}
            style={{
              padding: "3px 10px",
              borderRadius: "var(--radius-full)",
              fontSize: "11.5px",
              fontWeight: 600,
              color: accentColor,
              background: `color-mix(in srgb, ${accentColor} 12%, transparent)`,
              border: `1px solid color-mix(in srgb, ${accentColor} 30%, transparent)`,
              fontFamily: "var(--font-mono)",
            }}
          >
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
}
