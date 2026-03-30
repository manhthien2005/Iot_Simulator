import { Suspense, lazy, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type ColumnDef, type Table, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { Moon, ShieldAlert, Watch } from "lucide-react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton } from "../components/ui/Skeleton";
import { useDevices } from "../hooks/useDevices";
import { getRiskScore, getSleepSession, injectRiskScore, pushSleepSession, triggerRiskCalculation } from "../services/analyticsApi";
import type { RiskContribution, RiskLevel, RiskType, SleepHistoryRow } from "../types/analytics";
import { notify } from "../utils/toast";

const LazyReactECharts = lazy(() => import("echarts-for-react"));
const LazyHypnogramChart = lazy(() =>
  import("../components/charts/HypnogramChart").then((module) => ({ default: module.HypnogramChart }))
);
const LazyRiskHistoryChart = lazy(() =>
  import("../components/charts/RiskHistoryChart").then((module) => ({ default: module.RiskHistoryChart }))
);

type AnalyticsTab = "sleep" | "risk";

const fallbackBanner = "Chế độ hiện thực giấc ngủ: mẫu dự phòng (giai đoạn 5A). Hãy tải Sleep-EDF để nâng cấp.";

function riskSeverity(level: RiskLevel) {
  if (level === "LOW") return "normal" as const;
  if (level === "MEDIUM") return "warning" as const;
  if (level === "HIGH") return "warning" as const;
  return "critical" as const;
}

export function AnalyticsPage() {
  const [tab, setTab] = useState<AnalyticsTab>("sleep");
  const { data: devices = [], isLoading: devicesLoading } = useDevices();
  const [deviceId, setDeviceId] = useState<string>("");
  const [riskType, setRiskType] = useState<RiskType>("general");
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("MEDIUM");
  const [injectScore, setInjectScore] = useState<string>("0.72");
  const pushSleepMutation = useMutation({
    mutationFn: async () => pushSleepSession(deviceId),
  });

  useEffect(() => {
    if (!devices.length) {
      setDeviceId("");
      return;
    }
    if (!deviceId || !devices.some((device) => device.id === deviceId)) {
      setDeviceId(devices[0].id);
    }
  }, [deviceId, devices]);

  const sleepQuery = useQuery({
    queryKey: ["analytics", "sleep", deviceId],
    queryFn: () => getSleepSession(deviceId),
    enabled: Boolean(deviceId),
    refetchInterval: 15000,
  });

  const riskQuery = useQuery({
    queryKey: ["analytics", "risk", deviceId],
    queryFn: () => getRiskScore(deviceId),
    enabled: Boolean(deviceId),
    refetchInterval: 10000,
  });

  const sleepColumns = useMemo<ColumnDef<SleepHistoryRow>[]>(
    () => [
      { header: "Ngày", accessorKey: "date" },
      { header: "Điểm", accessorKey: "score" },
      {
        header: "Hiệu suất",
        accessorKey: "efficiency",
        cell: (info) => `${Number(info.getValue()).toFixed(1)}%`,
      },
      {
        header: "Thời lượng",
        accessorKey: "durationMinutes",
        cell: (info) => `${Math.round(Number(info.getValue()) / 60)}h ${Math.round(Number(info.getValue()) % 60)}m`,
      },
      {
        header: "Nhịp tim TB",
        accessorKey: "avgHeartRate",
        cell: (info) => `${Math.round(Number(info.getValue()))} bpm`,
      },
      {
        header: "SpO2 thấp nhất",
        accessorKey: "minSpo2",
        cell: (info) => `${Math.round(Number(info.getValue()))}%`,
      },
    ],
    []
  );

  const sleepTable = useReactTable({
    data: sleepQuery.data?.history ?? [],
    columns: sleepColumns,
    getCoreRowModel: getCoreRowModel(),
  });

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

  const onTriggerRisk = async () => {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi chạy tính toán rủi ro.");
      return;
    }
    await triggerRiskCalculation(deviceId);
    await riskQuery.refetch();
    notify.success("Đã chạy tính toán rủi ro.");
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
    await injectRiskScore({
      device_id: deviceId,
      risk_type: riskType,
      risk_level: riskLevel,
      score: parsed,
    });
    await riskQuery.refetch();
    notify.success("Đã tiêm rủi ro và tạo XAI.");
  };

  const onPushSleep = async () => {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi đẩy dữ liệu.");
      return;
    }
    try {
      await pushSleepMutation.mutateAsync();
      notify.success("Đã đẩy dữ liệu giấc ngủ lên backend mobile.");
    } catch {
      notify.error("Không thể đẩy dữ liệu giấc ngủ lên backend mobile.");
    }
  };

  if (devicesLoading) {
    return (
      <section style={{ display: "grid", gap: "12px" }}>
        <h1 className="page-title">Phân tích</h1>
        <Skeleton style={{ height: "220px" }} />
      </section>
    );
  }

  if (!devices.length) {
    return (
      <section style={{ display: "grid", gap: "12px" }}>
        <h1 className="page-title">Phân tích</h1>
        <EmptyState icon={Watch} title="Chưa có thiết bị" description="Tạo thiết bị để kích hoạt phân tích giấc ngủ và rủi ro." />
      </section>
    );
  }

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <h1 className="page-title">Phân tích</h1>
          <p className="page-subtitle">Phát lại giấc ngủ và phân tích rủi ro với chế độ fallback cho Sleep-EDF.</p>
        </div>
        <select
          value={deviceId}
          onChange={(event) => setDeviceId(event.target.value)}
          style={{
            background: "var(--bg-base)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            minHeight: "36px",
            padding: "0 10px",
          }}
        >
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name}
            </option>
          ))}
        </select>
      </div>

      <div style={{ display: "flex", gap: "8px" }}>
        <Button variant={tab === "sleep" ? "primary" : "secondary"} onClick={() => setTab("sleep")} leftIcon={<Moon size={14} />}>
          Giấc ngủ
        </Button>
        <Button variant={tab === "risk" ? "primary" : "secondary"} onClick={() => setTab("risk")} leftIcon={<ShieldAlert size={14} />}>
          Rủi ro
        </Button>
      </div>

      {tab === "sleep" ? (
        <div style={{ display: "grid", gap: "10px" }}>
          <div style={{ border: "1px solid rgba(6,182,212,0.35)", borderRadius: "var(--radius-md)", padding: "8px 12px", color: "#67E8F9", background: "rgba(6,182,212,0.08)" }}>
            {sleepQuery.data?.banner ?? fallbackBanner}
          </div>

          <Card>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
              <div style={{ display: "grid", gap: "4px" }}>
                <strong>Đẩy dữ liệu giấc ngủ</strong>
                <small style={{ color: "var(--text-secondary)" }}>Gửi phiên Sleep hiện tại qua endpoint push riêng, không cần gọi GET có side effect.</small>
              </div>
              <Button variant="primary" onClick={onPushSleep} loading={pushSleepMutation.isPending} disabled={!deviceId || sleepQuery.isLoading}>
                Đẩy dữ liệu
              </Button>
            </div>
          </Card>

          {sleepQuery.isLoading ? (
            <Skeleton style={{ height: "240px" }} />
          ) : (
            <Card>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(120px, 1fr))", gap: "10px" }}>
                <SleepMetric title="Điểm" value={`${sleepQuery.data?.score ?? 0}/100`} />
                <SleepMetric title="Hiệu suất" value={`${sleepQuery.data?.efficiency ?? 0}%`} />
                <SleepMetric title="Thời lượng" value={formatDuration(sleepQuery.data?.durationMinutes ?? 0)} />
                <SleepMetric title="Nhịp tim TB" value={`${Math.round(sleepQuery.data?.avgHeartRate ?? 0)} bpm`} />
                <SleepMetric title="SpO2 thấp nhất" value={`${Math.round(sleepQuery.data?.minSpo2 ?? 0)}%`} />
              </div>
            </Card>
          )}

          <Card header={<strong>Biểu đồ hypnogram</strong>}>
            <Suspense fallback={<ChartFallback height={260} />}>
              <LazyHypnogramChart phases={sleepQuery.data?.phases ?? []} />
            </Suspense>
          </Card>

          <Card header={<strong>Lịch sử giấc ngủ (7 đêm)</strong>}>
            <TableRenderer table={sleepTable} />
          </Card>
        </div>
      ) : (
        <div style={{ display: "grid", gap: "10px" }}>
          {riskQuery.isLoading ? (
            <Skeleton style={{ height: "260px" }} />
          ) : (
            <Card>
              <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "12px", alignItems: "center" }}>
                <Suspense fallback={<ChartFallback height={220} />}>
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
                    <Button variant="primary" onClick={onTriggerRisk}>
                      Chạy tính toán rủi ro
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
              <Button variant="outline" onClick={onInjectRisk}>
                Tiêm + tạo XAI
              </Button>
            </div>
          </Card>

          <Card header={<strong>Giải thích rủi ro (XAI)</strong>}>
            <TableRenderer table={riskTable} />
          </Card>

          <Card header={<strong>Lịch sử rủi ro (30 ngày)</strong>}>
            <Suspense fallback={<ChartFallback height={260} />}>
              <LazyRiskHistoryChart points={riskQuery.data?.history ?? []} />
            </Suspense>
          </Card>
        </div>
      )}
    </section>
  );
}

function SleepMetric(props: { title: string; value: string }) {
  return (
    <div style={{ border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "10px" }}>
      <small style={{ color: "var(--text-secondary)" }}>{props.title}</small>
      <div style={{ marginTop: "6px", fontFamily: "var(--font-mono)", fontSize: "18px", fontWeight: 700 }}>{props.value}</div>
    </div>
  );
}

function ChartFallback(props: { height: number }) {
  return <Skeleton style={{ height: `${props.height}px` }} />;
}

function formatDuration(totalMinutes: number) {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours} giờ ${minutes} phút`;
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

function riskLevelLabel(level: RiskLevel) {
  if (level === "LOW") return "Thấp";
  if (level === "MEDIUM") return "Trung bình";
  if (level === "HIGH") return "Cao";
  return "Nguy kịch";
}

const fieldStyle: CSSProperties = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  minHeight: "36px",
  padding: "0 10px",
};
