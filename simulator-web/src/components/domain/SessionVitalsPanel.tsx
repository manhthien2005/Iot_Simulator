import React, { memo, Suspense, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import type { SimulatedDevice } from "../../types/device";
import type { VitalsSample } from "../../types/vitals";
import { fetchLatestVitals } from "../../services/vitalsApi";
import { useSessionVitalsStore } from "../../stores/sessionVitalsStore";
import { getVitalSeverity } from "../../utils/severity";
import { isVitalsStreamStale, resolveVitalsFreshnessTimestamp } from "../../utils/vitalsFreshness";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import { POLL_INTERVALS } from "../../config/defaults";

const ReactECharts = React.lazy(() => import("echarts-for-react"));

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
type BadgeSeverity = "normal" | "warning" | "critical" | "info" | "offline";

const UTC7_TIME = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Bangkok",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

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
    if (activeDeviceId !== deviceId) {
      resetForDevice(deviceId);
    }
  }, [activeDeviceId, deviceId, resetForDevice]);

  useEffect(() => {
    if (!latestSample || !isConnected) return;
    appendSample(deviceId, latestSample);
  }, [appendSample, deviceId, isConnected, latestSample]);

  useEffect(() => {
    if (!isConnected && deviceId) {
      resetForDevice(deviceId);
    }
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
  const statusLabel = !isConnected ? "thiết bị ngắt" : error ? "lỗi lấy mẫu" : !current ? "chưa có mẫu" : stale ? "chậm cập nhật" : "trực tiếp";
  const statusSeverity = !isConnected ? "offline" : error ? "critical" : !current ? "offline" : stale ? "warning" : "normal";
  const hrSeverity = current ? getVitalSeverity("heartRate", current.heartRate) : null;
  const spo2Severity = current ? getVitalSeverity("spo2", current.spo2) : null;
  const tempSeverity = current?.temperature != null ? getVitalSeverity("temperature", current.temperature) : null;
  const bpSeverity = current?.bloodPressureSys != null ? getVitalSeverity("bloodPressureSys", current.bloodPressureSys) : null;
  const rrSeverity = current?.respiratoryRate != null ? respiratoryRateSeverity(current.respiratoryRate) : null;

  if (!devices.length) {
    return (
      <Card header={<strong>Bảng sinh hiệu trực tiếp</strong>}>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>Chưa có thiết bị để hiển thị sinh hiệu.</p>
      </Card>
    );
  }

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
          <strong>Bảng sinh hiệu trực tiếp</strong>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Badge severity={statusSeverity}>{statusLabel}</Badge>
            {current?.severity ? (
              <Badge severity={severityToBadge(current.severity)}>
                {current.severity === "critical" ? "🚨 Nguy kịch" : current.severity === "warning" ? "⚠️ Cảnh báo" : "✅ Ổn định"}
              </Badge>
            ) : null}
            {freshnessAt ? (
              <small style={{ color: "var(--text-muted)", fontSize: "11px", whiteSpace: "nowrap" }}>
                Cập nhật: {formatUtc7Time(freshnessAt)}
              </small>
            ) : null}
            <select
              value={deviceId}
              onChange={(event) => onDeviceChange(event.target.value)}
              aria-label="Chọn thiết bị để xem sinh hiệu"
              style={{
                background: "var(--bg-base)",
                color: "var(--text-primary)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-md)",
                padding: "7px 10px",
              }}
            >
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      }
    >
      {!isConnected ? (
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>Thiết bị đang ngắt kết nối, biểu đồ đã được đặt lại.</p>
      ) : isLoading && streamData.length === 0 ? (
        <Skeleton style={{ height: "280px" }} />
      ) : error && streamData.length === 0 ? (
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>Không lấy được mẫu sinh hiệu. Kiểm tra runtime, backend hoặc phiên mô phỏng.</p>
      ) : (
        <div style={{ display: "grid", gap: "10px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(120px, 1fr))", gap: "8px" }}>
            <MetricWidget title="HR" value={current ? `${Math.round(current.heartRate)} bpm` : "--"} severity={hrSeverity} />
            <MetricWidget title="SpO2" value={current ? `${Math.round(current.spo2)}%` : "--"} severity={spo2Severity} />
            <MetricWidget title="Temp" value={formatTemperature(current?.temperature)} severity={tempSeverity} />
            <MetricWidget
              title="BP"
              value={formatBloodPressure(current?.bloodPressureSys, current?.bloodPressureDia)}
              severity={bpSeverity}
            />
            <MetricWidget title="RR" value={formatRespiratoryRate(current?.respiratoryRate)} severity={rrSeverity} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(260px, 1fr))", gap: "8px" }}>
            <MetricChart title="Nhịp tim (HR)" metric="heartRate" data={streamData} />
            <MetricChart title="Nồng độ oxy (SpO2)" metric="spo2" data={streamData} />
            <MetricChart title="Nhiệt độ cơ thể" metric="temperature" data={streamData} />
            <MetricChart title="Huyết áp (BP)" metric="bloodPressure" data={streamData} />
            <MetricChart title="Nhịp thở (RR)" metric="respiratoryRate" data={streamData} />
          </div>
        </div>
      )}
    </Card>
  );
}

