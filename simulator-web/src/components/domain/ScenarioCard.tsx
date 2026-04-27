import { useState } from "react";
import { ArrowRight, ChevronDown, ChevronUp } from "lucide-react";
import type { CSSProperties } from "react";
import type {
  KeySignal,
  KeySignalDirection,
  ScenarioCategory,
  ScenarioFollowUp,
  ScenarioOption,
  ScenarioSeverity,
} from "../../types/scenario";
import { Card } from "../ui/Card";
import { useConfirm } from "../../hooks/useConfirm";

// ---------------------------------------------------------------------------
// ScenarioCard — Module H Block 3 redesign.
//
// Compact-card with expand-on-click.  The previous version stacked six
// info blocks per card (header, body, signals, follow-up, expected
// outcome, active-pill, CTA) which made the Scenarios grid feel like a
// reference manual rather than a launcher.  This iteration:
//
//   * Default (collapsed) state is a fixed-height card with only the
//     header (severity + category badges), name, two-line description
//     clamp, and the footer row (toggle + "Chạy" CTA).  Every card in
//     the grid renders at the same height so the layout looks tidy.
//
//   * Clicking "Xem chi tiết" expands the card in place, revealing the
//     same data the v1 card always rendered (key signals, follow-up
//     side-effect strip, expected outcome callout, active-devices pill).
//
// All BE-truthful data is preserved — the redesign is purely visual.
// Critical-severity scenarios still gate their "Chạy" click with a
// `useConfirm` dialog (Module G.5).
// ---------------------------------------------------------------------------

interface ScenarioCardProps {
  scenario: ScenarioOption;
  /** Number of devices that currently have this scenario applied. */
  activeDeviceCount: number;
  onRun: (scenarioId: string) => void;
}

const COLLAPSED_MIN_HEIGHT = 196;

export function ScenarioCard({ scenario, activeDeviceCount, onRun }: ScenarioCardProps) {
  const [expanded, setExpanded] = useState(false);
  // Module G.5 — confirm before navigating to apply a critical scenario.
  // The actual mutation happens in `<SessionRunnerPage/>::changeScenario`
  // which also confirms; this is the *front-line* guard so a misclick
  // here doesn't navigate away from the Scenarios page at all.
  const [confirm, confirmDialog] = useConfirm();

  async function handleRun() {
    if (scenario.severity === "critical") {
      const ok = await confirm({
        severity: "critical",
        title: `Chạy kịch bản "${scenario.name}"?`,
        description: `Kịch bản này được đánh dấu nguy cấp. Khi áp dụng, BE sẽ kích hoạt: ${
          scenario.followUp.map((f) => f.detail).join(", ") || "không có side-effect bổ sung"
        }.`,
        confirmLabel: "Mở Phiên mô phỏng",
      });
      if (!ok) return;
    }
    onRun(scenario.id);
  }

  return (
    <Card hoverable>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          minHeight: expanded ? undefined : `${COLLAPSED_MIN_HEIGHT}px`,
        }}
      >
        <Header scenario={scenario} />

        <h3
          style={{
            margin: 0,
            fontSize: "16px",
            lineHeight: 1.3,
            display: "-webkit-box",
            WebkitLineClamp: 1,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            wordBreak: "break-word",
          }}
        >
          {scenario.name}
        </h3>

        <p
          style={{
            margin: 0,
            color: "var(--text-secondary)",
            fontSize: "13px",
            lineHeight: 1.55,
            display: "-webkit-box",
            WebkitLineClamp: expanded ? undefined : 2,
            WebkitBoxOrient: "vertical",
            overflow: expanded ? "visible" : "hidden",
            // Spacer fills the remaining vertical space when collapsed,
            // so all cards align their footer row to the bottom.
            flex: expanded ? "0 0 auto" : 1,
          }}
        >
          {scenario.description}
        </p>

        {expanded && <ExpandedDetails scenario={scenario} activeDeviceCount={activeDeviceCount} />}

        <CardFooter
          expanded={expanded}
          onToggleExpanded={() => setExpanded((prev) => !prev)}
          onRun={handleRun}
          scenarioName={scenario.name}
        />
      </div>
      {confirmDialog}
    </Card>
  );
}

// ── Header ───────────────────────────────────────────────────────────────

