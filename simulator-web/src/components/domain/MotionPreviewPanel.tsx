import { memo, useMemo, useState } from "react";
import { Activity, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import type { CSSProperties } from "react";
import type { SimulatedDevice } from "../../types/device";
import type { MotionLatest } from "../../types/motion";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Sparkline } from "../ui/Sparkline";
import { useLatestMotion } from "../../hooks/useLatestMotion";
import {
  PEAK_ACCEL_WARN_THRESHOLD,
  describeActivity,
  describeFallVariant,
} from "../../utils/motionLabels";

// ---------------------------------------------------------------------------
// MotionPreviewPanel — Module H Block 2 simplification.
//
// Operator-friendly default + technical-detail collapse.  The previous
// version dumped 7 traces (|a|, ax, ay, az, gx, gy, gz) into the panel
// at all times, which read like a debugger view rather than a session
// monitor.  Now the default surface is:
//
//   * Vietnamized activity pill (Nghỉ ngơi / Đi bộ / Chạy / TÉ NGÃ / …)
//   * One large `|a|` sparkline tinted by severity
//   * Three metrics: Peak |a|, Mean |a|, Số mẫu
//   * Timestamp of the last published tick
//   * "Chi tiết kỹ thuật ▾" toggle
//
// The expanded view restores the 6 axis traces plus sample-rate, with
// Vietnamese labels for each ("Gia tốc trục X" instead of "ax", …).  No
// data is fabricated — when the simulator hasn't pushed a tick yet we
// still render the explicit empty state.
// ---------------------------------------------------------------------------

interface MotionPreviewPanelProps {
  selectedDevice: SimulatedDevice | null;
  /** Active session id — needed to scope the BE motion lookup. */
  sessionId: string | null;
}

export const MotionPreviewPanel = memo(function MotionPreviewPanel({
  selectedDevice,
  sessionId,
}: MotionPreviewPanelProps) {
  const deviceId = selectedDevice?.id ?? null;
  const { data: motion, isLoading } = useLatestMotion(sessionId, deviceId);
  const [showDetails, setShowDetails] = useState(false);

  if (!selectedDevice) {
    return (
      <Card header={<strong>Xem trước chuyển động</strong>}>
        <EmptyState
          icon={Activity}
          title="Chưa chọn thiết bị"
          description="Chọn một thiết bị đang bật SIM để xem dữ liệu chuyển động thật từ phiên hiện tại."
        />
      </Card>
    );
  }

  const hasData = Boolean(motion && motion.accelMag.length > 0);

  return (
    <Card header={<MotionHeader selectedDevice={selectedDevice} motion={motion ?? null} />}>
      {hasData && motion ? (
        <MotionBody
          motion={motion}
          showDetails={showDetails}
          onToggleDetails={() => setShowDetails((prev) => !prev)}
        />
      ) : (
        <EmptyState
          icon={Activity}
          title={isLoading ? "Đang chờ tick…" : "Chưa có dữ liệu chuyển động"}
          description={
            isLoading
              ? "Đang đợi tick đầu tiên của phiên — số liệu sẽ hiển thị ngay khi simulator publish."
              : "Phiên đã chạy nhưng simulator chưa publish window chuyển động cho thiết bị này. Hãy đảm bảo phiên đang ở trạng thái running."
          }
        />
      )}
    </Card>
  );
});

// ── Header ───────────────────────────────────────────────────────────────

