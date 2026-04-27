import React, { useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Download, Terminal } from "lucide-react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { LogEntry } from "../../hooks/useLogStream";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

interface LogViewerProps {
  logs: LogEntry[];
  deviceNameMap?: Record<string, string>;
}

function sanitizeCsvCell(val: string): string {
  if (/^[=+\-@\t\r]/.test(val)) return `'${val}`;
  return val;
}

function LogViewerInner({ logs, deviceNameMap = {} }: LogViewerProps) {
  const [device, setDevice] = useState("all");
  const [level, setLevel] = useState("WARN+");
  const parentRef = useRef<HTMLDivElement | null>(null);

  const devices = useMemo(() => ["all", ...Array.from(new Set(logs.map((log) => log.device_id)))], [logs]);
  const filtered = useMemo(() => {
    const levelOrder: Record<string, number> = { DEBUG: 1, INFO: 2, WARN: 3, ERROR: 4 };
    const threshold = level === "WARN+" ? 3 : levelOrder[level] ?? 1;
    return logs
      .filter((log) => (device === "all" ? true : log.device_id === device))
      .filter((log) => (level === "ALL" ? true : (levelOrder[log.level] ?? 1) >= threshold))
      .slice(-500);
  }, [device, level, logs]);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 28,
    overscan: 10,
  });

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(filtered, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "logs-mo-phong.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const exportCsv = () => {
    const header = "timestamp,level,device,message\n";
    const body = filtered
      .map(
        (row) =>
          `${sanitizeCsvCell(row.ts ?? "")},${sanitizeCsvCell(row.level)},${sanitizeCsvCell(row.device_id)},"${sanitizeCsvCell(row.message.replace(/"/g, '""'))}"`
      )
      .join("\n");
    const blob = new Blob([header + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "logs-mo-phong.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Terminal size={16} />
            <strong>Trình xem log</strong>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <select value={device} onChange={(event) => setDevice(event.target.value)} style={selectStyle}>
              {devices.map((item) => (
                <option key={item} value={item}>
                  {item === "all" ? "Tất cả thiết bị" : (deviceNameMap[item] ?? item)}
                </option>
              ))}
            </select>
            <select value={level} onChange={(event) => setLevel(event.target.value)} style={selectStyle}>
              <option value="WARN+">Cảnh báo trở lên</option>
              <option value="ALL">Tất cả mức</option>
              <option value="ERROR">Lỗi</option>
              <option value="WARN">Cảnh báo</option>
              <option value="INFO">Thông tin</option>
            </select>
            <Button size="sm" variant="secondary" leftIcon={<Download size={14} />} onClick={exportJson}>
              JSON
            </Button>
            <Button size="sm" variant="secondary" leftIcon={<Download size={14} />} onClick={exportCsv}>
              CSV
            </Button>
          </div>
        </div>
      }
    >
      <div
        ref={parentRef}
        style={{
          height: "280px",
          overflow: "auto",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-md)",
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
        }}
      >
        <div style={{ height: `${virtualizer.getTotalSize()}px`, width: "100%", position: "relative" }}>
          {virtualizer.getVirtualItems().map((item) => {
            const row = filtered[item.index];
            return (
              <div
                key={item.key}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: `${item.size}px`,
                  transform: `translateY(${item.start}px)`,
                  display: "grid",
                  gridTemplateColumns: "110px 70px 160px 1fr",
                  gap: "8px",
                  alignItems: "center",
                  padding: "0 10px",
                  borderBottom: "1px solid var(--border-default)",
                  color: row.level === "ERROR" ? "var(--severity-critical)" : row.level === "WARN" ? "var(--severity-warning)" : "var(--text-secondary)",
                }}
              >
                <span>{new Date(row.ts ?? Date.now()).toLocaleTimeString()}</span>
                <span>[{row.level}]</span>
                <span title={row.device_id}>{deviceNameMap[row.device_id] ?? row.device_id}</span>
                <span>{row.message}</span>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}

export const LogViewer = React.memo(LogViewerInner);

const selectStyle: CSSProperties = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "6px 8px",
};
