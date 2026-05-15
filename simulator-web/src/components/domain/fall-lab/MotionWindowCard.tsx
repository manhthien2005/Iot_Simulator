import type { CSSProperties } from "react";
import { useMemo, useState } from "react";
import { Activity, AlertTriangle, ChevronRight } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { Sparkline } from "../../ui/Sparkline";
import { describeFallVariant } from "../../../utils/motionLabels";
import type { MotionLatest } from "../../../types/motion";
import type { FallState } from "../../../types/fall";

interface Props {
  motion: MotionLatest | null;
  fallState: FallState | null;
}

export function MotionWindowCard({ motion, fallState }: Props) {
  const [showDetails, setShowDetails] = useState(false);

  const summary = useMemo(() => {
    if (!motion || motion.accelMag.length === 0) return null;
    const peak = Math.max(...motion.accelMag);
    const mean = motion.accelMag.reduce((a, b) => a + b, 0) / motion.accelMag.length;
    return { peak, mean, count: motion.accelMag.length };
  }, [motion]);

  const variantBadge = describeFallVariant(motion?.fallVariant);
  const isFalling = motion?.activityState?.toLowerCase() === "fall";
  const heroStroke = isFalling ? "var(--severity-critical)" : "var(--accent-cyan)";

  const aiAlignedAt = fallState?.motionWindowRef?.emittedAt;
  const motionAt = motion?.emittedAt;
  const aligned = Boolean(aiAlignedAt && motionAt && aiAlignedAt === motionAt);

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <Activity size={14} />
            <strong>Cửa sổ chuyển động (50 mẫu)</strong>
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
            {variantBadge && <Badge severity="info">{variantBadge}</Badge>}
            {fallState?.aiPrediction?.modelStatus === "ok"
              ? (
                <Badge severity={aligned ? "normal" : "warning"}>
                  {aligned ? "Cùng cửa sổ với AI" : "Cửa sổ mới (sau AI)"}
                </Badge>
              )
              : null}
          </div>
        </div>
      }
    >
      {!motion || !summary
        ? (
          <EmptyState
            icon={Activity}
            title="Chưa có dữ liệu chuyển động"
            description="Phiên đang chạy nhưng chưa có window nào được publish cho thiết bị này."
          />
        )
        : (
          <div style={{ display: "grid", gap: "12px" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "8px",
                padding: "10px 12px",
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <MetricCell label="Đỉnh |a|" value={`${summary.peak.toFixed(2)} m/s²`} highlight={summary.peak >= 20} />
              <MetricCell label="Trung bình |a|" value={`${summary.mean.toFixed(2)} m/s²`} />
              <MetricCell label="Số mẫu" value={`${summary.count}`} />
              <MetricCell
                label="Tần số"
                value={motion.sampleRate ? `${motion.sampleRate} Hz` : "—"}
              />
            </div>
            <Sparkline
              values={motion.accelMag}
              stroke={heroStroke}
              height={84}
              ariaLabel="Gia tốc tổng |a| theo thời gian"
            />
            <button
              type="button"
              onClick={() => setShowDetails((s) => !s)}
              aria-expanded={showDetails}
              style={detailsToggleStyle}
            >
              <ChevronRight
                size={14}
                style={{ transform: showDetails ? "rotate(90deg)" : "none", transition: "transform 200ms" }}
              />
              {showDetails ? "Ẩn chi tiết 6 trục" : "Hiện chi tiết 6 trục"}
            </button>
            {showDetails && (
              <div style={{ display: "grid", gap: "6px", paddingTop: "6px", borderTop: "1px dashed var(--border-default)" }}>
                <TraceRow label="Gia tốc trục X" values={motion.accelX} stroke="var(--text-secondary)" />
                <TraceRow label="Gia tốc trục Y" values={motion.accelY} stroke="var(--text-secondary)" />
                <TraceRow label="Gia tốc trục Z" values={motion.accelZ} stroke="var(--text-secondary)" />
                <TraceRow label="Vận tốc góc trục X" values={motion.gyroX} stroke="var(--severity-warning)" />
                <TraceRow label="Vận tốc góc trục Y" values={motion.gyroY} stroke="var(--severity-warning)" />
                <TraceRow label="Vận tốc góc trục Z" values={motion.gyroZ} stroke="var(--severity-warning)" />
              </div>
            )}
          </div>
        )}
    </Card>
  );
}

function MetricCell({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{label}</span>
      <strong
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "13px",
          color: highlight ? "var(--severity-critical)" : "var(--text-primary)",
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        {highlight && <AlertTriangle size={12} aria-hidden="true" />}
        {value}
      </strong>
    </div>
  );
}

function TraceRow({ label, values, stroke }: { label: string; values: number[]; stroke: string }) {
  const last = values[values.length - 1];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "150px 1fr 70px", gap: "8px", alignItems: "center" }}>
      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{label}</span>
      <Sparkline values={values} stroke={stroke} height={22} ariaLabel={`Trace ${label}`} />
      <span
        style={{ fontFamily: "var(--font-mono)", fontSize: "12px", textAlign: "right", color: "var(--text-secondary)" }}
      >
        {last !== undefined ? last.toFixed(2) : "—"}
      </span>
    </div>
  );
}

const detailsToggleStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  alignSelf: "flex-start",
  padding: "6px 10px",
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--border-default)",
  background: "transparent",
  color: "var(--text-secondary)",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 500,
};
