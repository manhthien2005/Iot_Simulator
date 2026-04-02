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
import {
  backfillSleep,
  getDbSleepHistory,
  getRiskScore,
  getSleepSession,
  injectRiskScore,
  pushSleepForDate,
  triggerRiskCalculation,
} from "../services/analyticsApi";
import type {
  BackfillSleepResponse,
  DbSleepHistoryRow,
  RiskContribution,
  RiskLevel,
  RiskType,
  SleepHistoryRow,
} from "../types/analytics";
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
const sleepScenarioOptions = [
  { id: "good_sleep_night", label: "Đêm ngủ tốt (AASM chuẩn)" },
  { id: "fragmented_sleep", label: "Ngủ phân mảnh" },
  { id: "sleep_apnea_mild", label: "Ngưng thở nhẹ (AHI ~10)" },
  { id: "sleep_apnea_severe", label: "Ngưng thở nặng (AHI >30)" },
  { id: "insomnia_pattern", label: "Mất ngủ kinh niên" },
  { id: "elderly_normal", label: "Ngủ người cao tuổi (bình thường)" },
] as const;

function riskSeverity(level: RiskLevel) {
  if (level === "LOW") return "normal" as const;
  if (level === "MEDIUM") return "warning" as const;
  if (level === "HIGH") return "warning" as const;
  return "critical" as const;
}

