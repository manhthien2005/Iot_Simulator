import type { CSSProperties, ReactNode } from "react";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  CpuIcon,
  Info,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { aiLabelText, aiStatusLabel, fallSeverityPalette } from "../../../utils/severity";
import type {
  AIPrediction,
  CountdownPolicy,
  FallState,
  FallStateValue,
} from "../../../types/fall";

interface Props {
  fallState: FallState | null;
  disabled: boolean;
  cancelling: boolean;
  onCancel: () => void;
}

export function AIVerdictPanel({ fallState, disabled, cancelling, onCancel }: Props) {
  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <Brain size={14} />
            <strong>AI verdict + countdown</strong>
          </span>
          <FallStateBadge value={fallState?.fallState ?? "idle"} />
        </div>
      }
    >
      <div style={{ display: "grid", gap: "12px" }}>
        <AIVerdictBlock prediction={fallState?.aiPrediction ?? null} />
        <CountdownBlock
          fallState={fallState}
          disabled={disabled || cancelling}
          cancelling={cancelling}
          onCancel={onCancel}
        />
      </div>
    </Card>
  );
}

function FallStateBadge({ value }: { value: FallStateValue }) {
  const map: Record<FallStateValue, { label: string; severity: "normal" | "warning" | "critical" | "offline" | "info" }> = {
    idle:           { label: "Sẵn sàng",        severity: "offline" },
    fall_detected:  { label: "Đã ghi nhận",      severity: "warning" },
    fall_countdown: { label: "Đang đếm ngược",   severity: "warning" },
    sos_active:     { label: "SOS kích hoạt",    severity: "critical" },
    fall_resolved:  { label: "Đã hủy / phục hồi", severity: "normal" },
  };
  const entry = map[value];
  return <Badge severity={entry.severity}>{entry.label}</Badge>;
}

