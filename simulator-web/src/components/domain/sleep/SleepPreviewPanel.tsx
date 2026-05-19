import { Suspense, lazy, useMemo } from "react";
import { type ColumnDef, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { UseQueryResult } from "@tanstack/react-query";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import { Skeleton } from "../../ui/Skeleton";
import { TableRenderer } from "../../ui/TableRenderer";
import type { SleepHistoryRow, SleepSessionResponse } from "../../../types/analytics";

// ---------------------------------------------------------------------------
// SleepPreviewPanel — read-only preview of the simulator-side sleep session.
//
// Sourced entirely from the simulator registry (Sleep-EDF or fallback) via
// `GET /analytics/sleep`.  Three sub-cards:
//   * Realism mode banner (banner string from BE).
//   * 5-tile metric strip (Score / Efficiency / Duration / HR avg / SpO2 min).
//   * Hypnogram chart (lazy import of HypnogramChart).
//   * 7-night preview history table.
//
// Pure presentation: receives the React Query result, no fetching here.
// ---------------------------------------------------------------------------

const LazyHypnogramChart = lazy(() =>
  import("../../charts/HypnogramChart").then((module) => ({ default: module.HypnogramChart }))
);

const FALLBACK_BANNER =
  "Chế độ hiện thực giấc ngủ: mẫu dự phòng (giai đoạn 5A). Hãy tải Sleep-EDF để nâng cấp.";

interface SleepPreviewPanelProps {
  sleepQuery: UseQueryResult<SleepSessionResponse>;
}

export function SleepPreviewPanel({ sleepQuery }: SleepPreviewPanelProps) {
  const previewColumns = useMemo<ColumnDef<SleepHistoryRow>[]>(
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

  const table = useReactTable({
    data: sleepQuery.data?.history ?? [],
    columns: previewColumns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div style={{ display: "grid", gap: "12px" }}>
      <div
        style={{
          border: "1px solid rgba(6,182,212,0.35)",
          borderRadius: "var(--radius-md)",
          padding: "8px 12px",
          color: "#67E8F9",
          background: "rgba(6,182,212,0.08)",
          fontSize: "13px",
        }}
      >
        {sleepQuery.data?.banner ?? FALLBACK_BANNER}
      </div>

      {sleepQuery.isLoading ? (
        <Skeleton style={{ height: "120px" }} />
      ) : (
        <Card>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(120px, 1fr))", gap: "10px" }}>
            <MetricTile title="Điểm" value={`${sleepQuery.data?.score ?? 0}/100`} />
            <MetricTile title="Hiệu suất" value={`${sleepQuery.data?.efficiency ?? 0}%`} />
            <MetricTile title="Thời lượng" value={formatDuration(sleepQuery.data?.durationMinutes ?? 0)} />
            <MetricTile title="Nhịp tim TB" value={`${Math.round(sleepQuery.data?.avgHeartRate ?? 0)} bpm`} />
            <MetricTile title="SpO2 thấp nhất" value={`${Math.round(sleepQuery.data?.minSpo2 ?? 0)}%`} />
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
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "8px",
              flexWrap: "wrap",
            }}
          >
            <strong>Lịch sử preview (7 đêm)</strong>
            <Badge severity="info">Simulator Only</Badge>
          </div>
        }
      >
        <TableRenderer table={table} />
      </Card>
    </div>
  );
}

function MetricTile(props: { title: string; value: string }) {
  return (
    <div
      style={{
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)",
        padding: "10px",
      }}
    >
      <small style={{ color: "var(--text-secondary)" }}>{props.title}</small>
      <div
        style={{
          marginTop: "6px",
          fontFamily: "var(--font-mono)",
          fontSize: "18px",
          fontWeight: 700,
        }}
      >
        {props.value}
      </div>
    </div>
  );
}

function formatDuration(totalMinutes: number) {
  const safe = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(safe / 60);
  const minutes = safe % 60;
  return `${hours} giờ ${minutes} phút`;
}
