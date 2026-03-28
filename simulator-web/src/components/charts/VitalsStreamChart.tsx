import { useDeferredValue, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { VitalsSample } from "../../types/vitals";

interface VitalsStreamChartProps {
  data: VitalsSample[];
}

export function VitalsStreamChart({ data }: VitalsStreamChartProps) {
  const deferred = useDeferredValue(data);
  const isStale = deferred.length > 0 ? Date.now() - new Date(deferred[deferred.length - 1].timestamp).getTime() > 5000 : false;

  const option = useMemo(() => {
    const points = deferred.slice(-60);
    const hr = points.map((item) => [item.timestamp, item.heartRate]);
    const spo2 = points.map((item) => [item.timestamp, item.spo2]);
    const temp = points.map((item) => [item.timestamp, item.temperature]);
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1a2235",
        borderColor: "#1e2d4a",
      },
      grid: { top: 24, right: 58, bottom: 28, left: 46 },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#1e2d4a" } },
        axisLabel: { color: "#64748b" },
      },
      yAxis: [
        {
          type: "value",
          min: 40,
          max: 200,
          name: "HR",
          nameTextStyle: { color: "#ef4444" },
          splitLine: { lineStyle: { color: "#1e2d4a", type: "dashed" } },
        },
        {
          type: "value",
          min: 70,
          max: 100,
          name: "SpO2",
          position: "right",
          nameTextStyle: { color: "#06b6d4" },
          splitLine: { show: false },
        },
        {
          type: "value",
          min: 34,
          max: 42,
          name: "Temp",
          position: "right",
          offset: 48,
          nameTextStyle: { color: "#f59e0b" },
          splitLine: { show: false },
        },
      ],
      series: [
        { name: "HR", type: "line", smooth: true, yAxisIndex: 0, showSymbol: false, data: hr, lineStyle: { color: "#ef4444" } },
        { name: "SpO2", type: "line", smooth: true, yAxisIndex: 1, showSymbol: false, data: spo2, lineStyle: { color: "#06b6d4" } },
        { name: "Temp", type: "line", smooth: true, yAxisIndex: 2, showSymbol: false, data: temp, lineStyle: { color: "#f59e0b" } },
      ],
    };
  }, [deferred]);

  return (
    <div style={{ display: "grid", gap: "8px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong>Sinh hiệu trực tiếp (60 giây)</strong>
        {isStale ? <span className="stale-badge">TRỄ DỮ LIỆU</span> : null}
      </div>
      <ReactECharts option={option} notMerge={false} lazyUpdate style={{ height: "280px", width: "100%" }} />
    </div>
  );
}
