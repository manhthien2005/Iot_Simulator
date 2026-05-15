import { Card } from "../../ui/Card";
import type { ScenarioOption, ScenarioSeverity } from "../../../types/scenario";

// ---------------------------------------------------------------------------
// ScenarioSelector — redesigned per May 2026 UX feedback.
//
// Layout:
//   ┌─ Kịch bản mô phỏng ──────────────────────────────┐
//   │  [Dropdown chọn kịch bản]                        │
//   │  ─────────────────────────────────────────────── │
//   │  ## Nghỉ ngơi bình thường (title to)             │
//   │                                                  │
//   │  Mức độ: ● Ổn định                               │
//   │                                                  │
//   │  Mô tả ngắn kịch bản                             │
//   │                                                  │
//   │  Các chỉ số biến thiên:                          │
//   │    • Nhịp tim (HR)    →  65 – 75 bpm   ↓ giảm   │
//   │    • SpO2             →  96 – 99 %     ↑ tăng   │
//   │    ...                                           │
//   └──────────────────────────────────────────────────┘
//
// Changes from previous version:
//   - Removed the "Mở thư viện" modal button.
//   - Replaced key-signal chips with a clear signal-variance table.
//   - Replaced Badge component with an inline "Mức độ" text row
//     so severity is readable at a glance without decoding badge colours.
//   - Title rendered at h3 (20 px, bold) directly inside the card body.
// ---------------------------------------------------------------------------

interface ScenarioSelectorProps {
  scenarios: ScenarioOption[];
  selectedScenarioId: string;
  onChange: (scenarioId: string) => void;
  isApplying?: boolean;
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Severity display helpers
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

const DIRECTION_LABEL: Record<string, string> = {
  up: "↑ tăng",
  down: "↓ giảm",
  flat: "→ ổn định",
};

export function ScenarioSelector({
  scenarios,
  selectedScenarioId,
  onChange,
  isApplying = false,
  disabled = false,
}: ScenarioSelectorProps) {
  // Fall scenarios are handled on the Fall Lab page — exclude from inline picker.
  const inlineScenarios = scenarios.filter((scenario) => scenario.category !== "fall");
  const selected = inlineScenarios.find((scenario) => scenario.id === selectedScenarioId) ?? null;

  return (
    <Card header={<strong>Kịch bản mô phỏng</strong>}>
      <div style={{ display: "grid", gap: "16px" }}>
        {/* ── Dropdown ── */}
        <select
          value={selectedScenarioId}
          disabled={disabled || isApplying}
          onChange={(event) => onChange(event.target.value)}
          aria-label="Chọn kịch bản mô phỏng"
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
          {inlineScenarios.length === 0 ? (
            <option value="">Không có kịch bản khả dụng</option>
          ) : (
            inlineScenarios.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {SEVERITY_OPTION_EMOJI[scenario.severity]} {scenario.name}
              </option>
            ))
          )}
        </select>

        {/* ── Detail card — visible after a scenario is chosen ── */}
        {selected ? <ScenarioDetailCard scenario={selected} isApplying={isApplying} /> : null}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// ScenarioDetailCard — the rich content below the dropdown.
// Rendered only when a scenario is selected.
// ---------------------------------------------------------------------------

function ScenarioDetailCard({
  scenario,
  isApplying,
}: {
  scenario: ScenarioOption;
  isApplying: boolean;
}) {
  const dotColor = SEVERITY_DOT[scenario.severity];
  const severityLabel = SEVERITY_LABEL[scenario.severity];
  const severityStyle: React.CSSProperties = {
    color: dotColor,
    fontWeight: 700,
  };

  return (
    <div
      style={{
        padding: "16px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-elevated)",
        border: "1px solid rgba(255,255,255,0.05)",
        display: "grid",
        gap: "12px",
        opacity: isApplying ? 0.6 : 1,
        transition: "opacity 160ms ease",
      }}
    >
      {/* Title row */}
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
        {scenario.name}
      </h3>

      {/* Severity row */}
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
        <span style={severityStyle}>{severityLabel}</span>
      </div>

      {/* Description */}
      {scenario.description ? (
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
      ) : null}

      {/* Key-signal variance table */}
      {scenario.keySignals.length > 0 ? (
        <div style={{ display: "grid", gap: "6px" }}>
          <div
            style={{
              fontSize: "11.5px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.07em",
              color: "var(--text-muted)",
              marginBottom: "2px",
            }}
          >
            Các chỉ số biến thiên
          </div>
          <div
            style={{
              display: "grid",
              gap: "4px",
            }}
          >
            {scenario.keySignals.map((signal, idx) => {
              const dirLabel = signal.direction ? (DIRECTION_LABEL[signal.direction] ?? signal.direction) : null;
              const signalDotColor = SEVERITY_DOT[signal.severity];
              return (
                <div
                  key={`${signal.label}-${idx}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "8px 1fr auto auto",
                    alignItems: "center",
                    gap: "8px",
                    padding: "7px 10px",
                    borderRadius: "var(--radius-md)",
                    background: "rgba(255,255,255,0.03)",
                    fontSize: "13px",
                  }}
                >
                  {/* Severity dot for this signal */}
                  <span
                    style={{
                      width: "7px",
                      height: "7px",
                      borderRadius: "50%",
                      background: signalDotColor,
                      flexShrink: 0,
                    }}
                  />
                  {/* Signal name */}
                  <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                    {signal.label}
                  </span>
                  {/* Target value */}
                  <span
                    style={{
                      color: "var(--text-secondary)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "12.5px",
                    }}
                  >
                    {signal.target ?? "—"}
                  </span>
                  {/* Direction */}
                  {dirLabel ? (
                    <span
                      style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        color: signalDotColor,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {dirLabel}
                    </span>
                  ) : (
                    <span />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
