import { useMemo } from "react";
import { type ColumnDef, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { UseQueryResult } from "@tanstack/react-query";
import { Moon } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { Skeleton } from "../../ui/Skeleton";
import { TableRenderer } from "../../ui/TableRenderer";
import type { DbSleepHistoryRow } from "../../../types/analytics";

// ---------------------------------------------------------------------------
// SleepHistoryPanel — DB-backed table of the last 30 sleep_sessions rows.
//
// Reads `dbHistoryQuery.data` (already polled by the parent) and renders a
// table with a "Dùng ngày này" action that hands the date back through
// `onUseDate` so the operator can immediately re-push that night with a
// different scenario.
// ---------------------------------------------------------------------------

interface SleepHistoryPanelProps {
  dbHistoryQuery: UseQueryResult<DbSleepHistoryRow[]>;
  onUseDate: (date: string) => void;
}

export function SleepHistoryPanel({ dbHistoryQuery, onUseDate }: SleepHistoryPanelProps) {
  const columns = useMemo<ColumnDef<DbSleepHistoryRow>[]>(
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
          <Button size="sm" variant="outline" onClick={() => onUseDate(row.original.date)}>
            Dùng ngày này
          </Button>
        ),
      },
    ],
    [onUseDate]
  );

  const table = useReactTable({
    data: dbHistoryQuery.data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (dbHistoryQuery.isLoading) {
    return <Skeleton style={{ height: "240px" }} />;
  }

  if (!dbHistoryQuery.data || dbHistoryQuery.data.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={Moon}
          title="Chưa có lịch sử trong DB"
          description="Push một ngày hoặc chạy backfill để bắt đầu thấy dữ liệu thật ở vùng này."
        />
      </Card>
    );
  }

  return (
    <Card
      header={
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "8px",
            flexWrap: "wrap",
          }}
        >
          <strong>30 đêm gần nhất</strong>
          <Badge severity="normal">{dbHistoryQuery.data.length} bản ghi</Badge>
        </div>
      }
    >
      <TableRenderer table={table} />
    </Card>
  );
}

function formatDuration(totalMinutes: number) {
  const safe = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(safe / 60);
  const minutes = safe % 60;
  return `${hours} giờ ${minutes} phút`;
}

function formatPhaseSummary(phases: Record<string, number>) {
  const segments = [
    ["Light", phases?.light ?? 0],
    ["Deep", phases?.deep ?? 0],
    ["REM", phases?.rem ?? 0],
    ["Awake", phases?.awake ?? 0],
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
