import { Suspense, lazy, useMemo, type CSSProperties } from "react";
import { type ColumnDef, type Table, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useMutation, type UseQueryResult } from "@tanstack/react-query";
import { Moon } from "lucide-react";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Skeleton } from "../ui/Skeleton";
import { BackfillCard } from "./BackfillCard";
import { pushSleepForDate } from "../../services/analyticsApi";
import type { DbSleepHistoryRow, SleepHistoryRow, SleepSessionResponse } from "../../types/analytics";
import { notify } from "../../utils/toast";

const LazyHypnogramChart = lazy(() =>
  import("../charts/HypnogramChart").then((module) => ({ default: module.HypnogramChart }))
);

const sleepScenarioOptions = [
  { id: "good_sleep_night", label: "Đêm ngủ tốt (AASM chuẩn)" },
  { id: "fragmented_sleep", label: "Ngủ phân mảnh" },
  { id: "sleep_apnea_mild", label: "Ngưng thở nhẹ (AHI ~10)" },
  { id: "sleep_apnea_severe", label: "Ngưng thở nặng (AHI >30)" },
  { id: "insomnia_pattern", label: "Mất ngủ kinh niên" },
  { id: "elderly_normal", label: "Ngủ người cao tuổi (bình thường)" },
] as const;

const fallbackBanner = "Chế độ hiện thực giấc ngủ: mẫu dự phòng (giai đoạn 5A). Hãy tải Sleep-EDF để nâng cấp.";

export interface SleepAnalyticsTabProps {
  deviceId: string;
  sleepQuery: UseQueryResult<SleepSessionResponse>;
  dbHistoryQuery: UseQueryResult<DbSleepHistoryRow[]>;
  sleepScenarioId: string;
  onSleepScenarioIdChange: (id: string) => void;
  targetDate: string;
  onTargetDateChange: (date: string) => void;
  yesterdayStr: string;
  yesterdayInputMax: string;
  oldestInputMin: string;
}

const fieldStyle: CSSProperties = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  minHeight: "36px",
  padding: "0 10px",
};

export function SleepAnalyticsTab({
  deviceId,
  sleepQuery,
  dbHistoryQuery,
  sleepScenarioId,
  onSleepScenarioIdChange,
  targetDate,
  onTargetDateChange,
  yesterdayStr,
  yesterdayInputMax,
  oldestInputMin,
}: SleepAnalyticsTabProps) {
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
          <Button size="sm" variant="outline" onClick={() => onTargetDateChange(row.original.date)}>
            Dùng ngày này
          </Button>
        ),
      },
    ],
    [onTargetDateChange]
  );

  const dbHistoryTable = useReactTable({
    data: dbHistoryQuery.data ?? [],
    columns: dbHistoryColumns,
    getCoreRowModel: getCoreRowModel(),
  });

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

  return (
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
          <Suspense fallback={<Skeleton style={{ height: "260px" }} />}>
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
                <select value={sleepScenarioId} onChange={(event) => onSleepScenarioIdChange(event.target.value)} style={fieldStyle}>
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
                  onChange={(event) => onTargetDateChange(event.target.value)}
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
  );
}

/* ── Private helpers ─────────────────────────────────────────────── */

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