function Header({ scenario }: { scenario: ScenarioOption }) {
  const tone = SEVERITY_TONES[scenario.severity];
  const catTone = CATEGORY_TONES[scenario.category];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
      <span
        style={{
          ...badgeBaseStyle,
          border: `1px solid ${tone.border}`,
          background: tone.bg,
          color: tone.fg,
        }}
        aria-label={`Mức nghiêm trọng: ${SEVERITY_LABEL[scenario.severity]}`}
      >
        {SEVERITY_LABEL[scenario.severity]}
      </span>
      <span
        style={{
          ...badgeBaseStyle,
          border: `1px solid ${catTone.border}`,
          background: catTone.bg,
          color: catTone.fg,
        }}
      >
        {CATEGORY_LABEL[scenario.category]}
      </span>
    </div>
  );
}

// ── Footer ───────────────────────────────────────────────────────────────

function CardFooter({
  expanded,
  onToggleExpanded,
  onRun,
  scenarioName,
}: {
  expanded: boolean;
  onToggleExpanded: () => void;
  onRun: () => void;
  scenarioName: string;
}) {
  return (
    <div style={footerRowStyle}>
      <button
        type="button"
        onClick={onToggleExpanded}
        aria-expanded={expanded}
        aria-label={`${expanded ? "Ẩn chi tiết" : "Xem chi tiết"} kịch bản ${scenarioName}`}
        style={secondaryButtonStyle}
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {expanded ? "Ẩn chi tiết" : "Xem chi tiết"}
      </button>
      <button
        type="button"
        onClick={onRun}
        aria-label={`Chạy kịch bản ${scenarioName} trong phiên`}
        style={ctaStyle}
      >
        Chạy <ArrowRight size={14} />
      </button>
    </div>
  );
}

// ── Expanded body ────────────────────────────────────────────────────────

function ExpandedDetails({
  scenario,
  activeDeviceCount,
}: {
  scenario: ScenarioOption;
  activeDeviceCount: number;
}) {
  return (
    <div style={{ display: "grid", gap: "10px" }}>
      {scenario.keySignals.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {scenario.keySignals.map((signal, index) => (
            <KeySignalChip key={`${scenario.id}:${index}`} signal={signal} />
          ))}
        </div>
      )}

      {scenario.followUp.length > 0 && <FollowUpStrip items={scenario.followUp} />}

      <div style={expectedOutcomeBoxStyle}>
        <div style={expectedOutcomeLabelStyle}>Kết quả kỳ vọng</div>
        <div style={{ marginTop: "6px", fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
          {scenario.expectedOutcome}
        </div>
      </div>

      {activeDeviceCount > 0 && (
        <div style={activePillStyle}>
          Đang áp dụng cho <strong>{activeDeviceCount}</strong> thiết bị
        </div>
      )}
    </div>
  );
}

// ── Key signal chip ──────────────────────────────────────────────────────

function KeySignalChip({ signal }: { signal: KeySignal }) {
  const tone = SEVERITY_TONES[signal.severity];
  return (
    <span
      title={signal.target ?? undefined}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "3px 8px",
        borderRadius: "var(--radius-full)",
        background: tone.bg,
        border: `1px solid ${tone.border}`,
        color: tone.fg,
        fontSize: "11px",
        fontFamily: "var(--font-mono)",
      }}
    >
      {signal.direction && <DirectionGlyph direction={signal.direction} />}
      {signal.label}
    </span>
  );
}

function DirectionGlyph({ direction }: { direction: KeySignalDirection }) {
  if (direction === "up") return <span aria-label="tăng">▲</span>;
  if (direction === "down") return <span aria-label="giảm">▼</span>;
  return <span aria-label="ổn định">●</span>;
}

// ── Follow-up strip ──────────────────────────────────────────────────────