function MotionHeader({
  selectedDevice,
  motion,
}: {
  selectedDevice: SimulatedDevice;
  motion: MotionLatest | null;
}) {
  const activity = describeActivity(motion?.activityState);
  const variantLabel = describeFallVariant(motion?.fallVariant);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "10px",
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        <strong>Xem trước chuyển động</strong>
        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          Thiết bị {selectedDevice.name} · nguồn dữ liệu: dataset registry
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
        {motion?.activityState && (
          <Badge severity={activity.severity}>
            {activity.display}
            {variantLabel ? ` · ${variantLabel}` : ""}
          </Badge>
        )}
        {motion?.emittedAt && (
          <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            {new Date(motion.emittedAt).toLocaleTimeString("vi-VN", { hour12: false })}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Body ─────────────────────────────────────────────────────────────────

function MotionBody({
  motion,
  showDetails,
  onToggleDetails,
}: {
  motion: MotionLatest;
  showDetails: boolean;
  onToggleDetails: () => void;
}) {
  const summary = useMemo(() => {
    const peakAccelMag = motion.accelMag.length ? Math.max(...motion.accelMag) : 0;
    const meanAccelMag = motion.accelMag.length
      ? motion.accelMag.reduce((sum, value) => sum + value, 0) / motion.accelMag.length
      : 0;
    return {
      peakAccelMag,
      meanAccelMag,
      sampleCount: motion.accelMag.length,
    };
  }, [motion]);

  const peakOverThreshold = summary.peakAccelMag >= PEAK_ACCEL_WARN_THRESHOLD;
  const isFalling = motion.activityState?.toLowerCase() === "fall";
  const primaryStroke = isFalling ? "var(--severity-critical)" : "var(--accent-cyan)";

  return (
    <div style={{ display: "grid", gap: "12px" }}>
      {/* Hero sparkline — |a| only, tinted by severity */}
      <div style={{ display: "grid", gap: "6px" }}>
        <div style={summaryRowStyle}>
          <SummaryCell
            label="Đỉnh |a|"
            value={`${summary.peakAccelMag.toFixed(2)} m/s²`}
            highlight={peakOverThreshold}
            highlightHint={peakOverThreshold ? "Đỉnh gia tốc vượt ngưỡng té ngã" : undefined}
          />
          <SummaryCell label="Trung bình |a|" value={`${summary.meanAccelMag.toFixed(2)} m/s²`} />
          <SummaryCell label="Số mẫu" value={`${summary.sampleCount}`} />
        </div>
        <Sparkline
          values={motion.accelMag}
          stroke={primaryStroke}
          height={72}
          ariaLabel="Gia tốc tổng |a| theo thời gian"
        />
      </div>

      {/* Toggle */}
      <button
        type="button"
        onClick={onToggleDetails}
        aria-expanded={showDetails}
        style={toggleStyle}
      >
        {showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {showDetails ? "Ẩn chi tiết kỹ thuật" : "Chi tiết kỹ thuật (6 trục + sample rate)"}
      </button>

      {/* Expanded technical view */}
      {showDetails && <TechnicalTraces motion={motion} />}
    </div>
  );
}

// ── Technical traces ─────────────────────────────────────────────────────

function TechnicalTraces({ motion }: { motion: MotionLatest }) {
  return (
    <div style={{ display: "grid", gap: "8px", paddingTop: "8px", borderTop: "1px dashed var(--border-default)" }}>
      {motion.sampleRate ? (
        <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          Tần số lấy mẫu: <strong style={{ color: "var(--text-secondary)" }}>{motion.sampleRate} Hz</strong>
        </div>
      ) : null}
      <TraceRow label="Gia tốc trục X" values={motion.accelX} stroke="var(--text-secondary)" />
      <TraceRow label="Gia tốc trục Y" values={motion.accelY} stroke="var(--text-secondary)" />
      <TraceRow label="Gia tốc trục Z" values={motion.accelZ} stroke="var(--text-secondary)" />
      <TraceRow label="Vận tốc góc trục X" values={motion.gyroX} stroke="var(--severity-warning)" />
      <TraceRow label="Vận tốc góc trục Y" values={motion.gyroY} stroke="var(--severity-warning)" />
      <TraceRow label="Vận tốc góc trục Z" values={motion.gyroZ} stroke="var(--severity-warning)" />
    </div>
  );
}

function TraceRow({
  label,
  values,
  stroke,
}: {
  label: string;
  values: number[];
  stroke: string;
}) {
  const last = values[values.length - 1];
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "150px 1fr 70px",
        gap: "8px",
        alignItems: "center",
      }}
    >
      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{label}</span>
      <Sparkline
        values={values}
        stroke={stroke}
        height={22}
        ariaLabel={`Trace ${label}`}
      />
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          textAlign: "right",
          color: "var(--text-secondary)",
        }}
      >
        {last !== undefined ? last.toFixed(2) : "—"}
      </span>
    </div>
  );
}

// ── Cells ────────────────────────────────────────────────────────────────

function SummaryCell({
  label,
  value,
  highlight,
  highlightHint,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  highlightHint?: string;
}) {
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
        title={highlightHint}
      >
        {highlight && <AlertTriangle size={12} aria-hidden="true" />}
        {value}
      </strong>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────

const summaryRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "8px",
  padding: "8px 10px",
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
};

const toggleStyle: CSSProperties = {
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
  transition: "color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
};
