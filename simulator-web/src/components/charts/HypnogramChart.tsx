import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { SleepStage, SleepStageSegment } from "../../types/analytics";

interface HypnogramChartProps {
  phases: SleepStageSegment[];
}

const stageOrder: SleepStage[] = ["deep", "light", "rem", "awake"];

const stageColor: Record<SleepStage, string> = {
  deep: "#1E40AF",
  light: "#06B6D4",
  rem: "#8B5CF6",
  awake: "rgba(239,68,68,0.4)",
};

const stageLabel: Record<SleepStage, string> = {
  deep: "Ngủ sâu",
  light: "Ngủ nông",
  rem: "REM",
  awake: "Thức",
};

export function HypnogramChart({ phases }: HypnogramChartProps) {
  const option = useMemo(() => {
    const rows = phases
      .map((phase) => ({
        stage: phase.stage,
        value: [new Date(phase.start).getTime(), new Date(phase.end).getTime(), stageOrder.indexOf(phase.stage)],
      }))
      .filter((item) => item.value[2] >= 0);

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        formatter: (params: { dataIndex: number }) => {
          const segment = rows[params.dataIndex];
          if (!segment) return "";
          const start = new Date(segment.value[0]).toLocaleTimeString();
          const end = new Date(segment.value[1]).toLocaleTimeString();
          return `${stageLabel[segment.stage]}<br/>${start} -> ${end}`;
        },
      },
      grid: { top: 24, left: 54, right: 20, bottom: 30 },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#1e2d4a" } },
        splitLine: { lineStyle: { color: "#1e2d4a", type: "dashed" } },
        axisLabel: { color: "#64748b" },
      },
      yAxis: {
        type: "category",
        data: stageOrder.map((stage) => stageLabel[stage]),
        axisLabel: { color: "#94a3b8" },
        axisLine: { lineStyle: { color: "#1e2d4a" } },
      },
      series: [
        {
          type: "custom",
          renderItem: (params: { dataIndex: number }, api: { value: (idx: number) => number; coord: (value: number[]) => number[]; size: (value: number[]) => number[]; style: (style?: object) => object }) => {
            const category = api.value(2);
            const start = api.coord([api.value(0), category]);
            const end = api.coord([api.value(1), category]);
            const barHeight = api.size([0, 1])[1] * 0.56;
            const phase = rows[params.dataIndex];
            return {
              type: "rect",
              shape: {
                x: start[0],
                y: start[1] - barHeight / 2,
                width: Math.max(1, end[0] - start[0]),
                height: barHeight,
              },
              style: api.style({ fill: phase ? stageColor[phase.stage] : "#64748b" }),
            };
          },
          data: rows,
          encode: { x: [0, 1], y: 2 },
        },
      ],
    };
  }, [phases]);

  if (!phases.length) {
    return <p style={{ margin: 0, color: "var(--text-secondary)" }}>Không đủ dữ liệu để vẽ dòng thời gian.</p>;
  }

  return <ReactECharts option={option} style={{ height: "260px", width: "100%" }} />;
}
