import { Suspense, lazy, useMemo } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import { XaiInspectorPanel } from "./XaiInspectorPanel";
import type { RiskLevel, RiskScoreResponse } from "../../types/analytics";

const LazyReactECharts = lazy(() => import("echarts-for-react"));
const LazyRiskHistoryChart = lazy(() =>
  import("../charts/RiskHistoryChart").then((module) => ({ default: module.RiskHistoryChart })),
);

// ---------------------------------------------------------------------------
// RiskAnalyticsTab — Module D.4: read-only clinical view.
//
// Removed in this commit:
//   * "Chạy tính toán rủi ro" trigger button (mutation)
//   * "Tiêm rủi ro" inject form (mutation)
//   * Local `useState` pending flags
//
// Both moved to the Diagnostics surface (`<RiskInjectorPanel/>`) so
// `/analytics` no longer mutates state and is safe for clinical viewers.
// ---------------------------------------------------------------------------

export interface RiskAnalyticsTabProps {
  deviceId: string;
  riskQuery: UseQueryResult<RiskScoreResponse>;
}

export function RiskAnalyticsTab({ deviceId: _deviceId, riskQuery }: RiskAnalyticsTabProps) {
  const gaugeOption = useMemo(() => {
    const score = riskQuery.data?.score ?? 0;
    return {
      series: [
        {
          type: "gauge",
          startAngle: 210,
          endAngle: -30,
          min: 0,
          max: 1,
          splitNumber: 4,
          axisLine: {
            lineStyle: {
              width: 14,
              color: [
                [0.5, "#22C55E"],
                [0.75, "#F59E0B"],
                [1, "#EF4444"],
              ],
            },
          },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { distance: -44, color: "#94a3b8" },
          pointer: { width: 4, itemStyle: { color: "#E2E8F0" } },
          detail: {
            valueAnimation: true,
            formatter: (value: number) => value.toFixed(2),
            color: "#E2E8F0",
            fontSize: 20,
          },
          data: [{ value: score }],
        },
      ],
    };
  }, [riskQuery.data?.score]);

  return (
    <div style={{ display: "grid", gap: "10px" }}>
      {riskQuery.isLoading ? (
        <Skeleton style={{ height: "260px" }} />
      ) : (
        <Card>
          <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "12px", alignItems: "center" }}>
            <Suspense fallback={<Skeleton style={{ height: "220px" }} />}>
              <LazyReactECharts option={gaugeOption} style={{ height: "220px", width: "100%" }} />
            </Suspense>
            <div style={{ display: "grid", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <strong>Mức rủi ro</strong>
                <Badge severity={riskSeverity(riskQuery.data?.riskLevel ?? "LOW")}>
                  {riskLevelLabel(riskQuery.data?.riskLevel ?? "LOW")}
                </Badge>
              </div>
              <small style={{ color: "var(--text-secondary)" }}>
                Mô hình: {riskQuery.data?.model ?? "-"}
              </small>
              <small style={{ color: "var(--text-secondary)" }}>
                Thuật toán: {riskQuery.data?.algorithm ?? "-"}
              </small>
              <small style={{ color: "var(--text-secondary)" }}>
                Lần tính gần nhất:{" "}
                {riskQuery.data?.calculatedAt
                  ? new Date(riskQuery.data.calculatedAt).toLocaleString()
                  : "-"}
              </small>
              <small style={{ color: "var(--text-muted)", marginTop: "4px" }}>
                Cần chạy tính toán theo yêu cầu hoặc tiêm dữ liệu test? Mở trang{" "}
                <strong style={{ color: "var(--accent-cyan)" }}>Diagnostics → Risk Tools</strong>.
              </small>
            </div>
          </div>
        </Card>
      )}

      <XaiInspectorPanel contributions={riskQuery.data?.explanation ?? []} />

      <Card header={<strong>Lịch sử rủi ro (30 ngày)</strong>}>
        <Suspense fallback={<Skeleton style={{ height: "260px" }} />}>
          <LazyRiskHistoryChart points={riskQuery.data?.history ?? []} />
        </Suspense>
      </Card>
    </div>
  );
}

/* ── Private helpers ─────────────────────────────────────────────── */

function riskSeverity(level: RiskLevel) {
  if (level === "LOW") return "normal" as const;
  if (level === "MEDIUM") return "warning" as const;
  if (level === "HIGH") return "warning" as const;
  return "critical" as const;
}

function riskLevelLabel(level: RiskLevel) {
  if (level === "LOW") return "Thấp";
  if (level === "MEDIUM") return "Trung bình";
  if (level === "HIGH") return "Cao";
  return "Nguy kịch";
}