const METRIC_SEVERITY_COLOR: Record<MetricSeverity, string> = {
  normal: "var(--severity-normal, #22c55e)",
  warning: "var(--severity-warning, #f59e0b)",
  critical: "var(--severity-critical, #ef4444)",
};

const MetricWidget = memo(function MetricWidget(props: { title: string; value: string; severity: MetricSeverity | null }) {
  const borderColor = props.severity ? METRIC_SEVERITY_COLOR[props.severity] : "var(--border-default)";
  return (
    <div style={{ border: "1px solid var(--border-default)", borderLeft: `3px solid ${borderColor}`, borderRadius: "var(--radius-md)", padding: "10px" }}>
      <small style={{ color: "var(--text-secondary)" }}>{props.title}</small>
      <div style={{ marginTop: "6px", fontSize: "18px", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{props.value}</div>
    </div>
  );
}, (prev, next) =>
  prev.title === next.title &&
  prev.value === next.value &&
  prev.severity === next.severity
);

const MetricChart = memo(function MetricChart(props: { title: string; metric: MetricKey; data: VitalsSample[] }) {
  const option = useMemo(() => buildMetricOption(props.metric, props.data), [props.metric, props.data]);
  return (
    <div style={{ border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "8px" }}>
      <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "6px" }}>{props.title}</div>
      <Suspense fallback={<Skeleton style={{ height: "180px" }} />}>
        <ReactECharts option={option} notMerge={false} lazyUpdate style={{ height: "180px", width: "100%" }} />
      </Suspense>
    </div>
  );
}, (prev, next) => {
  if (prev.title !== next.title) return false;
  if (prev.data === next.data) return true;
  if (prev.data.length !== next.data.length) return false;
  if (prev.data.length === 0) return true;
  const prevLast = prev.data[prev.data.length - 1];
  const nextLast = next.data[next.data.length - 1];
  return prevLast.timestamp === nextLast.timestamp;
});

