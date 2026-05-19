import type { CSSProperties } from "react";
import { useMemo, useState } from "react";
import { Activity, AlertTriangle, ChevronRight } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { describeFallVariant } from "../../../utils/motionLabels";
import type { MotionLatest } from "../../../types/motion";
import type { FallState } from "../../../types/fall";

// ---------------------------------------------------------------------------
// MotionWindowDetailCard — Module FA Phase 1, Section C of the Fall Lab.
//
// Replaces the old `<MotionWindowCard/>` with a research-grade chart:
//
//   * Hero accelMag SVG with horizontal threshold lines (3.0g hard +
//     2.5g soft) and a vertical peak marker so the operator can see at
//     a glance which threshold the window crossed.
//   * Pre-impact (samples 0..peakIndex-1) vs post-impact (peakIndex..N-1)
//     metrics — mean |a|, peak |a|, gyro mean for pre; mean |a|, std |a|
//     for post.  These are the same window stats the BE pre-trigger
//     checks (see `pre_model_trigger.fall_pre_trigger.evaluate`).
//   * Sub-traces (gyro magnitude derived from gx/gy/gz, environment binary
//     lane) live in a "show details" toggle so the hero stays scan-friendly.
//
// Peak index is derived FE-side via `argmax(accelMag)`.  Phase 2 may
// move this to the BE if we add `peakIndex` to `MotionLatest`.
// ---------------------------------------------------------------------------

interface Props {
  motion: MotionLatest | null;
  fallState: FallState | null;
}

const HARD_THRESHOLD_G = 3.0;
const SOFT_THRESHOLD_G = 2.5;

