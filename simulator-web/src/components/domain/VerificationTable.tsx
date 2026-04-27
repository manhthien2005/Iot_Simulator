import React from "react";
import type { VerificationResult, VerificationStatus } from "../../types/verification";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { PipelineStageStrip } from "./PipelineStageStrip";
import { ListChecks } from "lucide-react";

// ---------------------------------------------------------------------------
// VerificationTable — Module E.5 (redesigned).
//
// Each row is a per-device evidence card:
//   • Top line  — device ID (mono) + status badge + timestamp
//   • Sub line  — session ID (truncated 8 chars) + latency/ack stats
//   • Pipeline  — 3-column grid (no horizontal overflow)
//   • Footer    — failure reason banner when present
// ---------------------------------------------------------------------------

interface VerificationTableProps {
  rows: VerificationResult[];
  onRefresh: () => void;
  deviceNameMap?: Record<string, string>;
}

function statusSeverity(status: VerificationStatus) {
  if (status === "PASS") return "normal" as const;
  if (status === "DELAYED") return "warning" as const;
  if (status === "FAILED") return "critical" as const;
  return "offline" as const;
}

function statusLabel(status: VerificationStatus) {
  if (status === "PASS") return "Đạt";
  if (status === "DELAYED") return "Chậm cập nhật";
  if (status === "FAILED") return "Lỗi publish";
  return "Chờ";
}

function VerificationTableInner({ rows, onRefresh, deviceNameMap = {} }: VerificationTableProps) {
  if (rows.length === 0) {
    return (
      <Card
        header={
          <div style={headerStyle}>
            <strong>Bảng xác minh</strong>
            <Button variant="secondary" size="sm" onClick={onRefresh}>
              Kiểm tra lại
            </Button>
          </div>
        }
      >
        <EmptyState
          icon={ListChecks}
          title="Chưa có phiên để xác minh"
          description="Mở Phiên mô phỏng và bắt đầu một phiên để bắt đầu thu thập bằng chứng."
        />
      </Card>
    );
  }

  return (
    <Card
      header={
        <div style={headerStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <strong>Bảng xác minh</strong>
            <span style={countPillStyle}>{rows.length} thiết bị</span>
          </div>
          <Button variant="secondary" size="sm" onClick={onRefresh}>
            Kiểm tra lại
          </Button>
        </div>
      }
    >
      <ul style={listStyle}>
        {rows.map((row) => (
          <li key={`${row.sessionId ?? ""}:${row.deviceId}`} style={rowStyle}>
            {/* ── Row header ── */}
            <div style={rowTopStyle}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", minWidth: 0 }}>
                <strong style={deviceIdStyle}>
                  {deviceNameMap[row.deviceId] ?? row.deviceId}
                </strong>
                <span style={deviceSubIdStyle}>{row.deviceId}</span>
                <Badge severity={statusSeverity(row.status)}>{statusLabel(row.status)}</Badge>
              </div>
              <span style={timestampStyle}>
                {new Date(row.lastCheckedAt).toLocaleTimeString("vi-VN", { hour12: false })}
              </span>
            </div>

            {/* ── Stats sub-line ── */}
            <div style={subLineStyle}>
              <span style={metaStyle}>
                Latency&nbsp;<code style={codeStyle}>{row.latencyMs}&nbsp;ms</code>
              </span>
              <span style={metaStyle}>
                Ack&nbsp;<code style={codeStyle}>{row.publishAckCount}/{row.publishAttemptCount}</code>
              </span>
            </div>

            {/* ── Pipeline grid ── */}
            <PipelineStageStrip stages={row.stages} orientation="grid" />

            {/* ── Failure reason ── */}
            {row.failureReason && (
              <p style={failureReasonStyle}>
                <strong>Nguyên nhân lỗi:</strong> {row.failureReason}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

const headerStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
} as const;

const countPillStyle = {
  fontSize: "11px",
  padding: "1px 7px",
  borderRadius: "999px",
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
  color: "var(--text-secondary)",
} as const;

const listStyle = {
  display: "flex",
  flexDirection: "column" as const,
  gap: "10px",
  margin: 0,
  padding: 0,
  listStyle: "none" as const,
};

const rowStyle = {
  display: "flex",
  flexDirection: "column" as const,
  gap: "8px",
  padding: "12px 14px",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  background: "var(--bg-elevated)",
};

const rowTopStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
} as const;

const deviceIdStyle = {
  fontSize: "14px",
  fontWeight: 600,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap" as const,
  maxWidth: "220px",
} as const;

const deviceSubIdStyle = {
  fontSize: "11px",
  fontFamily: "var(--font-mono)",
  color: "var(--text-muted)",
  flexShrink: 0,
} as const;

const subLineStyle = {
  display: "flex",
  alignItems: "center",
  gap: "12px",
  flexWrap: "wrap" as const,
} as const;

const metaStyle = {
  fontSize: "12px",
  color: "var(--text-secondary)",
} as const;

const codeStyle = {
  fontFamily: "var(--font-mono)",
  fontSize: "11px",
  color: "var(--text-primary)",
} as const;

const timestampStyle = {
  fontSize: "11px",
  color: "var(--text-muted)",
  whiteSpace: "nowrap" as const,
  flexShrink: 0,
} as const;

const failureReasonStyle = {
  margin: 0,
  padding: "8px 10px",
  fontSize: "12px",
  color: "var(--severity-critical)",
  background: "rgba(239,68,68,0.08)",
  border: "1px solid rgba(239,68,68,0.30)",
  borderRadius: "var(--radius-sm)",
  lineHeight: 1.5,
} as const;

export const VerificationTable = React.memo(VerificationTableInner);
