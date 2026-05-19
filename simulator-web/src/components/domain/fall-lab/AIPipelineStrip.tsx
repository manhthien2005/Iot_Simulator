import type { CSSProperties, ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Clock, MinusCircle, XCircle } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import type { FallState, FallVariantSpec } from "../../../types/fall";

// ---------------------------------------------------------------------------
// AIPipelineStrip — Module FA Phase 1, Section B of the Fall Lab.
//
// 4-stage horizontal visualizer of the fall AI pipeline:
//
//   1) Motion window 50 mẫu (BE-derived)
//   2) Pre-trigger evaluate    (Phase 1: derive from motion;
//                               Phase 2: read from FallState.preTriggerResult)
//   3) Model API /predict      (BE-derived from FallState.aiPrediction)
//   4) Verdict + countdown     (BE-derived; downstream of model API)
//
// Each stage renders a status icon (ok / fail / pending / skipped) plus
// a few key/value rows so the operator sees, at a glance, *why* a verdict
// came out the way it did — instead of staring at a single percentage and
// wondering whether the pre-trigger even fired.
//
// During Phase 1 the Pre-trigger stage derives from the motion window
// (peak |a| vs the 3.0g hard / 2.5g soft thresholds embedded here).  This
// is a temporary derive while the BE schema (Phase 2) lands; once
// `FallState.preTriggerResult` exists we'll switch to BE-truth.
// ---------------------------------------------------------------------------

interface Props {
  fallState: FallState | null;
  motionPeakG: number | null;
  motionSampleCount: number | null;
  motionSampleRate: number | null;
  expectedVariant: FallVariantSpec | null;
}