export function MotionWindowDetailCard({ motion, fallState }: Props) {
  const [showDetails, setShowDetails] = useState(false);

  const stats = useMemo(() => {
    if (!motion || motion.accelMag.length === 0) return null;
    const arr = motion.accelMag;
    let peak = -Infinity;
    let peakIdx = 0;
    let sum = 0;
    for (let i = 0; i < arr.length; i++) {
      const value = arr[i];
      sum += value;
      if (value > peak) { peak = value; peakIdx = i; }
    }
    const mean = sum / arr.length;
    const preArr = arr.slice(0, peakIdx);
    const postArr = arr.slice(peakIdx);
    const preMean = preArr.length > 0 ? preArr.reduce((a, b) => a + b, 0) / preArr.length : 0;
    const postMean = postArr.length > 0 ? postArr.reduce((a, b) => a + b, 0) / postArr.length : 0;
    const postStd = postArr.length > 0
      ? Math.sqrt(postArr.reduce((a, b) => a + (b - postMean) ** 2, 0) / postArr.length)
      : 0;
    const gyroMag = motion.gyroX.map((_, i) => Math.sqrt(
      motion.gyroX[i] ** 2 + (motion.gyroY[i] ?? 0) ** 2 + (motion.gyroZ[i] ?? 0) ** 2,
    ));
    const gyroMeanPre = gyroMag.slice(0, peakIdx);
    const gyroPreMean = gyroMeanPre.length > 0
      ? gyroMeanPre.reduce((a, b) => a + b, 0) / gyroMeanPre.length : 0;
    return { peak, peakIdx, mean, preMean, postMean, postStd, gyroPreMean, gyroMag, count: arr.length };
  }, [motion]);

  const variantBadge = describeFallVariant(motion?.fallVariant);
  const aiAlignedAt = fallState?.motionWindowRef?.emittedAt;
  const motionAt = motion?.emittedAt;
  const aligned = Boolean(aiAlignedAt && motionAt && aiAlignedAt === motionAt);

  return (
    <Card
      header={
        <div style={cardHeadStyle}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <Activity size={14} />
            <strong>Cửa sổ chuyển động (50 mẫu) · accel + ngưỡng + peak marker</strong>
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
            {variantBadge && <Badge severity="info">{variantBadge}</Badge>}
            {fallState?.aiPrediction?.modelStatus === "ok" && (
              <Badge severity={aligned ? "normal" : "warning"}>
                {aligned ? "Cùng cửa sổ AI đã chấm" : "Cửa sổ mới (sau AI)"}
              </Badge>
            )}
          </div>
        </div>
      }
    >
      {!motion || !stats
        ? (
          <EmptyState
            icon={Activity}
            title="Chưa có dữ liệu chuyển động"
            description="Phiên đang chạy nhưng chưa có window nào được publish cho thiết bị này."
          />
        )
        : (
          <div style={{ display: "grid", gap: "12px" }}>

            <div style={metaGridStyle}>
              <MetricCell label="Đỉnh |a|" value={`${stats.peak.toFixed(2)} g`} highlight={stats.peak >= HARD_THRESHOLD_G} />
              <MetricCell label="Trung bình |a|" value={`${stats.mean.toFixed(2)} g`} />
              <MetricCell label="Peak ở mẫu" value={`${stats.peakIdx} / ${stats.count}`} />
              <MetricCell label="Tần số" value={motion.sampleRate ? `${motion.sampleRate} Hz` : "—"} />
            </div>

            <HeroChart
              values={motion.accelMag}
              peakIdx={stats.peakIdx}
              peakValue={stats.peak}
            />

            <Legend />

            <ImpactSplit
              preMean={stats.preMean}
              prePeak={stats.peak}
              gyroPreMean={stats.gyroPreMean}
              postMean={stats.postMean}
              postStd={stats.postStd}
              peakIdx={stats.peakIdx}
              count={stats.count}
            />

            <button type="button" onClick={() => setShowDetails((s) => !s)} style={detailsToggleStyle}>
              <ChevronRight
                size={14}
                style={{ transform: showDetails ? "rotate(90deg)" : "none", transition: "transform 200ms" }}
              />
              {showDetails ? "Ẩn chi tiết 6 trục + gyro magnitude" : "Hiện chi tiết 6 trục + gyro magnitude"}
            </button>
            {showDetails && <SubTraces motion={motion} gyroMag={stats.gyroMag} />}
          </div>
        )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sub-pieces (kept inline; each <30 lines so the file stays scannable)
// ---------------------------------------------------------------------------

function MetricCell({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{label}</span>
      <strong style={{
        fontFamily: "var(--font-mono)",
        fontSize: "13px",
        color: highlight ? "var(--severity-critical)" : "var(--text-primary)",
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
      }}>
        {highlight && <AlertTriangle size={12} aria-hidden="true" />}
        {value}
      </strong>
    </div>
  );
}

function HeroChart({ values, peakIdx, peakValue }: { values: number[]; peakIdx: number; peakValue: number }) {
  const W = 600, H = 180;
  const len = values.length;
  if (len === 0) return null;
  // y-domain: 0 → max(peak, hard threshold) so threshold lines stay visible
  const yMax = Math.max(peakValue, HARD_THRESHOLD_G + 0.5);
  const points = values.map((v, i) => {
    const x = (i / (len - 1 || 1)) * W;
    const y = H - (v / yMax) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const peakX = (peakIdx / (len - 1 || 1)) * W;
  const peakY = H - (peakValue / yMax) * H;
  const hardY = H - (HARD_THRESHOLD_G / yMax) * H;
  const softY = H - (SOFT_THRESHOLD_G / yMax) * H;

  return (
    <div style={heroStyle} aria-label="Gia tốc tổng |a| với ngưỡng pre-trigger và peak marker">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: "100%", display: "block" }}>
        <rect x={0} y={0} width={peakX} height={H} fill="rgba(34,197,94,0.05)" />
        <rect x={peakX} y={0} width={W - peakX} height={H} fill="rgba(239,68,68,0.06)" />
        <line x1={0} y1={hardY} x2={W} y2={hardY} stroke="#ef4444" strokeWidth={1} strokeDasharray="6 4" opacity={0.7} />
        <text x={6} y={hardY - 4} fill="#ef4444" fontSize={10} fontFamily="JetBrains Mono">hard {HARD_THRESHOLD_G.toFixed(1)}g</text>
        <line x1={0} y1={softY} x2={W} y2={softY} stroke="#f59e0b" strokeWidth={1} strokeDasharray="6 4" opacity={0.7} />
        <text x={6} y={softY - 4} fill="#f59e0b" fontSize={10} fontFamily="JetBrains Mono">soft {SOFT_THRESHOLD_G.toFixed(1)}g</text>
        <line x1={peakX} y1={0} x2={peakX} y2={H} stroke="#06b6d4" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
        <text x={peakX + 6} y={18} fill="#06b6d4" fontSize={10} fontFamily="JetBrains Mono">impact ở mẫu {peakIdx}</text>
        <polyline fill="none" stroke="#06b6d4" strokeWidth={2} points={points} />
        <circle cx={peakX} cy={peakY} r={4} fill="#ef4444" stroke="#fff" strokeWidth={1} />
      </svg>
    </div>
  );
}

function Legend() {
  return (
    <div style={legendStyle}>
      <LegendItem swatch="#06b6d4" label="|a| accel magnitude" />
      <LegendItem swatch="#ef4444" label={`ngưỡng hard ${HARD_THRESHOLD_G.toFixed(1)}g`} />
      <LegendItem swatch="#f59e0b" label={`ngưỡng soft ${SOFT_THRESHOLD_G.toFixed(1)}g`} />
      <LegendItem swatch="rgba(34,197,94,0.4)" label="vùng pre-impact" />
      <LegendItem swatch="rgba(239,68,68,0.4)" label="vùng post-impact" />
    </div>
  );
}

function LegendItem({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "var(--text-secondary)" }}>
      <span style={{ width: "14px", height: "3px", borderRadius: "2px", background: swatch }} />
      {label}
    </span>
  );
}

function ImpactSplit(props: {
  preMean: number; prePeak: number; gyroPreMean: number;
  postMean: number; postStd: number; peakIdx: number; count: number;
}) {
  return (
    <div style={impactSplitStyle}>
      <div style={{ ...paneStyle, ...prePaneStyle }}>
        <h4 style={{ ...paneHeadStyle, color: "var(--severity-normal)" }}>
          Pre-impact · mẫu 0–{Math.max(props.peakIdx - 1, 0)}
        </h4>
        <Row label="Mean |a|" value={`${props.preMean.toFixed(2)} g`} />
        <Row label="Peak |a|" value={`${props.prePeak.toFixed(2)} g`} />
        <Row label="Gyro mean" value={`${props.gyroPreMean.toFixed(0)} dps`} />
      </div>
      <div style={{ ...paneStyle, ...postPaneStyle }}>
        <h4 style={{ ...paneHeadStyle, color: "var(--severity-critical)" }}>
          Post-impact · mẫu {props.peakIdx}–{props.count - 1}
        </h4>
        <Row label="Mean |a|" value={`${props.postMean.toFixed(2)} g`} />
        <Row label="Std |a|" value={`${props.postStd.toFixed(2)} g`} />
        <Row label="Sample count" value={`${props.count - props.peakIdx}`} />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", padding: "2px 0", fontSize: "12px", color: "var(--text-secondary)" }}>
      <span>{label}</span>
      <code style={{ color: "var(--text-primary)" }}>{value}</code>
    </div>
  );
}

function SubTraces({ motion, gyroMag }: { motion: MotionLatest; gyroMag: number[] }) {
  const accelLast = motion.accelX[motion.accelX.length - 1] ?? 0;
  return (
    <div style={{ display: "grid", gap: "6px", paddingTop: "6px", borderTop: "1px dashed var(--border-default)" }}>
      <Sub label="Gyro magnitude" sub="derive từ gx/gy/gz" values={gyroMag} stroke="var(--severity-warning)" />
      <Sub label="Gia tốc trục X" sub={`last = ${accelLast.toFixed(2)}`} values={motion.accelX} stroke="var(--text-secondary)" />
      <Sub label="Gia tốc trục Y" sub="" values={motion.accelY} stroke="var(--text-secondary)" />
      <Sub label="Gia tốc trục Z" sub="" values={motion.accelZ} stroke="var(--text-secondary)" />
    </div>
  );
}

function Sub({ label, sub, values, stroke }: { label: string; sub: string; values: number[]; stroke: string }) {
  if (values.length === 0) return null;
  const W = 600, H = 28;
  let yMin = Infinity, yMax = -Infinity;
  for (const v of values) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; }
  if (yMin === yMax) { yMin -= 0.5; yMax += 0.5; }
  const range = yMax - yMin;
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1 || 1)) * W;
    const y = H - ((v - yMin) / range) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const last = values[values.length - 1];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "150px 1fr 70px", gap: "8px", alignItems: "center" }}>
      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
        {label}{sub ? <small style={{ display: "block", color: "var(--text-muted)", fontSize: "10px" }}>{sub}</small> : null}
      </span>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: "22px", display: "block" }}>
        <polyline fill="none" stroke={stroke} strokeWidth={1.5} points={points} vectorEffect="non-scaling-stroke" />
      </svg>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", textAlign: "right", color: "var(--text-secondary)" }}>
        {last.toFixed(2)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const cardHeadStyle: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: "8px",
  padding: "10px 12px",
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
};

const heroStyle: CSSProperties = {
  position: "relative",
  height: "180px",
  background: "var(--bg-base)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  overflow: "hidden",
};

const legendStyle: CSSProperties = { display: "flex", gap: "14px", flexWrap: "wrap", padding: "0 4px" };

const impactSplitStyle: CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0,
  border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", overflow: "hidden",
};

const paneStyle: CSSProperties = { padding: "12px 14px" };
const prePaneStyle: CSSProperties = { background: "rgba(34,197,94,0.04)", borderRight: "1px solid var(--border-default)" };
const postPaneStyle: CSSProperties = { background: "rgba(239,68,68,0.05)" };

const paneHeadStyle: CSSProperties = {
  margin: "0 0 8px", fontSize: "11px", fontWeight: 600,
  textTransform: "uppercase", letterSpacing: "0.06em",
};

const detailsToggleStyle: CSSProperties = {
  display: "inline-flex", alignItems: "center", gap: "6px",
  alignSelf: "flex-start", padding: "6px 10px",
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--border-default)",
  background: "transparent", color: "var(--text-secondary)",
  cursor: "pointer", fontSize: "12px", fontWeight: 500,
};
