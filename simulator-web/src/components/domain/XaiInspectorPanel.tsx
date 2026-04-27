import { useMemo } from "react";
import { type ColumnDef, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { Card } from "../ui/Card";
import { TableRenderer } from "../ui/TableRenderer";
import type { RiskContribution } from "../../types/analytics";

// ---------------------------------------------------------------------------
// XaiInspectorPanel — pure presentational view of the per-feature risk
// explanation (XAI table).  Extracted from `RiskAnalyticsTab` (Module D.3)
// so the same widget can render inside `/analytics` (read-only) and
// `/diagnostics` (next to the inject + trigger tools).
//
// No mutations, no async — the panel only renders whatever
// `contributions` it is handed.  The parent owns fetching + caching.
// ---------------------------------------------------------------------------

interface XaiInspectorPanelProps {
  contributions: RiskContribution[];
  /** Optional title override (e.g. "XAI gần nhất" vs "Giải thích rủi ro"). */
  title?: string;
}

export function XaiInspectorPanel({
  contributions,
  title = "Giải thích rủi ro (XAI)",
}: XaiInspectorPanelProps) {
  const columns = useMemo<ColumnDef<RiskContribution>[]>(
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
    [],
  );

  const table = useReactTable({
    data: contributions,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <Card header={<strong>{title}</strong>}>
      {contributions.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0 }}>
          Chưa có dữ liệu giải thích — hãy chạy tính toán rủi ro hoặc đợi snapshot kế tiếp.
        </p>
      ) : (
        <TableRenderer table={table} />
      )}
    </Card>
  );
}