function FollowUpStrip({ items }: { items: ScenarioFollowUp[] }) {
  return (
    <div style={followUpBoxStyle}>
      <div style={followUpLabelStyle}>Side-effect khi áp dụng</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
        {items.map((item, index) => (
          <span
            key={`${item.kind}:${index}`}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "3px 8px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-base)",
              border: "1px solid var(--border-default)",
              fontSize: "11px",
              fontFamily: "var(--font-mono)",
              color: "var(--text-primary)",
            }}
          >
            <strong style={{ color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              {FOLLOW_UP_LABEL[item.kind]}
            </strong>
            <span>{item.detail}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Tones / labels ───────────────────────────────────────────────────────

interface Tone {
  fg: string;
  bg: string;
  border: string;
}

const SEVERITY_TONES: Record<ScenarioSeverity, Tone> = {
  normal: {
    fg: "var(--severity-normal)",
    bg: "rgba(34,197,94,0.12)",
    border: "rgba(34,197,94,0.35)",
  },
  warning: {
    fg: "var(--severity-warning)",
    bg: "rgba(245,158,11,0.16)",
    border: "rgba(245,158,11,0.40)",
  },
  critical: {
    fg: "var(--severity-critical)",
    bg: "rgba(239,68,68,0.14)",
    border: "rgba(239,68,68,0.45)",
  },
};

const SEVERITY_LABEL: Record<ScenarioSeverity, string> = {
  normal: "Bình thường",
  warning: "Cảnh báo",
  critical: "Nguy cấp",
};

const CATEGORY_TONES: Record<ScenarioCategory, Tone> = {
  vitals: {
    fg: "var(--accent-cyan)",
    bg: "rgba(6,182,212,0.20)",
    border: "rgba(6,182,212,0.35)",
  },
  fall: {
    fg: "var(--severity-critical)",
    bg: "rgba(239,68,68,0.20)",
    border: "rgba(239,68,68,0.35)",
  },
  sleep: {
    fg: "#8B5CF6",
    bg: "rgba(139,92,246,0.20)",
    border: "rgba(139,92,246,0.40)",
  },
  risk: {
    fg: "var(--severity-warning)",
    bg: "rgba(245,158,11,0.20)",
    border: "rgba(245,158,11,0.35)",
  },
};

const CATEGORY_LABEL: Record<ScenarioCategory, string> = {
  vitals: "Sinh hiệu",
  fall: "Té ngã",
  sleep: "Giấc ngủ",
  risk: "Rủi ro",
};

const FOLLOW_UP_LABEL: Record<ScenarioFollowUp["kind"], string> = {
  fall_event: "Fall",
  risk_inject: "Risk",
  sleep_phase: "Sleep",
  wake: "Wake",
};

// ── Styles ───────────────────────────────────────────────────────────────

const badgeBaseStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  whiteSpace: "nowrap",
  borderRadius: "var(--radius-full)",
  padding: "2px 8px",
  fontSize: "11px",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  fontWeight: 600,
};

const expectedOutcomeBoxStyle: CSSProperties = {
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "10px",
  background: "var(--bg-base)",
};

const expectedOutcomeLabelStyle: CSSProperties = {
  fontSize: "11px",
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const followUpBoxStyle: CSSProperties = {
  border: "1px dashed var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "8px 10px",
  background: "var(--bg-elevated)",
};

const followUpLabelStyle: CSSProperties = {
  fontSize: "10px",
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const activePillStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  padding: "4px 10px",
  borderRadius: "var(--radius-full)",
  background: "rgba(6,182,212,0.10)",
  border: "1px solid rgba(6,182,212,0.30)",
  color: "var(--accent-cyan)",
  fontSize: "12px",
  width: "fit-content",
};

// Footer row holds two same-size buttons side-by-side (Xem chi tiết +
// Chạy).  Both share `BUTTON_HEIGHT` so the visual rhythm stays tidy
// across the grid even though their content differs.
const BUTTON_HEIGHT = 36;

const footerRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: "8px",
  marginTop: "auto",
};

const buttonBaseStyle: CSSProperties = {
  height: `${BUTTON_HEIGHT}px`,
  borderRadius: "var(--radius-md)",
  fontWeight: 600,
  fontSize: "13px",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  cursor: "pointer",
  transition:
    "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
};

const secondaryButtonStyle: CSSProperties = {
  ...buttonBaseStyle,
  border: "1px solid var(--border-default)",
  background: "transparent",
  color: "var(--text-secondary)",
};

const ctaStyle: CSSProperties = {
  ...buttonBaseStyle,
  border: "1px solid var(--accent-cyan)",
  background: "rgba(6,182,212,0.12)",
  color: "var(--accent-cyan)",
};
