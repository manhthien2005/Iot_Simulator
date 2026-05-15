import React, { memo, Suspense, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import type { SimulatedDevice } from "../../types/device";
import type { VitalsSample } from "../../types/vitals";
import { fetchLatestVitals } from "../../services/vitalsApi";
import { useSessionVitalsStore } from "../../stores/sessionVitalsStore";
import { getVitalSeverity } from "../../utils/severity";
import { isVitalsStreamStale, resolveVitalsFreshnessTimestamp } from "../../utils/vitalsFreshness";
import { Card } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import { POLL_INTERVALS } from "../../config/defaults";

const ReactECharts = React.lazy(() => import("echarts-for-react"));

// ---------------------------------------------------------------------------
// Time formatters — two variants:
//   UTC7_FULL   HH:mm:ss  for tooltip (precise)
//   UTC7_SHORT  HH:mm     for x-axis labels (concise, no overlap)
// ---------------------------------------------------------------------------

const UTC7_FULL = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Bangkok",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

const UTC7_SHORT = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Bangkok",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SessionVitalsPanelProps {
  devices: SimulatedDevice[];
  deviceId: string;
  runtimeTickAt?: string | null;
  onDeviceChange: (deviceId: string) => void;
}

interface EChartsTooltipParam {
  axisValue: string;
  marker: string;
  seriesName: string;
  data: [string, number];
}

type MetricKey = "heartRate" | "spo2" | "temperature" | "bloodPressure" | "respiratoryRate";
type MetricSeverity = "normal" | "warning" | "critical";

// ---------------------------------------------------------------------------
// Severity colours (shared between MetricWidget and chart)
// ---------------------------------------------------------------------------

const SEVERITY_COLOR: Record<MetricSeverity, string> = {
  normal: "var(--severity-normal, #22c55e)",
  warning: "var(--severity-warning, #f59e0b)",
  critical: "var(--severity-critical, #ef4444)",
};

// ---------------------------------------------------------------------------
// SessionVitalsPanel
// ---------------------------------------------------------------------------

