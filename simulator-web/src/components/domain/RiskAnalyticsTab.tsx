import { Suspense, lazy, useMemo, useState, type CSSProperties } from "react";
import { type ColumnDef, type Table, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { UseQueryResult } from "@tanstack/react-query";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import { injectRiskScore, triggerRiskCalculation } from "../../services/analyticsApi";
import type { RiskContribution, RiskLevel, RiskScoreResponse, RiskType } from "../../types/analytics";
import { notify } from "../../utils/toast";

const LazyReactECharts = lazy(() => import("echarts-for-react"));
const LazyRiskHistoryChart = lazy(() =>
  import("../charts/RiskHistoryChart").then((module) => ({ default: module.RiskHistoryChart }))
);

export interface RiskAnalyticsTabProps {
  deviceId: string;
  riskQuery: UseQueryResult<RiskScoreResponse>;
}

const fieldStyle: CSSProperties = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  minHeight: "36px",
  padding: "0 10px",
};

export function RiskAnalyticsTab({ deviceId, riskQuery }: RiskAnalyticsTabProps) {
  const [riskType, setRiskType] = useState<RiskType>("general");
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("MEDIUM");
  const [injectScore, setInjectScore] = useState<string>("0.72");

  const riskColumns = useMemo<ColumnDef<RiskContribution>[]>(
    () => [
      { header: "Đặc trưng", accessorKey: "feature" },
      { header: "Giá trị", accessorKey: "value" },
      {
        header: "Trọng số",
        accessorKey: "weight",
        cell: (info) => {
          const value = Number(info.getValue());
          const sign = value >= 0 ? "+" : "";
          return `${sign}${value.toFixed(2)}`;
        },
      },
      {
        header: "Chiều tác động",
        accessorKey: "direction",
        cell: (info) => {
          const value = String(info.getValue());
          if (value === "up") return "Tăng rủi ro";
          if (value === "down") return "Giảm rủi ro";
          return "Trung tính";
        },
      },
    ],
    []
  );

  const riskTable = useReactTable({
    data: riskQuery.data?.explanation ?? [],
    columns: riskColumns,
    getCoreRowModel: getCoreRowModel(),
  });

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
          detail: { valueAnimation: true, formatter: (value: number) => value.toFixed(2), color: "#E2E8F0", fontSize: 20 },
          data: [{ value: score }],
        },
      ],
    };
  }, [riskQuery.data?.score]);

  const [isTriggering, setIsTriggering] = useState(false);
  const [isInjecting, setIsInjecting] = useState(false);

  const onTriggerRisk = async () => {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi chạy tính toán rủi ro.");
      return;
    }
    setIsTriggering(true);
    try {
      await triggerRiskCalculation(deviceId);
      await riskQuery.refetch();
      notify.success("Đã chạy tính toán rủi ro.");
    } catch {
      notify.error("Không thể chạy tính toán rủi ro.");
    } finally {
      setIsTriggering(false);
    }
  };

  const onInjectRisk = async () => {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi tiêm rủi ro.");
      return;
    }
    const parsed = Number(injectScore);
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
      notify.error("Điểm phải nằm trong khoảng 0.0 đến 1.0.");
      return;
    }
    setIsInjecting(true);
    try {
      await injectRiskScore({
        device_id: deviceId,
        risk_type: riskType,
        risk_level: riskLevel,
        score: parsed,
      });
      await riskQuery.refetch();
      notify.success("Đã tiêm rủi ro và tạo XAI.");
    } catch {
      notify.error("Không thể tiêm rủi ro.");
    } finally {
      setIsInjecting(false);
    }
  };

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
                <Badge severity={riskSeverity(riskQuery.data?.riskLevel ?? "LOW")}>{riskLevelLabel(riskQuery.data?.riskLevel ?? "LOW")}</Badge>
              </div>
              <small style={{ color: "var(--text-secondary)" }}>Mô hình: {riskQuery.data?.model ?? "-"}</small>
              <small style={{ color: "var(--text-secondary)" }}>Thuật toán: {riskQuery.data?.algorithm ?? "-"}</small>
              <small style={{ color: "var(--text-secondary)" }}>Lần tính gần nhất: {riskQuery.data?.calculatedAt ? new Date(riskQuery.data.calculatedAt).toLocaleString() : "-"}</small>
              <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                <Button variant="primary" onClick={onTriggerRisk} loading={isTriggering} disabled={isTriggering}>
                  {isTriggering ? "Đang tính toán…" : "Chạy tính toán rủi ro"}
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card header={<strong>Tiêm rủi ro (chế độ hỗ trợ)</strong>}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(130px, 1fr))", gap: "8px", alignItems: "end" }}>
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Loại rủi ro
            <select value={riskType} onChange={(event) => setRiskType(event.target.value as RiskType)} style={fieldStyle}>
              <option value="general">Tổng quát</option>
              <option value="stroke">Đột quỵ</option>
              <option value="cardiac">Tim mạch</option>
            </select>
          </label>
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Mức rủi ro
            <select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value as RiskLevel)} style={fieldStyle}>
              <option value="LOW">Thấp</option>
              <option value="MEDIUM">Trung bình</option>
              <option value="HIGH">Cao</option>
              <option value="CRITICAL">Nguy kịch</option>
            </select>
          </label>
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Điểm
            <input value={injectScore} onChange={(event) => setInjectScore(event.target.value)} style={fieldStyle} />
          </label>
          <Button variant="outline" onClick={onInjectRisk} loading={isInjecting} disabled={isInjecting}>
            {isInjecting ? "Đang tiêm…" : "Tiêm + tạo XAI"}
          </Button>
        </div>
      </Card>

      <Card header={<strong>Giải thích rủi ro (XAI)</strong>}>
        <TableRenderer table={riskTable} />
      </Card>

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

function TableRenderer<TData>(props: { table: Table<TData> }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          {props.table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} style={{ color: "var(--text-secondary)", fontSize: "12px", textTransform: "uppercase" }}>
              {headerGroup.headers.map((header) => (
                <th key={header.id} style={{ textAlign: "left", padding: "8px 0" }}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {props.table.getRowModel().rows.length === 0 ? (
            <tr>
              <td colSpan={Math.max(1, props.table.getAllLeafColumns().length)} style={{ padding: "12px 0", color: "var(--text-secondary)" }}>
                Không có dữ liệu
              </td>
            </tr>
          ) : (
            props.table.getRowModel().rows.map((row) => (
              <tr key={row.id} style={{ borderTop: "1px solid var(--border-default)" }}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} style={{ padding: "10px 0", color: "var(--text-primary)" }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