function BackfillCard({ deviceId, onCompleted }: { deviceId: string; onCompleted?: () => void | Promise<void> }) {
  const [days, setDays] = useState(30);
  const [scenarioId, setScenarioId] = useState("good_sleep_night");
  const [result, setResult] = useState<BackfillSleepResponse | null>(null);

  const backfillMutation = useMutation({
    mutationFn: () =>
      backfillSleep({
        device_id: deviceId,
        days_behind: days,
        scenario_id: scenarioId,
      }),
    onSuccess: async (data) => {
      setResult(data);
      notify.success(`Backfill hoàn tất: ${data.pushed}/${data.total_days} ngày thành công.`);
      await onCompleted?.();
    },
    onError: () => {
      notify.error("Backfill thất bại. Kiểm tra kết nối Backend.");
    },
  });

  return (
    <Card header={<strong>Tiêm dữ liệu lịch sử giấc ngủ</strong>}>
      <div style={{ display: "grid", gap: "10px" }}>
        <small style={{ color: "var(--text-secondary)" }}>
          Bơm N ngày dữ liệu giấc ngủ vào DB để AI có đủ lịch sử phân tích. Mỗi ngày được gán timestamp ngẫu nhiên
          trong khung 21:00-01:00.
        </small>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr auto",
            gap: "8px",
            alignItems: "end",
          }}
        >
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Kịch bản
            <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)} style={fieldStyle}>
              {sleepScenarioOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Số ngày (1-90)
            <input
              type="number"
              min={1}
              max={90}
              value={days}
              onChange={(event) => {
                const nextValue = Number(event.target.value);
                if (!Number.isFinite(nextValue)) {
                  setDays(1);
                  return;
                }
                setDays(Math.max(1, Math.min(90, nextValue)));
              }}
              style={fieldStyle}
            />
          </label>
          <Button
            variant="outline"
            onClick={() => backfillMutation.mutate()}
            loading={backfillMutation.isPending}
            disabled={!deviceId}
          >
            Bắt đầu backfill
          </Button>
        </div>

        {result ? (
          <div
            style={{
              borderRadius: "var(--radius-md)",
              padding: "10px 12px",
              background: result.errors.length === 0 ? "rgba(34,197,94,0.08)" : "rgba(245,158,11,0.08)",
              border: `1px solid ${
                result.errors.length === 0 ? "rgba(34,197,94,0.3)" : "rgba(245,158,11,0.35)"
              }`,
              fontSize: "13px",
            }}
          >
            ✅ {result.pushed}/{result.total_days} ngày thành công
            {result.skipped > 0 ? ` | ⚠️ ${result.skipped} ngày bị bỏ qua` : null}
            {result.errors.length > 0 ? (
              <details style={{ marginTop: "6px" }}>
                <summary style={{ cursor: "pointer", color: "var(--text-secondary)" }}>{result.errors.length} lỗi chi tiết</summary>
                <ul style={{ margin: "6px 0 0", paddingLeft: "16px", color: "var(--text-secondary)" }}>
                  {result.errors.map((error, index) => (
                    <li key={`${index}-${error}`} style={{ fontSize: "12px" }}>
                      {error}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}

export function AnalyticsPage() {
  const [tab, setTab] = useState<AnalyticsTab>("sleep");
  const { data: devices = [], isLoading: devicesLoading } = useDevices();
  const [deviceId, setDeviceId] = useState<string>("");
  const [riskType, setRiskType] = useState<RiskType>("general");
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("MEDIUM");
  const [injectScore, setInjectScore] = useState<string>("0.72");
  const [sleepScenarioId, setSleepScenarioId] = useState("good_sleep_night");
  const [targetDate, setTargetDate] = useState(() => {
    const value = new Date();
    value.setDate(value.getDate() - 1);
    return toDateInputValue(value);
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

  const yesterdayStr = useMemo(() => {
    const value = new Date();
    value.setHours(0, 0, 0, 0);
    value.setDate(value.getDate() - 1);
    return value.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }, []);

  const yesterdayInputMax = useMemo(() => {
    const value = new Date();
    value.setHours(0, 0, 0, 0);
    value.setDate(value.getDate() - 1);
    return toDateInputValue(value);
  }, []);

  const oldestInputMin = useMemo(() => {
    const value = new Date();
    value.setHours(0, 0, 0, 0);
    value.setDate(value.getDate() - 365);
    return toDateInputValue(value);
  }, []);

  const sleepQuery = useQuery({
    queryKey: ["analytics", "sleep", deviceId],
    queryFn: () => getSleepSession(deviceId),
    enabled: Boolean(deviceId),
    refetchInterval: 15000,
  });

  const dbHistoryQuery = useQuery({
    queryKey: ["analytics", "sleep", "db-history", deviceId],
    queryFn: () => getDbSleepHistory(deviceId, 30),
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

  const dbHistoryColumns = useMemo<ColumnDef<DbSleepHistoryRow>[]>(
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
        cell: (info) => formatDuration(Number(info.getValue())),
      },
      { header: "Lần thức", accessorKey: "wakeCount" },
      {
        header: "Phases",
        accessorKey: "phases",
        cell: (info) => formatPhaseSummary(info.getValue() as Record<string, number>),
      },
      {
        header: "Khung giờ",
        cell: ({ row }) => formatSleepWindow(row.original.startTime, row.original.endTime),
      },
      {
        header: "Ghi đè",
        cell: ({ row }) => (
          <Button size="sm" variant="outline" onClick={() => setTargetDate(row.original.date)}>
            Dùng ngày này
          </Button>
        ),
      },
    ],
    []
  );

  const dbHistoryTable = useReactTable({
    data: dbHistoryQuery.data ?? [],
    columns: dbHistoryColumns,
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

  const pushDateMutation = useMutation({
    mutationFn: () =>
      pushSleepForDate({
        device_id: deviceId,
        target_date: targetDate,
        scenario_id: sleepScenarioId,
      }),
    onSuccess: async (result) => {
      await dbHistoryQuery.refetch();
      const statusLabel = result.was_overwritten ? "Đã ghi đè" : "Đã tạo mới";
      notify.success(
        `${statusLabel} phiên ngày ${result.target_date}. Điểm ${result.sleep_score}/100, thời lượng ${formatDuration(
          result.duration_minutes
        )}.`
      );
    },
    onError: (error) => {
      notify.error(extractApiError(error, "Không thể push dữ liệu giấc ngủ cho ngày đã chọn."));
    },
  });

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

  const onPushSleepForDate = async () => {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi đẩy dữ liệu.");
      return;
    }
    if (!targetDate) {
      notify.error("Chọn ngày cần push trước khi tiếp tục.");
      return;
    }
    if (targetDate > yesterdayInputMax) {
      notify.error("Chỉ được chọn ngày quá khứ, tối đa là hôm qua.");
      return;
    }
    await pushDateMutation.mutateAsync();
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
        <div style={{ display: "grid", gap: "14px" }}>
          <div
            style={{
              display: "grid",
              gap: "12px",
              border: "1px solid rgba(6,182,212,0.35)",
              borderRadius: "var(--radius-lg)",
              padding: "14px",
              background: "linear-gradient(180deg, rgba(6,182,212,0.08), rgba(15,23,42,0.08))",
            }}
          >
            <SectionHeader title="Xem trước giấc ngủ" badge="Simulator Registry" severity="info" />
            <small style={{ color: "var(--text-secondary)" }}>
              Hypnogram và metrics ở vùng này lấy từ simulator registry hoặc Sleep-EDF. Dữ liệu chỉ xuất hiện trong DB
              sau khi bạn push hoặc backfill.
            </small>
            <div
              style={{
                border: "1px solid rgba(6,182,212,0.35)",
                borderRadius: "var(--radius-md)",
                padding: "8px 12px",
                color: "#67E8F9",
                background: "rgba(6,182,212,0.08)",
              }}
            >
              {sleepQuery.data?.banner ?? fallbackBanner}
            </div>

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

            <Card
              header={
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
                  <strong>Lịch sử preview (7 đêm)</strong>
                  <Badge severity="info">Simulator Only</Badge>
                </div>
              }
            >
              <TableRenderer table={sleepTable} />
            </Card>

            <Card header={<strong>Đẩy dữ liệu giấc ngủ vào DB</strong>}>
              <div style={{ display: "grid", gap: "10px" }}>
                <small style={{ color: "var(--text-secondary)" }}>
                  Chọn scenario và ngày quá khứ để tạo mới hoặc ghi đè một phiên đã lưu. Date picker khóa từ{" "}
                  <span style={{ color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>{yesterdayStr}</span> trở về trước.
                </small>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(220px, 1.2fr) minmax(180px, 0.8fr) auto",
                    gap: "8px",
                    alignItems: "end",
                  }}
                >
                  <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
                    Kịch bản
                    <select value={sleepScenarioId} onChange={(event) => setSleepScenarioId(event.target.value)} style={fieldStyle}>
                      {sleepScenarioOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
                    Ngày cần push
                    <input
                      type="date"
                      min={oldestInputMin}
                      max={yesterdayInputMax}
                      value={targetDate}
                      onChange={(event) => setTargetDate(event.target.value)}
                      style={fieldStyle}
                    />
                  </label>
                  <Button
                    variant="primary"
                    onClick={onPushSleepForDate}
                    loading={pushDateMutation.isPending}
                    disabled={!deviceId || sleepQuery.isLoading}
                  >
                    Đẩy / Ghi đè
                  </Button>
                </div>
              </div>
            </Card>

            <BackfillCard
              deviceId={deviceId}
              onCompleted={() => {
                void dbHistoryQuery.refetch();
              }}
            />
          </div>

          <SectionDivider label="Lịch sử đã lưu trong Database" />

          <div
            style={{
              display: "grid",
              gap: "12px",
              border: "1px solid rgba(34,197,94,0.3)",
              borderRadius: "var(--radius-lg)",
              padding: "14px",
              background: "linear-gradient(180deg, rgba(34,197,94,0.08), rgba(15,23,42,0.08))",
            }}
          >
            <SectionHeader title="Lịch sử giấc ngủ từ DB" badge="Backend Database" severity="normal" />
            <small style={{ color: "var(--text-secondary)" }}>
              Đây là dữ liệu đã được lưu thật trong bảng `sleep_sessions`. Nếu cần sửa một ngày đã có, bấm{" "}
              <strong>Dùng ngày này</strong> rồi push lại với scenario mong muốn.
            </small>

            {dbHistoryQuery.isLoading ? (
              <Skeleton style={{ height: "240px" }} />
            ) : dbHistoryQuery.data && dbHistoryQuery.data.length > 0 ? (
              <Card
                header={
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
                    <strong>30 đêm gần nhất</strong>
                    <Badge severity="normal">{dbHistoryQuery.data.length} bản ghi</Badge>
                  </div>
                }
              >
                <TableRenderer table={dbHistoryTable} />
              </Card>
            ) : (
              <Card>
                <EmptyState
                  icon={Moon}
                  title="Chưa có lịch sử trong DB"
                  description="Push một ngày hoặc chạy backfill để vùng Database bắt đầu có dữ liệu thật."
                />
              </Card>
            )}
          </div>
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

function SectionHeader(props: { title: string; badge: string; severity: "info" | "normal" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
      <strong style={{ fontSize: "16px" }}>{props.title}</strong>
      <Badge severity={props.severity}>{props.badge}</Badge>
    </div>
  );
}

function SectionDivider(props: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "var(--text-secondary)" }}>
      <div style={{ flex: 1, height: "1px", background: "var(--border-default)" }} />
      <span style={{ fontSize: "12px", letterSpacing: "0.06em", textTransform: "uppercase" }}>{props.label}</span>
      <div style={{ flex: 1, height: "1px", background: "var(--border-default)" }} />
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

function formatPhaseSummary(phases: Record<string, number>) {
  const segments = [
    ["Light", phases.light ?? 0],
    ["Deep", phases.deep ?? 0],
    ["REM", phases.rem ?? 0],
    ["Awake", phases.awake ?? 0],
  ] as const;

  const summary = segments
    .filter(([, minutes]) => minutes > 0)
    .map(([label, minutes]) => `${label} ${minutes}m`)
    .join(" • ");
  return summary || "-";
}

function formatSleepWindow(startTime: string, endTime: string) {
  if (!startTime || !endTime) {
    return "-";
  }
  const start = new Date(startTime);
  const end = new Date(endTime);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return "-";
  }
  const options: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" };
  return `${start.toLocaleTimeString("vi-VN", options)} → ${end.toLocaleTimeString("vi-VN", options)}`;
}

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function extractApiError(error: unknown, fallback: string) {
  if (typeof error === "object" && error && "response" in error) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }
  }
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return fallback;
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