export function SessionVitalsPanel({ devices, deviceId, runtimeTickAt = null, onDeviceChange }: SessionVitalsPanelProps) {
  const { activeDeviceId, streamData, appendSample, resetForDevice } = useSessionVitalsStore();
  const selectedDevice = devices.find((device) => device.id === deviceId) ?? null;
  const isConnected = Boolean(selectedDevice?.isOnline);

  const { data: latestSample, isLoading, error } = useQuery({
    queryKey: ["vitals", "session-panel", deviceId],
    queryFn: () => fetchLatestVitals(deviceId),
    refetchInterval: deviceId && isConnected ? POLL_INTERVALS.vitals : false,
    enabled: Boolean(deviceId && isConnected),
  });

  useEffect(() => {
    if (!deviceId) return;
    if (activeDeviceId !== deviceId) resetForDevice(deviceId);
  }, [activeDeviceId, deviceId, resetForDevice]);

  useEffect(() => {
    if (!latestSample || !isConnected) return;
    appendSample(deviceId, latestSample);
  }, [appendSample, deviceId, isConnected, latestSample]);

  useEffect(() => {
    if (!isConnected && deviceId) resetForDevice(deviceId);
  }, [deviceId, isConnected, resetForDevice]);

  const current = streamData[streamData.length - 1] ?? latestSample ?? null;
  const expectedIntervalMs = inferExpectedIntervalMs(streamData);
  const freshnessAt = resolveVitalsFreshnessTimestamp(runtimeTickAt, selectedDevice?.lastSeenAt, current?.timestamp);
  const stale = current
    ? isVitalsStreamStale({
        sampleTimestamp: current.timestamp,
        runtimeTickAt,
        deviceLastSeenAt: selectedDevice?.lastSeenAt,
        expectedIntervalMs,
      })
    : false;

  // Status derivation
  const statusLabel = !isConnected ? "Ngắt kết nối" : error ? "Lỗi lấy mẫu" : !current ? "Chờ dữ liệu" : stale ? "Chậm cập nhật" : "Trực tiếp";
  const statusColor = !isConnected ? "var(--text-muted)" : error ? "var(--severity-critical)" : !current ? "var(--text-muted)" : stale ? "var(--severity-warning)" : "var(--severity-normal)";

  // Per-metric severity
  const hrSeverity = current ? getVitalSeverity("heartRate", current.heartRate) : null;
  const spo2Severity = current ? getVitalSeverity("spo2", current.spo2) : null;
  const tempSeverity = current?.temperature != null ? getVitalSeverity("temperature", current.temperature) : null;
  const bpSeverity = current?.bloodPressureSys != null ? getVitalSeverity("bloodPressureSys", current.bloodPressureSys) : null;
  const rrSeverity = current?.respiratoryRate != null ? respiratoryRateSeverity(current.respiratoryRate) : null;

  // Overall severity badge (from stream sample)
  const overallSeverity = current?.severity ?? null;

  if (!devices.length) {
    return (
      <Card>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>Chưa có thiết bị để hiển thị sinh hiệu.</p>
      </Card>
    );
  }

  return (
    <Card
      header={
        <PanelHeader
          statusLabel={statusLabel}
          statusColor={statusColor}
          overallSeverity={overallSeverity as MetricSeverity | null}
          freshnessAt={freshnessAt}
          devices={devices}
          deviceId={deviceId}
          onDeviceChange={onDeviceChange}
        />
      }
    >
      {!isConnected ? (
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>Thiết bị đang ngắt kết nối, biểu đồ đã được đặt lại.</p>
      ) : isLoading && streamData.length === 0 ? (
        <Skeleton style={{ height: "320px" }} />
      ) : error && streamData.length === 0 ? (
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>Không lấy được mẫu sinh hiệu. Kiểm tra runtime, backend hoặc phiên mô phỏng.</p>
      ) : (
        <div style={{ display: "grid", gap: "12px" }}>

          {/* ── Metric widgets row ─────────────────────────────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(100px, 1fr))", gap: "8px" }}>
            <MetricWidget
              label="HR"
              number={current ? `${Math.round(current.heartRate)}` : "—"}
              unit="bpm"
              severity={hrSeverity}
            />
            <MetricWidget
              label="SpO2"
              number={current ? `${Math.round(current.spo2)}` : "—"}
              unit="%"
              severity={spo2Severity}
            />
            <MetricWidget
              label="Temp"
              number={current?.temperature != null ? current.temperature.toFixed(1) : "—"}
              unit="°C"
              severity={tempSeverity}
            />
            <MetricWidget
              label="BP"
              number={current?.bloodPressureSys != null && current?.bloodPressureDia != null
                ? `${Math.round(current.bloodPressureSys)}/${Math.round(current.bloodPressureDia)}`
                : "—"}
              unit="mmHg"
              severity={bpSeverity}
            />
            <MetricWidget
              label="RR"
              number={current?.respiratoryRate != null ? `${Math.round(current.respiratoryRate)}` : "—"}
              unit="/min"
              severity={rrSeverity}
            />
          </div>

          {/* ── Charts: HR full-width on top, then 2×2 for the rest ――― */}
          <div style={{ display: "grid", gap: "8px" }}>
            <MetricChart title="Nhịp tim (HR)" metric="heartRate" data={streamData} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
              <MetricChart title="Nồng độ oxy (SpO2)" metric="spo2" data={streamData} />
              <MetricChart title="Nhiệt độ cơ thể" metric="temperature" data={streamData} />
              <MetricChart title="Huyết áp (BP)" metric="bloodPressure" data={streamData} />
              <MetricChart title="Nhịp thở (RR)" metric="respiratoryRate" data={streamData} />
            </div>
          </div>

        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// PanelHeader — status bar with live indicator, overall severity, timestamp,
// and (when multiple devices) a device selector.
// ---------------------------------------------------------------------------

interface PanelHeaderProps {
  statusLabel: string;
  statusColor: string;
  overallSeverity: MetricSeverity | null;
  freshnessAt: Date | string | null | undefined;
  devices: SimulatedDevice[];
  deviceId: string;
  onDeviceChange: (id: string) => void;
}

function PanelHeader({ statusLabel, statusColor, overallSeverity, freshnessAt, devices, deviceId, onDeviceChange }: PanelHeaderProps) {
  const severityLabel = overallSeverity === "critical" ? "Nguy kịch" : overallSeverity === "warning" ? "Theo dõi" : overallSeverity === "normal" ? "Ổn định" : null;
  const severityDotColor = overallSeverity ? SEVERITY_COLOR[overallSeverity] : "var(--text-muted)";

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", width: "100%" }}>
      <strong>Bảng sinh hiệu trực tiếp</strong>

      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        {/* Live status */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: statusColor, flexShrink: 0 }} />
          <span style={{ fontSize: "12px", fontWeight: 600, color: statusColor }}>{statusLabel}</span>
        </div>

        {/* Overall severity */}
        {severityLabel ? (
          <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
            <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: severityDotColor, flexShrink: 0 }} />
            <span style={{ fontSize: "12px", fontWeight: 600, color: severityDotColor }}>{severityLabel}</span>
          </div>
        ) : null}

        {/* Last update */}
        {freshnessAt ? (
          <span style={{ fontSize: "11px", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
            Cập nhật: {formatFullTime(freshnessAt)}
          </span>
        ) : null}

        {/* Device selector — only when multiple devices */}
        {devices.length > 1 ? (
          <select
            value={deviceId}
            onChange={(event) => onDeviceChange(event.target.value)}
            aria-label="Chọn thiết bị để xem sinh hiệu"
            style={{
              background: "var(--bg-base)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
              padding: "5px 8px",
              fontSize: "12px",
            }}
          >
            {devices.map((device) => (
              <option key={device.id} value={device.id}>{device.name}</option>
            ))}
          </select>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetricWidget — compact KPI tile:
//   label (small, muted) + severity dot (top right)
//   number (large mono)
//   unit (small, secondary)
// ---------------------------------------------------------------------------

const MetricWidget = memo(function MetricWidget(props: {
  label: string;
  number: string;
  unit: string;
  severity: MetricSeverity | null;
}) {
  const valueColor = props.severity === "critical"
    ? "var(--severity-critical)"
    : props.severity === "warning"
      ? "var(--severity-warning)"
      : props.severity === "normal"
        ? "var(--severity-normal)"
        : "var(--text-primary)";

  return (
    <div
      style={{
        padding: "10px 12px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-default)",
        display: "grid",
        gap: "3px",
      }}
    >
      {/* Label row */}
      <span style={{ fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>
        {props.label}
      </span>

      {/* Value */}
      <div style={{ fontSize: "22px", fontWeight: 700, fontFamily: "var(--font-mono)", color: valueColor, lineHeight: 1.1 }}>
        {props.number}
      </div>

      {/* Unit */}
      <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
        {props.unit}
      </div>
    </div>
  );
}, (prev, next) =>
  prev.label === next.label &&
  prev.number === next.number &&
  prev.unit === next.unit &&
  prev.severity === next.severity
);

// ---------------------------------------------------------------------------
// MetricChart — ECharts line chart with cleaned-up options.
//
// Bug fixes vs previous version:
//   1. Removed yAxis.name + nameTextStyle — was causing "..." truncation.
//   2. X-axis formatter now uses UTC7_SHORT (HH:mm) + minInterval=60s
//      so labels never overlap.
//   3. Increased height to 200px and bottom grid margin to 30px so
//      the timestamp fits without clipping.
// ---------------------------------------------------------------------------

const MetricChart = memo(function MetricChart(props: { title: string; metric: MetricKey; data: VitalsSample[] }) {
  const option = useMemo(() => buildMetricOption(props.metric, props.data), [props.metric, props.data]);
  return (
    <div
      style={{
        borderRadius: "var(--radius-md)",
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-default)",
        padding: "10px 10px 4px 10px",
      }}
    >
      <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
        {props.title}
      </div>
      <Suspense fallback={<Skeleton style={{ height: "200px" }} />}>
        <ReactECharts option={option} notMerge={false} lazyUpdate style={{ height: "200px", width: "100%" }} />
      </Suspense>
    </div>
  );
}, (prev, next) => {
  if (prev.title !== next.title) return false;
  if (prev.data === next.data) return true;
  if (prev.data.length !== next.data.length) return false;
  if (prev.data.length === 0) return true;
  const pl = prev.data[prev.data.length - 1];
  const nl = next.data[next.data.length - 1];
  return pl.timestamp === nl.timestamp;
});

// ---------------------------------------------------------------------------
// buildMetricOption — ECharts config factory.
// ---------------------------------------------------------------------------

function buildMetricOption(metric: MetricKey, data: VitalsSample[]): EChartsOption {
  const points = data.slice(-120);

  const sharedXAxis = {
    type: "time" as const,
    minInterval: 10_000, // tick at most once per 10 s → readable on short windows
    axisLabel: {
      color: "#64748b",
      fontSize: 11,
      formatter: (value: number) => formatShortTime(value),
    },
    axisLine: { lineStyle: { color: "#1e2d4a" } },
    axisTick: { lineStyle: { color: "#1e2d4a" } },
  };

  const sharedGrid = { top: 12, right: 12, bottom: 30, left: 40 };

  const tooltipFormatter = (rawParams: unknown, seriesLabels: string[]) => {
    const params = Array.isArray(rawParams) ? rawParams as EChartsTooltipParam[] : [rawParams as EChartsTooltipParam];
    const time = `UTC+7: ${formatFullTime(params[0]?.axisValue)}`;
    const lines = params.map((p, i) => {
      const label = seriesLabels[i] ?? p.seriesName;
      const val = formatChartValue((p.data as [string, number])?.[1]);
      return `${p.marker ?? ""}${label}: ${val}`;
    });
    return [time, ...lines].join("<br/>");
  };

  if (metric === "bloodPressure") {
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        formatter: (p: unknown) => tooltipFormatter(p, ["Tâm thu", "Tâm trương"]),
      },
      grid: sharedGrid,
      xAxis: sharedXAxis,
      yAxis: {
        type: "value",
        min: 50,
        max: 190,
        axisLabel: { color: "#64748b", fontSize: 11 },
        splitLine: { lineStyle: { color: "#1e2d4a", type: "dashed" } },
      },
      series: [
        {
          name: "Tâm thu",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => [item.timestamp, item.bloodPressureSys]),
          lineStyle: { color: "#F97316", width: 2 },
          areaStyle: { color: "rgba(249,115,22,0.06)" },
        },
        {
          name: "Tâm trương",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => [item.timestamp, item.bloodPressureDia]),
          lineStyle: { color: "#22C55E", width: 2 },
          areaStyle: { color: "rgba(34,197,94,0.06)" },
        },
      ],
    };
  }

  const configs: Record<
    Exclude<MetricKey, "bloodPressure">,
    { min: number; max: number; color: string; seriesLabel: string; value: (item: VitalsSample) => number | null }
  > = {
    heartRate: {
      min: 40, max: 180, color: "#EF4444", seriesLabel: "HR",
      value: (item) => item.heartRate,
    },
    spo2: {
      min: 80, max: 100, color: "#06B6D4", seriesLabel: "SpO2",
      value: (item) => item.spo2,
    },
    temperature: {
      min: 34, max: 42, color: "#F59E0B", seriesLabel: "Temp",
      value: (item) => item.temperature,
    },
    respiratoryRate: {
      min: 4, max: 40, color: "#8B5CF6", seriesLabel: "RR",
      value: (item) => item.respiratoryRate,
    },
  };

  const cfg = configs[metric];
  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      formatter: (p: unknown) => tooltipFormatter(p, [cfg.seriesLabel]),
    },
    grid: sharedGrid,
    xAxis: sharedXAxis,
    yAxis: {
      type: "value",
      min: cfg.min,
      max: cfg.max,
      // NOTE: yAxis.name intentionally omitted — ECharts truncates it
      // with "..." when the chart is narrow, cluttering the corner.
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#1e2d4a", type: "dashed" } },
    },
    series: [
      {
        name: cfg.seriesLabel,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((item) => [item.timestamp, cfg.value(item)]),
        lineStyle: { color: cfg.color, width: 2 },
        areaStyle: { color: `${cfg.color}10` },
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Pure utilities
// ---------------------------------------------------------------------------

function respiratoryRateSeverity(value: number): MetricSeverity {
  if (value < 8 || value > 30) return "critical";
  if (value < 12 || value > 24) return "warning";
  return "normal";
}

function formatChartValue(value: number | null | undefined): string {
  return value != null ? Number(value).toFixed(1) : "—";
}

function parseTimestamp(value: string | number | Date): Date {
  if (value instanceof Date) return value;
  if (typeof value === "number") return new Date(value);
  const text = String(value).trim();
  const hasZone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(text);
  return new Date(hasZone ? text : `${text}Z`);
}

function formatFullTime(value: string | number | Date | null | undefined): string {
  if (!value) return "--:--:--";
  const date = parseTimestamp(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return UTC7_FULL.format(date);
}

function formatShortTime(value: string | number | Date | null | undefined): string {
  if (!value) return "--:--";
  const date = parseTimestamp(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return UTC7_SHORT.format(date);
}

function inferExpectedIntervalMs(points: VitalsSample[]): number {
  if (points.length < 2) return 15_000;
  const latest = parseTimestamp(points[points.length - 1].timestamp).getTime();
  const previous = parseTimestamp(points[points.length - 2].timestamp).getTime();
  return Math.max(1_000, latest - previous);
}