function AIVerdictBlock({ prediction }: { prediction: AIPrediction | null }) {
  if (!prediction) {
    return (
      <div style={emptyVerdictStyle}>
        <Info size={14} style={{ color: "var(--text-muted)" }} />
        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
          Chưa có verdict — inject một kịch bản té ngã ở bên trái để nhận AI prediction.
        </span>
      </div>
    );
  }

  const probabilityPct = Math.round(prediction.probability * 100);
  const confidencePct = Math.round(prediction.confidence * 100);
  const palette = fallSeverityPalette(prediction.riskBand);

  if (prediction.modelStatus !== "ok") {
    return (
      <div
        style={{
          display: "grid",
          gap: "6px",
          padding: "10px 12px",
          background: "var(--bg-elevated)",
          border: "1px dashed var(--border-default)",
          borderRadius: "var(--radius-md)",
        }}
      >
        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <CpuIcon size={14} style={{ color: "var(--text-muted)" }} />
          <strong style={{ fontSize: "13px" }}>{aiStatusLabel(prediction.modelStatus)}</strong>
        </div>
        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
          {prediction.explanationSummary
            ?? "AI không trả về verdict — hệ thống đang dựa vào pre-trigger fallback."}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gap: "10px",
        padding: "12px",
        background: palette.bg,
        border: `1px solid ${palette.border}`,
        borderRadius: "var(--radius-md)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {prediction.riskBand === "critical"
            ? <ShieldAlert size={18} style={{ color: palette.text }} />
            : prediction.riskBand === "warning"
            ? <AlertTriangle size={18} style={{ color: palette.text }} />
            : <ShieldCheck size={18} style={{ color: palette.text }} />}
          <strong style={{ fontSize: "14px", color: palette.text }}>
            {aiLabelText(prediction.label)}
          </strong>
        </div>
        <Badge severity={prediction.riskBand}>{prediction.riskBand}</Badge>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }}>
        <ProbabilityMeter label="Xác suất té ngã" value={probabilityPct} tone={prediction.riskBand} />
        <ProbabilityMeter label="Độ tin cậy" value={confidencePct} tone={prediction.riskBand} />
      </div>
      {prediction.explanationSummary
        ? <p style={{ margin: 0, fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            {prediction.explanationSummary}
          </p>
        : null}
      {prediction.topFeatures.length > 0
        ? (
          <div style={{ display: "grid", gap: "6px", marginTop: "4px" }}>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Đặc trưng đóng góp lớn nhất
            </span>
            {prediction.topFeatures.map((feature, idx) => (
              <div
                key={`${feature.featureName}-${idx}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: "8px",
                  alignItems: "center",
                  padding: "6px 8px",
                  background: "rgba(255,255,255,0.03)",
                  borderRadius: "var(--radius-sm)",
                  borderLeft: `3px solid ${fallSeverityPalette(feature.severity).text}`,
                }}
              >
                <span style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                  {feature.vietnameseExplanation || feature.featureName}
                </span>
                <code style={{ fontSize: "11px", color: fallSeverityPalette(feature.severity).text }}>
                  {feature.contribution >= 0 ? "+" : ""}
                  {feature.contribution.toFixed(3)}
                </code>
              </div>
            ))}
          </div>
        )
        : null}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", fontSize: "11px", color: "var(--text-muted)" }}>
        <span>
          Ghi nhận lúc:{" "}
          <code style={{ color: "var(--text-secondary)" }}>
            {new Date(prediction.predictedAt).toLocaleTimeString("vi-VN", { hour12: false })}
          </code>
        </span>
        {prediction.requiresAttention ? <Badge severity="warning">Cần chú ý</Badge> : null}
        {prediction.highPriorityAlert ? <Badge severity="critical">High priority</Badge> : null}
      </div>
    </div>
  );
}

function ProbabilityMeter({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "normal" | "warning" | "critical";
}) {
  const palette = fallSeverityPalette(tone);
  return (
    <div style={{ display: "grid", gap: "4px" }}>
      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{label}</span>
      <div
        style={{
          height: "8px",
          background: "var(--bg-base)",
          border: "1px solid var(--border-default)",
          borderRadius: "999px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.max(0, Math.min(100, value))}%`,
            height: "100%",
            background: palette.text,
          }}
        />
      </div>
      <strong style={{ fontFamily: "var(--font-mono)", fontSize: "13px", color: palette.text }}>
        {value}%
      </strong>
    </div>
  );
}

function CountdownBlock({
  fallState,
  disabled,
  cancelling,
  onCancel,
}: {
  fallState: FallState | null;
  disabled: boolean;
  cancelling: boolean;
  onCancel: () => void;
}) {
  if (!fallState) return null;
  const { countdownRemainingSec, countdownTotalSec, countdownPolicy } = fallState;
  const inCountdown = countdownTotalSec > 0 && fallState.deviceState === "fall_countdown";

  if (!inCountdown) {
    if (fallState.fallState === "fall_resolved" && countdownRemainingSec === 0) {
      return (
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 12px",
            fontSize: "12px",
            color: "var(--severity-normal)",
            background: "rgba(34,197,94,0.08)",
            border: "1px solid rgba(34,197,94,0.30)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <CheckCircle2 size={14} />
          BE đã ra khỏi fall_countdown — quay về streaming.
        </div>
      );
    }
    return null;
  }

  const policy: CountdownPolicy | null = countdownPolicy;
  const percent = countdownTotalSec > 0
    ? Math.max(0, Math.min(100, (countdownRemainingSec / countdownTotalSec) * 100))
    : 0;
  const critical = countdownRemainingSec <= 10;
  const palette = fallSeverityPalette(critical ? "critical" : "warning");

  return (
    <div
      style={{
        display: "grid",
        gap: "8px",
        padding: "12px",
        background: palette.bg,
        border: `1px solid ${palette.border}`,
        borderRadius: "var(--radius-md)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontSize: "13px" }}>SOS countdown đang chạy</strong>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "13px", color: palette.text }}>
          {countdownRemainingSec} / {countdownTotalSec}s
        </span>
      </div>
      <div style={{ height: "8px", background: "var(--bg-base)", borderRadius: "999px", overflow: "hidden" }}>
        <div
          style={{
            width: `${percent}%`,
            height: "100%",
            background: palette.text,
            transition: "width 0.4s linear",
          }}
        />
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", fontSize: "11px" }}>
        {policy?.autoResolve
          ? <PolicyChip icon={<CheckCircle2 size={12} />} label="Sẽ tự huỷ" tone="normal" />
          : null}
        {policy && !policy.allowsCancel
          ? <PolicyChip icon={<XCircle size={12} />} label="Không cho huỷ" tone="critical" />
          : null}
      </div>
      {policy?.allowsCancel
        ? (
          <Button variant="secondary" disabled={disabled} onClick={onCancel}>
            {cancelling ? "Đang gửi…" : "Tôi ổn — Hủy SOS"}
          </Button>
        )
        : (
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            Variant này không cho phép huỷ — countdown sẽ chạy đến 0.
          </span>
        )}
    </div>
  );
}

function PolicyChip({
  icon,
  label,
  tone = "normal",
}: {
  icon: ReactNode;
  label: string;
  tone?: "normal" | "warning" | "critical" | "offline";
}) {
  const palette = fallSeverityPalette(tone);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "3px 8px",
        fontSize: "11px",
        borderRadius: "var(--radius-full)",
        border: `1px solid ${palette.border}`,
        background: "var(--bg-elevated)",
        color: palette.text,
      }}
    >
      {icon}
      {label}
    </span>
  );
}

const emptyVerdictStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  padding: "10px 12px",
  background: "var(--bg-elevated)",
  border: "1px dashed var(--border-default)",
  borderRadius: "var(--radius-md)",
};
