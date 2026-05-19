import type { CSSProperties } from "react";
import { useMemo } from "react";
import { Activity, ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { InfoTooltip } from "./InfoTooltip";
import { useVitalsRingBuffer, type VitalsBufferEntry } from "../../../hooks/useVitalsRingBuffer";

// ---------------------------------------------------------------------------
// VitalsAfterFallCard — Module FA Phase 1, Section D of the Fall Lab.
//
// Renders 4 mini-charts (HR / SpO2 / BP_sys / RR) with a +/-60s window
// around `lastFallEventAt`, plus pre/post 30s baseline diff so the
// operator can see the post-fall sympathetic spike (HR up, SpO2 down,
// BP_sys up, RR up) at a glance.
//
// Sample source: client-side ring buffer (`useVitalsRingBuffer`) since
// the simulator BE only exposes a "latest" endpoint.  Buffer is reset
// whenever `deviceId` changes so switching device does not leak samples.
//
// Empty state: shown when no fall event has happened yet OR when the
// buffer doesn't yet cover both pre and post halves of the window
// (typical immediately after the operator picks the device).
// ---------------------------------------------------------------------------

interface Props {
  deviceId: string | null;
  lastFallEventAt: string | null;
}

const HR_DELTA_WARN = 20;
const SPO2_DELTA_WARN = -3;
const BP_DELTA_WARN = 15;
const RR_DELTA_WARN = 5;

const PRE_POST_WINDOW_SEC = 30;

export function VitalsAfterFallCard({ deviceId, lastFallEventAt }: Props) {
  const { buffer } = useVitalsRingBuffer(deviceId);

  const summary = useMemo(() => {
    if (!lastFallEventAt) return null;
    const fallTs = Date.parse(lastFallEventAt);
    if (Number.isNaN(fallTs)) return null;
    const preCutoff = fallTs - PRE_POST_WINDOW_SEC * 1000;
    const postCutoff = fallTs + PRE_POST_WINDOW_SEC * 1000;
    const inWindow = buffer.filter(
      (entry) => entry.timestampMs >= preCutoff && entry.timestampMs <= postCutoff,
    );
    if (inWindow.length === 0) return null;
    const pre = inWindow.filter((entry) => entry.timestampMs <= fallTs);
    const post = inWindow.filter((entry) => entry.timestampMs > fallTs);
    return {
      fallTs,
      windowEntries: inWindow,
      preMean: meanOf(pre),
      postMean: meanOf(post),
      latest: inWindow[inWindow.length - 1],
    };
  }, [buffer, lastFallEventAt]);

  return (
    <Card
      header={
        <div style={cardHeadStyle}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <Activity size={14} />
            <strong>Biến thiên sinh hiệu sau té ngã (±60s)</strong>
          </span>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            client-side ring buffer · pre/post {PRE_POST_WINDOW_SEC}s baseline
          </span>
        </div>
      }
    >
      {!lastFallEventAt
        ? (
          <EmptyState
            icon={Activity}
            title="Chưa có fall event"
            description="Inject một kịch bản té ngã ở Section A để theo dõi biến thiên HR / SpO2 / BP / RR quanh thời điểm fall."
          />
        )
        : !summary
        ? (
          <EmptyState
            icon={Activity}
            title="Đang gom mẫu vitals…"
            description="Buffer chưa có đủ sample trong cửa sổ ±60s quanh fall event. Chờ vài giây để buffer đầy."
          />
        )
        : <VitalsGrid summary={summary} />}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sub-pieces
// ---------------------------------------------------------------------------

function VitalsGrid({ summary }: { summary: VitalsSummary }) {
  return (
    <div style={{ display: "grid", gap: "12px" }}>
      <div style={vitalsGridStyle}>
        <VitalCell
          label="Nhịp tim" tooltipKey="vitalsHr" unit="bpm"
          now={summary.latest.heartRate}
          pre={summary.preMean.heartRate}
          post={summary.postMean.heartRate}
          window={summary.windowEntries}
          fallTs={summary.fallTs}
          getter={(e) => e.heartRate}
          warnUpAt={HR_DELTA_WARN}
        />
        <VitalCell
          label="SpO₂" tooltipKey="vitalsSpo2" unit="%"
          now={summary.latest.spo2}
          pre={summary.preMean.spo2}
          post={summary.postMean.spo2}
          window={summary.windowEntries}
          fallTs={summary.fallTs}
          getter={(e) => e.spo2}
          warnDownAt={SPO2_DELTA_WARN}
        />
        <VitalCell
          label="HA tâm thu" tooltipKey="vitalsBpSys" unit="mmHg"
          now={summary.latest.bloodPressureSys ?? null}
          pre={summary.preMean.bloodPressureSys}
          post={summary.postMean.bloodPressureSys}
          window={summary.windowEntries}
          fallTs={summary.fallTs}
          getter={(e) => e.bloodPressureSys}
          warnUpAt={BP_DELTA_WARN}
        />
        <VitalCell
          label="Nhịp thở" tooltipKey="vitalsRr" unit="br/m"
          now={summary.latest.respiratoryRate ?? null}
          pre={summary.preMean.respiratoryRate}
          post={summary.postMean.respiratoryRate}
          window={summary.windowEntries}
          fallTs={summary.fallTs}
          getter={(e) => e.respiratoryRate}
          warnUpAt={RR_DELTA_WARN}
        />
      </div>
    </div>
  );
}

interface VitalCellProps {
  label: string;
  tooltipKey: import("./fallLabTooltips").FallLabTooltipKey;
  unit: string;
  now: number | null;
  pre: number | null;
  post: number | null;
  window: VitalsBufferEntry[];
  fallTs: number;
  getter: (entry: VitalsBufferEntry) => number | null;
  warnUpAt?: number;
  warnDownAt?: number;
}

function VitalCell({ label, tooltipKey, unit, now, pre, post, window, fallTs, getter, warnUpAt, warnDownAt }: VitalCellProps) {
  const delta = pre != null && post != null ? post - pre : null;
  const tone = severityForDelta(delta, warnUpAt, warnDownAt);
  return (
    <div style={vitalCardStyle}>
      <div style={vitalHeadStyle}>
        <strong style={{ fontSize: "11px", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {label}
          <InfoTooltip k={tooltipKey} />
        </strong>
        <DeltaChip delta={delta} unit={unit} tone={tone} />
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "20px", fontWeight: 700, color: colorForTone(tone) }}>
        {now != null ? now.toFixed(0) : "—"}
        <small style={{ fontSize: "11px", fontWeight: 500, color: "var(--text-muted)", marginLeft: "4px" }}>{unit}</small>
      </div>
      <VitalSparkline window={window} fallTs={fallTs} getter={getter} />
      <div style={baselineStyle}>
        <BaselineRow label="Pre 30s" value={pre} unit={unit} />
        <BaselineRow label="Post 30s" value={post} unit={unit} />
      </div>
    </div>
  );
}

function DeltaChip({ delta, unit, tone }: { delta: number | null; unit: string; tone: "normal" | "warning" | "critical" }) {
  if (delta == null) return <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>—</span>;
  const Arrow = delta > 0 ? ArrowUp : delta < 0 ? ArrowDown : Minus;
  const sign = delta > 0 ? "+" : "";
  return (
    <span style={{ ...deltaChipStyle, color: colorForTone(tone), background: bgForTone(tone) }}>
      <Arrow size={11} />
      {sign}{delta.toFixed(0)} {unit}
    </span>
  );
}

function VitalSparkline({
  window, fallTs, getter,
}: { window: VitalsBufferEntry[]; fallTs: number; getter: (entry: VitalsBufferEntry) => number | null }) {
  if (window.length < 2) {
    return <div style={{ height: "40px", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)" }} />;
  }
  const values = window.map(getter);
  let yMin = Infinity, yMax = -Infinity;
  for (const v of values) { if (v == null) continue; if (v < yMin) yMin = v; if (v > yMax) yMax = v; }
  if (!Number.isFinite(yMin) || !Number.isFinite(yMax) || yMin === yMax) {
    yMin = (yMin || 0) - 1; yMax = (yMax || 0) + 1;
  }
  const range = yMax - yMin;
  const tMin = window[0].timestampMs;
  const tMax = window[window.length - 1].timestampMs;
  const tRange = tMax - tMin || 1;
  const W = 200, H = 40;
  const points = window
    .map((entry, idx) => {
      const v = values[idx];
      if (v == null) return null;
      const x = ((entry.timestampMs - tMin) / tRange) * W;
      const y = H - ((v - yMin) / range) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter((p): p is string => p !== null)
    .join(" ");
  const fallX = ((fallTs - tMin) / tRange) * W;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: "40px", display: "block" }}>
      <line x1={fallX} y1={0} x2={fallX} y2={H} stroke="#ef4444" strokeWidth={1} strokeDasharray="2 2" opacity={0.6} />
      <polyline fill="none" stroke="#06b6d4" strokeWidth={1.5} points={points} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function BaselineRow({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
      {label}
      <strong style={{ display: "block", fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>
        {value != null ? `${value.toFixed(0)} ${unit}` : "—"}
      </strong>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface VitalsMean {
  heartRate: number | null;
  spo2: number | null;
  bloodPressureSys: number | null;
  respiratoryRate: number | null;
}

function meanOf(entries: VitalsBufferEntry[]): VitalsMean {
  if (entries.length === 0) {
    return { heartRate: null, spo2: null, bloodPressureSys: null, respiratoryRate: null };
  }
  let hr = 0, hrN = 0;
  let sp = 0, spN = 0;
  let bp = 0, bpN = 0;
  let rr = 0, rrN = 0;
  for (const entry of entries) {
    if (Number.isFinite(entry.heartRate)) { hr += entry.heartRate; hrN += 1; }
    if (Number.isFinite(entry.spo2)) { sp += entry.spo2; spN += 1; }
    if (entry.bloodPressureSys != null && Number.isFinite(entry.bloodPressureSys)) {
      bp += entry.bloodPressureSys; bpN += 1;
    }
    if (entry.respiratoryRate != null && Number.isFinite(entry.respiratoryRate)) {
      rr += entry.respiratoryRate; rrN += 1;
    }
  }
  return {
    heartRate: hrN > 0 ? hr / hrN : null,
    spo2: spN > 0 ? sp / spN : null,
    bloodPressureSys: bpN > 0 ? bp / bpN : null,
    respiratoryRate: rrN > 0 ? rr / rrN : null,
  };
}

function severityForDelta(
  delta: number | null,
  warnUpAt: number | undefined,
  warnDownAt: number | undefined,
): "normal" | "warning" | "critical" {
  if (delta == null) return "normal";
  if (warnUpAt != null && delta >= warnUpAt) return delta >= warnUpAt * 1.5 ? "critical" : "warning";
  if (warnDownAt != null && delta <= warnDownAt) return delta <= warnDownAt * 1.5 ? "critical" : "warning";
  return "normal";
}

function colorForTone(tone: "normal" | "warning" | "critical"): string {
  if (tone === "critical") return "var(--severity-critical)";
  if (tone === "warning") return "var(--severity-warning)";
  return "var(--text-primary)";
}

function bgForTone(tone: "normal" | "warning" | "critical"): string {
  if (tone === "critical") return "var(--severity-critical-bg)";
  if (tone === "warning") return "var(--severity-warning-bg)";
  return "var(--severity-offline-bg)";
}

// Type alias for the summary memo so callers can reuse it.
interface VitalsSummary {
  fallTs: number;
  windowEntries: VitalsBufferEntry[];
  preMean: VitalsMean;
  postMean: VitalsMean;
  latest: VitalsBufferEntry;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const cardHeadStyle: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap",
};

const vitalsGridStyle: CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px",
};

const vitalCardStyle: CSSProperties = {
  padding: "12px",
  background: "var(--bg-base)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  display: "grid", gap: "8px",
};

const vitalHeadStyle: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px",
};

const baselineStyle: CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px",
  paddingTop: "6px", borderTop: "1px dashed var(--border-default)",
};

const deltaChipStyle: CSSProperties = {
  display: "inline-flex", alignItems: "center", gap: "3px",
  padding: "2px 6px", borderRadius: "var(--radius-sm)",
  fontFamily: "var(--font-mono)", fontSize: "11px", fontWeight: 600,
};
