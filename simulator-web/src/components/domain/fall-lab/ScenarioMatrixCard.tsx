import type { CSSProperties } from "react";
import { CheckCircle2, Circle, XCircle } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import { InfoTooltip } from "./InfoTooltip";
import {
  FALL_VARIANT_CATALOGUE,
  type FallVariantId,
  type FallVariantSpec,
} from "../../../types/fall";

// ---------------------------------------------------------------------------
// ScenarioMatrixCard — Module FA Phase 1 redesign of `<VariantPickerCard/>`.
//
// Renders the 6 fall variants as a comparison table (1 row = 1 variant) so
// the operator can scan expected metrics across scenarios at a glance:
// peak |a|, posture, pre-trigger band, AI band, countdown, push alert.
//
// Hovering / focusing a row shows an evidence checklist below the table —
// the same checklist seen in the HTML mockup (Section A) listing the
// concrete numbers the BE pipeline should produce.  This makes it obvious
// when a verdict deviates from expectation (e.g. AI returns `normal` for
// a `confirmed` inject — peak |a| under 3.0g would jump out immediately).
//
// Inject is fired the moment the operator clicks a row — no pre-confirm
// dialog because that delay doesn't exist on production mobile.
// ---------------------------------------------------------------------------

interface Props {
  disabled: boolean;
  pendingVariant: FallVariantId | null;
  onPick: (variant: FallVariantSpec) => void;
  onHover: (id: FallVariantId | null) => void;
  focalVariant: FallVariantSpec | null;
}

export function ScenarioMatrixCard({
  disabled,
  pendingVariant,
  onPick,
  onHover,
  focalVariant,
}: Props) {
  return (
    <Card
      padding="none"
      header={
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 16px",
            gap: "10px",
            flexWrap: "wrap",
          }}
        >
          <strong style={{ fontSize: "13px" }}>
            Bảng so sánh kịch bản ({FALL_VARIANT_CATALOGUE.length} variants)
          </strong>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            Hover để xem evidence checklist · click để inject ngay
          </span>
        </div>
      }
    >
      <div style={{ overflowX: "auto" }}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Kịch bản</th>
              <th style={thStyle}>Severity</th>
              <th style={thStyle}>Peak |a| <InfoTooltip k="scenarioPeakG" /></th>
              <th style={thStyle}>Posture <InfoTooltip k="scenarioPostureDeg" /></th>
              <th style={thStyle}>Pre-trigger <InfoTooltip k="scenarioPreTrigger" /></th>
              <th style={thStyle}>Inject env <InfoTooltip k="scenarioInjectEnv" /></th>
              <th style={thStyle}>AI band <InfoTooltip k="scenarioAiBand" /></th>
              <th style={thStyle}>Countdown <InfoTooltip k="scenarioCountdown" /></th>
              <th style={thStyle}>Alert <InfoTooltip k="scenarioPushAlert" /></th>
              <th style={{ ...thStyle, textAlign: "right" }}>&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {FALL_VARIANT_CATALOGUE.map((variant) => (
              <ScenarioRow
                key={variant.id}
                variant={variant}
                disabled={disabled}
                pending={pendingVariant === variant.id}
                active={focalVariant?.id === variant.id}
                onPick={onPick}
                onHover={onHover}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border-default)",
          background: "var(--bg-base)",
        }}
      >
        <EvidenceChecklist variant={focalVariant} />
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Row component — keeps the table render side-effect free.
// ---------------------------------------------------------------------------

function ScenarioRow({
  variant,
  disabled,
  pending,
  active,
  onPick,
  onHover,
}: {
  variant: FallVariantSpec;
  disabled: boolean;
  pending: boolean;
  active: boolean;
  onPick: (v: FallVariantSpec) => void;
  onHover: (id: FallVariantId | null) => void;
}) {
  const rowDisabled = disabled || pending;
  return (
    <tr
      style={{
        ...rowStyle,
        background: active ? "var(--accent-cyan-bg)" : undefined,
        boxShadow: active ? "inset 3px 0 0 var(--accent-cyan)" : undefined,
        cursor: rowDisabled ? "not-allowed" : "pointer",
        opacity: rowDisabled && !pending ? 0.55 : 1,
      }}
      onMouseEnter={() => onHover(variant.id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(variant.id)}
      onBlur={() => onHover(null)}
      onClick={() => {
        if (rowDisabled) return;
        onPick(variant);
      }}
      tabIndex={rowDisabled ? -1 : 0}
      aria-disabled={rowDisabled}
      aria-label={`${variant.label} — ${variant.subtitle}`}
    >
      <td style={tdStyle}>
        <strong style={{ fontSize: "12.5px", color: "var(--text-primary)" }}>
          {pending ? "Đang inject…" : variant.label}
        </strong>
        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
          {variant.physicalAction}
        </div>
      </td>
      <td style={tdStyle}>
        <Badge severity={variant.severity}>{variant.severity}</Badge>
      </td>
      <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: "11.5px" }}>
        {variant.expectedPeakG.min.toFixed(1)}–{variant.expectedPeakG.max.toFixed(1)} g
      </td>
      <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: "11.5px" }}>
        {variant.expectedPostureDeg
          ? `${variant.expectedPostureDeg.min}–${variant.expectedPostureDeg.max}°`
          : "—"}
      </td>
      <td style={tdStyle}>
        <Badge severity={preTriggerSeverity(variant.expectedPreTrigger)}>
          {variant.expectedPreTrigger}
        </Badge>
      </td>
      <td style={tdStyle}>
        <Badge severity={variant.injectEnvironment ? "info" : "offline"}>
          {variant.injectEnvironment ? "true" : "false"}
        </Badge>
      </td>
      <td style={tdStyle}>
        <Badge severity={variant.expectedAiBand}>{variant.expectedAiBand}</Badge>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "10.5px", color: "var(--text-secondary)", marginTop: "2px" }}>
          {Math.round(variant.expectedAiProbability.min * 100)}–
          {Math.round(variant.expectedAiProbability.max * 100)}%
        </div>
      </td>
      <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: "11.5px" }}>
        {variant.countdownSec === 0
          ? "0s"
          : `${variant.countdownSec}s${variant.autoResolve ? " · auto" : ""}${!variant.allowsCancel ? " · không huỷ" : ""}`}
      </td>
      <td style={tdStyle}>
        {variant.pushesAlert
          ? <Badge severity="info">webhook</Badge>
          : <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>—</span>}
      </td>
      <td style={{ ...tdStyle, textAlign: "right" }}>
        <span style={{ fontSize: "11px", color: rowDisabled ? "var(--text-muted)" : "var(--accent-cyan)" }}>
          {pending ? "Đang gửi…" : disabled ? "—" : "Inject →"}
        </span>
      </td>
    </tr>
  );
}

