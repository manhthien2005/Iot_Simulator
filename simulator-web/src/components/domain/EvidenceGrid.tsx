import React, { useMemo } from "react";
import type { CSSProperties } from "react";
import { ListChecks } from "lucide-react";
import type { LogEntry } from "../../hooks/useLogStream";
import type { VerificationResult } from "../../types/verification";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { DeviceEvidenceCard } from "./DeviceEvidenceCard";

// ---------------------------------------------------------------------------
// EvidenceGrid — wraps the device-evidence cards in a single Card with the
// shared header (count pill + refresh).  Owns the per-device log grouping so
// each child card receives only its own log slice.
// ---------------------------------------------------------------------------

const PER_DEVICE_LOG_LIMIT = 50;

interface EvidenceGridProps {
  rows: VerificationResult[];
  logs: LogEntry[];
  deviceNameMap: Record<string, string>;
  onRefresh: () => void;
  onFocusLogs: (deviceId: string) => void;
}

function EvidenceGridInner({
  rows,
  logs,
  deviceNameMap,
  onRefresh,
  onFocusLogs,
}: EvidenceGridProps) {
  const logsByDevice = useMemo(() => {
    const map: Record<string, LogEntry[]> = {};
    for (const log of logs) {
      const arr = map[log.device_id] ?? (map[log.device_id] = []);
      arr.push(log);
    }
    for (const id of Object.keys(map)) {
      const arr = map[id];
      if (arr.length > PER_DEVICE_LOG_LIMIT) {
        map[id] = arr.slice(arr.length - PER_DEVICE_LOG_LIMIT);
      }
    }
    return map;
  }, [logs]);

  if (rows.length === 0) {
    return (
      <Card
        header={
          <div style={headerStyle}>
            <strong>Bằng chứng theo thiết bị</strong>
            <Button variant="secondary" size="sm" onClick={onRefresh}>
              Kiểm tra lại
            </Button>
          </div>
        }
      >
        <EmptyState
          icon={ListChecks}
          title="Chưa có phiên để xác minh"
          description="Mở Mô phỏng tín hiệu sinh tồn và bắt đầu một phiên để bắt đầu thu thập bằng chứng."
        />
      </Card>
    );
  }

  return (
    <Card
      header={
        <div style={headerStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <strong>Bằng chứng theo thiết bị</strong>
            <span style={countPillStyle}>{rows.length} thiết bị</span>
          </div>
          <Button variant="secondary" size="sm" onClick={onRefresh}>
            Kiểm tra lại
          </Button>
        </div>
      }
    >
      <ul style={gridStyle}>
        {rows.map((row) => (
          <DeviceEvidenceCard
            key={`${row.sessionId ?? ""}:${row.deviceId}`}
            result={row}
            logs={logsByDevice[row.deviceId] ?? []}
            deviceName={deviceNameMap[row.deviceId] ?? row.deviceId}
            onFocusLogs={onFocusLogs}
          />
        ))}
      </ul>
    </Card>
  );
}

export const EvidenceGrid = React.memo(EvidenceGridInner);

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
};

const countPillStyle: CSSProperties = {
  fontSize: "11px",
  padding: "1px 7px",
  borderRadius: "var(--radius-full)",
  background: "var(--bg-base)",
  border: "1px solid var(--border-default)",
  color: "var(--text-secondary)",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
  gap: "12px",
  margin: 0,
  padding: 0,
  listStyle: "none",
};