export function AIPipelineStrip({
  fallState,
  motionPeakG,
  motionSampleCount,
  motionSampleRate,
  expectedVariant,
}: Props) {
  const window = computeWindowStage(motionSampleCount, motionSampleRate, fallState);
  const preTrigger = computePreTriggerStage(motionPeakG, expectedVariant);
  const modelApi = computeModelApiStage(fallState);
  const verdict = computeVerdictStage(fallState);

  return (
    <Card
      padding="none"
      header={
        <div style={headerStyle}>
          <strong style={{ fontSize: "13px" }}>
            Pipeline đánh giá: motion window → pre-trigger → model API → verdict
          </strong>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            BE-derived · stage 2 sẽ chuyển sang BE-truth ở Phase 2
          </span>
        </div>
      }
    >
      <div style={stripStyle}>
        <Stage num={1} title="Motion window 50 mẫu" data={window} />
        <Stage num={2} title="Pre-trigger evaluate" data={preTrigger} />
        <Stage num={3} title="Model API /predict" data={modelApi} />
        <Stage num={4} title="Verdict + countdown" data={verdict} />
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Stage shape + renderer
// ---------------------------------------------------------------------------

type StageStatus = "ok" | "fail" | "pending" | "skip";

interface StageData {
  status: StageStatus;
  rows: { label: string; value: ReactNode }[];
}

function Stage({ num, title, data }: { num: number; title: string; data: StageData }) {
  return (
    <div style={{ ...stageStyle, ...stageBgStyle(data.status) }}>
      <div style={stageHeadStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={stageNumStyle}>{num}</span>
          <span style={{ fontSize: "13px", fontWeight: 600 }}>{title}</span>
        </div>
        <StatusIcon status={data.status} />
      </div>
      <div style={{ display: "grid", gap: "4px" }}>
        {data.rows.map((row, idx) => (
          <div key={idx} style={kvRowStyle}>
            <span style={{ color: "var(--text-muted)" }}>{row.label}</span>
            <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: StageStatus }) {
  if (status === "ok") return <CheckCircle2 size={16} style={{ color: "var(--severity-normal)" }} />;
  if (status === "fail") return <XCircle size={16} style={{ color: "var(--severity-critical)" }} />;
  if (status === "pending") return <Clock size={16} style={{ color: "var(--severity-warning)" }} />;
  return <MinusCircle size={16} style={{ color: "var(--text-muted)" }} />;
}

// ---------------------------------------------------------------------------
// Stage data computation — Phase 1 derives from FE state; Phase 2 will
// swap stage 2 for `FallState.preTriggerResult` from the BE.
// ---------------------------------------------------------------------------

function computeWindowStage(
  sampleCount: number | null,
  sampleRate: number | null,
  fallState: FallState | null,
): StageData {
  const haveWindow = sampleCount != null && sampleCount >= 50;
  const ref = fallState?.motionWindowRef ?? null;
  return {
    status: haveWindow ? "ok" : sampleCount != null ? "fail" : "pending",
    rows: [
      { label: "Sample count", value: sampleCount != null ? `${sampleCount} / 50` : "—" },
      { label: "Sample rate", value: sampleRate ? `${sampleRate} Hz` : "—" },
      { label: "Emitted at", value: ref?.emittedAt ? formatTime(ref.emittedAt) : "—" },
      { label: "Variant", value: ref?.fallVariant ?? "—" },
    ],
  };
}

// Pre-trigger thresholds from `pre_model_trigger/fall_pipeline_wrist_config.json`
// stage_1_pretrigger. Hard 3.0g, soft 2.5g. Mirrored here for FE derive
// during Phase 1; replaced by BE evidence in Phase 2.
const HARD_THRESHOLD_G = 3.0;
const SOFT_THRESHOLD_G = 2.5;

function computePreTriggerStage(
  peakG: number | null,
  expected: FallVariantSpec | null,
): StageData {
  if (peakG == null) {
    return {
      status: "pending",
      rows: [
        { label: "Trigger type", value: "—" },
        { label: "Peak |a|", value: "chưa có dữ liệu" },
        { label: "Ngưỡng hard", value: `${HARD_THRESHOLD_G.toFixed(1)} g` },
        { label: "Ngưỡng soft", value: `${SOFT_THRESHOLD_G.toFixed(1)} g` },
      ],
    };
  }
  const fired: "hard" | "soft" | "none" =
    peakG >= HARD_THRESHOLD_G ? "hard" : peakG >= SOFT_THRESHOLD_G ? "soft" : "none";
  const matchesExpectation = expected ? expected.expectedPreTrigger === fired : true;
  return {
    status: fired === "none" ? "skip" : matchesExpectation ? "ok" : "fail",
    rows: [
      {
        label: "Trigger type",
        value: <Badge severity={badgeForPreTrigger(fired)}>{fired.toUpperCase()}</Badge>,
      },
      {
        label: "Peak |a| đo được",
        value: `${peakG.toFixed(2)} g`,
      },
      {
        label: "Vs ngưỡng hard",
        value: `${HARD_THRESHOLD_G.toFixed(1)} g`,
      },
      {
        label: "Vs ngưỡng soft",
        value: `${SOFT_THRESHOLD_G.toFixed(1)} g`,
      },
    ],
  };
}

function computeModelApiStage(fallState: FallState | null): StageData {
  const ai = fallState?.aiPrediction ?? null;
  if (!ai) {
    return {
      status: "pending",
      rows: [
        { label: "Endpoint", value: "8001/api/v1/fall/predict" },
        { label: "Status", value: "chưa có verdict" },
        { label: "Failure reason", value: "—" },
        { label: "Predicted at", value: "—" },
      ],
    };
  }
  const isOk = ai.modelStatus === "ok" && ai.failureReason === "ok";
  return {
    status: isOk ? "ok" : ai.modelStatus === "skipped" ? "skip" : "fail",
    rows: [
      { label: "Endpoint", value: "8001/api/v1/fall/predict" },
      {
        label: "Status",
        value: <Badge severity={badgeForModelStatus(ai.modelStatus)}>{ai.modelStatus}</Badge>,
      },
      { label: "Failure reason", value: ai.failureReason === "ok" ? "—" : ai.failureReason },
      { label: "Predicted at", value: formatTime(ai.predictedAt) },
    ],
  };
}

function computeVerdictStage(fallState: FallState | null): StageData {
  const ai = fallState?.aiPrediction ?? null;
  const fsm = fallState?.fallState ?? null;
  if (!ai || !fsm) {
    return {
      status: "pending",
      rows: [
        { label: "Label", value: "—" },
        { label: "Probability", value: "—" },
        { label: "Countdown", value: "—" },
        { label: "FSM state", value: "—" },
      ],
    };
  }
  const isCountdown = fsm === "fall_countdown";
  return {
    status: isCountdown ? "pending" : ai.riskBand === "critical" ? "ok" : "ok",
    rows: [
      {
        label: "Label",
        value: <Badge severity={badgeForBand(ai.riskBand)}>{ai.label}</Badge>,
      },
      { label: "Probability", value: `${Math.round(ai.probability * 100)}%` },
      {
        label: "Countdown",
        value: fallState?.countdownTotalSec
          ? `${fallState.countdownRemainingSec} / ${fallState.countdownTotalSec}s`
          : "—",
      },
      { label: "FSM state", value: <Badge severity={badgeForFsm(fsm)}>{fsm}</Badge> },
    ],
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("vi-VN", { hour12: false });
  } catch {
    return "—";
  }
}

function badgeForPreTrigger(value: "hard" | "soft" | "none"): "critical" | "warning" | "offline" {
  if (value === "hard") return "critical";
  if (value === "soft") return "warning";
  return "offline";
}

function badgeForModelStatus(status: string): "normal" | "warning" | "critical" | "offline" {
  if (status === "ok") return "normal";
  if (status === "skipped") return "offline";
  return "critical";
}

function badgeForBand(band: string): "normal" | "warning" | "critical" {
  if (band === "critical") return "critical";
  if (band === "warning") return "warning";
  return "normal";
}

function badgeForFsm(fsm: string): "normal" | "warning" | "critical" | "offline" {
  if (fsm === "sos_active") return "critical";
  if (fsm === "fall_countdown" || fsm === "fall_detected") return "warning";
  if (fsm === "fall_resolved") return "normal";
  return "offline";
}

function stageBgStyle(status: StageStatus): CSSProperties {
  if (status === "ok") return { background: "rgba(34,197,94,0.04)" };
  if (status === "fail") return { background: "rgba(239,68,68,0.05)" };
  if (status === "skip") return { background: "rgba(107,114,128,0.05)" };
  return {};
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "12px 16px",
  gap: "10px",
  flexWrap: "wrap",
};

const stripStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
  gap: 0,
};

const stageStyle: CSSProperties = {
  padding: "14px 16px",
  borderRight: "1px solid var(--border-default)",
  display: "grid",
  gap: "8px",
};

const stageHeadStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
};

const stageNumStyle: CSSProperties = {
  width: "22px",
  height: "22px",
  borderRadius: "50%",
  background: "var(--bg-base)",
  border: "1px solid var(--border-default)",
  display: "grid",
  placeItems: "center",
  fontSize: "11px",
  fontWeight: 700,
  color: "var(--text-secondary)",
};

const kvRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr auto",
  gap: "8px",
  padding: "2px 0",
  fontSize: "11px",
  alignItems: "center",
};

// Suppress unused import warning — AlertTriangle is reserved for future
// "expectation mismatch" badge (Phase 2/3 scope).
void AlertTriangle;