function preTriggerSeverity(value: "hard" | "soft" | "none"): "critical" | "warning" | "offline" {
  if (value === "hard") return "critical";
  if (value === "soft") return "warning";
  return "offline";
}

// ---------------------------------------------------------------------------
// Evidence checklist — concrete numbers an operator can use to decide
// "did the BE pipeline actually behave like this variant should?"
// ---------------------------------------------------------------------------

function EvidenceChecklist({ variant }: { variant: FallVariantSpec | null }) {
  if (!variant) {
    return (
      <div
        style={{
          padding: "10px 12px",
          fontSize: "12px",
          color: "var(--text-muted)",
          background: "var(--bg-elevated)",
          border: "1px dashed var(--border-default)",
          borderRadius: "var(--radius-md)",
        }}
      >
        Hover hoặc click một kịch bản để xem evidence checklist (peak g, posture, pre-trigger, AI band kỳ vọng).
      </div>
    );
  }

  const items: { tone: "ok" | "pending" | "fail"; label: string; value: string }[] = [
    {
      tone: "pending",
      label: `Peak |a| trong cửa sổ 50 mẫu phải nằm trong khoảng kỳ vọng`,
      value: `${variant.expectedPeakG.min.toFixed(1)}–${variant.expectedPeakG.max.toFixed(1)} g`,
    },
    {
      tone: "pending",
      label: variant.expectedPostureDeg
        ? `Posture change angle phải nằm trong khoảng`
        : `Posture không phải tín hiệu chính cho variant này`,
      value: variant.expectedPostureDeg
        ? `${variant.expectedPostureDeg.min}–${variant.expectedPostureDeg.max}°`
        : "—",
    },
    {
      tone: "pending",
      label: `Pre-trigger phải fire ở mức`,
      value: variant.expectedPreTrigger.toUpperCase(),
    },
    {
      tone: "pending",
      label: `Inject environment signals (floor_vibration, pressure_mat)`,
      value: variant.injectEnvironment ? "true" : "false",
    },
    {
      tone: "pending",
      label: `AI verdict phải rơi vào band`,
      value: `${variant.expectedAiBand} · ${Math.round(variant.expectedAiProbability.min * 100)}–${Math.round(variant.expectedAiProbability.max * 100)}%`,
    },
    {
      tone: "pending",
      label: variant.countdownSec === 0
        ? `Không countdown — BE không vào fall_countdown`
        : `Countdown ${variant.countdownSec}s${variant.autoResolve ? " (auto-resolve)" : ""}${!variant.allowsCancel ? " · không cho huỷ" : ""}`,
      value: variant.pushesAlert ? "có alert webhook" : "không alert",
    },
  ];

  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <h4 style={checklistTitleStyle}>Evidence checklist · {variant.label}</h4>
      {items.map((item, idx) => (
        <div key={idx} style={checklistRowStyle}>
          {item.tone === "ok"
            ? <CheckCircle2 size={14} style={{ color: "var(--severity-normal)" }} />
            : item.tone === "fail"
            ? <XCircle size={14} style={{ color: "var(--severity-critical)" }} />
            : <Circle size={14} style={{ color: "var(--text-muted)" }} />}
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{item.label}</span>
          <code style={{ fontSize: "11px", color: "var(--text-primary)", textAlign: "right" }}>
            {item.value}
          </code>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles (CSSProperties const blocks; theme via CSS variables)
// ---------------------------------------------------------------------------

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "separate",
  borderSpacing: 0,
  fontSize: "12.5px",
};

const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  background: "var(--bg-base)",
  color: "var(--text-muted)",
  fontWeight: 600,
  fontSize: "10.5px",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  borderBottom: "1px solid var(--border-default)",
  whiteSpace: "nowrap",
};

const tdStyle: CSSProperties = {
  padding: "10px 12px",
  borderBottom: "1px solid var(--border-default)",
  verticalAlign: "middle",
};

const rowStyle: CSSProperties = {
  transition: "background var(--duration-fast) var(--ease-default)",
};

const checklistTitleStyle: CSSProperties = {
  margin: "0 0 6px",
  fontSize: "11px",
  color: "var(--text-secondary)",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};

const checklistRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "18px 1fr auto",
  gap: "8px",
  alignItems: "center",
};