function buildMetricOption(metric: MetricKey, data: VitalsSample[]): EChartsOption {
  const points = data.slice(-120);

  if (metric === "bloodPressure") {
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        formatter: (rawParams: unknown) => {
          const params = rawParams as EChartsTooltipParam | EChartsTooltipParam[];
          const rows = Array.isArray(params) ? params : [params];
          const axis = rows[0]?.axisValue;
          const header = `UTC+7: ${formatUtc7Time(axis)}`;
          const lines = rows.map((row) => `${row.marker ?? ""}${row.seriesName}: ${formatChartValue((row.data as [string, number])?.[1])}`).join("<br/>");
          return `${header}<br/>${lines}`;
        },
      },
      grid: { top: 20, right: 20, bottom: 26, left: 42 },
      xAxis: {
        type: "time",
        axisLabel: {
          color: "#64748b",
          formatter: (value: number) => formatUtc7Time(value),
        },
        axisLine: { lineStyle: { color: "#1e2d4a" } },
      },
      yAxis: {
        type: "value",
        min: 50,
        max: 190,
        axisLabel: { color: "#64748b" },
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
        },
        {
          name: "Tâm trương",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => [item.timestamp, item.bloodPressureDia]),
          lineStyle: { color: "#22C55E", width: 2 },
        },
      ],
    };
  }

  const configs: Record<
    Exclude<MetricKey, "bloodPressure">,
    { min: number; max: number; color: string; label: string; value: (item: VitalsSample) => number | null }
  > = {
    heartRate: {
      min: 40,
      max: 180,
      color: "#EF4444",
      label: "HR",
      value: (item) => item.heartRate,
    },
    spo2: {
      min: 80,
      max: 100,
      color: "#06B6D4",
      label: "SpO2",
      value: (item) => item.spo2,
    },
    temperature: {
      min: 34,
      max: 42,
      color: "#F59E0B",
      label: "Temp",
      value: (item) => item.temperature,
    },
    respiratoryRate: {
      min: 4,
      max: 40,
      color: "#8B5CF6",
      label: "RR",
      value: (item) => item.respiratoryRate,
    },
  };

  const config = configs[metric];
  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      formatter: (rawParams: unknown) => {
        const params = rawParams as EChartsTooltipParam | EChartsTooltipParam[];
        const rows = Array.isArray(params) ? params : [params];
        const axis = rows[0]?.axisValue;
        return `UTC+7: ${formatUtc7Time(axis)}<br/>${rows[0]?.seriesName ?? ""}: ${formatChartValue((rows[0]?.data as [string, number])?.[1])}`;
      },
    },
    grid: { top: 20, right: 20, bottom: 26, left: 42 },
    xAxis: {
      type: "time",
      axisLabel: {
        color: "#64748b",
        formatter: (value: number) => formatUtc7Time(value),
      },
      axisLine: { lineStyle: { color: "#1e2d4a" } },
    },
    yAxis: {
      type: "value",
      min: config.min,
      max: config.max,
      name: config.label,
      nameTextStyle: { color: config.color },
      axisLabel: { color: "#64748b" },
      splitLine: { lineStyle: { color: "#1e2d4a", type: "dashed" } },
    },
    series: [
      {
        name: config.label,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((item) => [item.timestamp, config.value(item)]),
        lineStyle: { color: config.color, width: 2 },
      },
    ],
  };
}

function respiratoryRateSeverity(value: number): MetricSeverity {
  if (value < 8 || value > 30) return "critical";
  if (value < 12 || value > 24) return "warning";
  return "normal";
}

function formatTemperature(value: number | null | undefined): string {
  return value != null ? `${value.toFixed(1)}°C` : "—";
}

function formatBloodPressure(sys: number | null | undefined, dia: number | null | undefined): string {
  return sys != null && dia != null ? `${Math.round(sys)}/${Math.round(dia)} mmHg` : "—";
}

function formatRespiratoryRate(value: number | null | undefined): string {
  return value != null ? `${Math.round(value)} /min` : "—";
}

function formatChartValue(value: number | null | undefined): string {
  return value != null ? Number(value).toFixed(1) : "—";
}

function severityToBadge(value: string): BadgeSeverity {
  if (value === "critical") return "critical";
  if (value === "warning") return "warning";
  if (value === "normal") return "normal";
  return "info";
}

function parseTimestamp(value: string | number | Date): Date {
  if (value instanceof Date) return value;
  if (typeof value === "number") return new Date(value);
  const text = String(value).trim();
  const hasZone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(text);
  return new Date(hasZone ? text : `${text}Z`);
}

function formatUtc7Time(value: string | number | Date | null | undefined): string {
  if (!value) return "--:--:--";
  const date = parseTimestamp(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return UTC7_TIME.format(date);
}

function inferExpectedIntervalMs(points: VitalsSample[]): number {
  if (points.length < 2) return 15000;
  const latest = parseTimestamp(points[points.length - 1].timestamp).getTime();
  const previous = parseTimestamp(points[points.length - 2].timestamp).getTime();
  const diff = Math.max(1000, latest - previous);
  return diff;
}
