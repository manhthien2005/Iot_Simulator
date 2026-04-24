import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { RiskHistoryPoint } from "../../types/analytics";

interface RiskHistoryChartProps {
  points: RiskHistoryPoint[];
}

export function RiskHistoryChart({ points }: RiskHistoryChartProps) {
  const option = useMemo(() => {
    return {
      backgroundColor: "transparent",
      tooltip: { trigger: "axis" },
      grid: { top: 24, left: 44, right: 22, bottom: 30 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: points.map((point) => point.date.slice(5)),
        axisLabel: { color: "#64748b", interval: 4 },
        axisLine: { lineStyle: { color: "#1e2d4a" } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 1,
        axisLabel: { color: "#64748b" },
        axisLine: { lineStyle: { color: "#1e2d4a" } },
        splitLine: { lineStyle: { color: "#1e2d4a", type: "dashed" } },
      },
      series: [
        {
          type: "line",
          smooth: true,
          data: points.map((p) => p.score),
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(99,102,241,0.45)" },
                { offset: 1, color: "rgba(99,102,241,0.04)" },
              ],
            },
          },
          lineStyle: { color: "#6366F1", width: 2 },
          showSymbol: false,
          markLine: {
            symbol: ["none", "none"],
            label: { color: "#94a3b8" },
            data: [
              { yAxis: 0.5, lineStyle: { color: "#F59E0B", width: 1.5 }, name: "cảnh báo" },
              { yAxis: 0.75, lineStyle: { color: "#EF4444", width: 1.5, type: "dashed" }, name: "nguy cấp" },
            ],
          },
        },
      ],
    };
  }, [points]);

  if (points.length < 2) {
    return <p style={{ margin: 0, color: "var(--text-secondary)" }}>Cần ít nhất 2 điểm dữ liệu để hiển thị xu hướng.</p>;
  }

  return <ReactECharts option={option} style={{ height: "260px", width: "100%" }} />;
}
