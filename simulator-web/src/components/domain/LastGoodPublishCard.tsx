import { CheckCircle2, RefreshCw } from "lucide-react";
import { Card } from "../ui/Card";
import type { VerificationResult } from "../../types/verification";

// ---------------------------------------------------------------------------
// LastGoodPublishCard — Module E.6.
//
// Surface the most recent successful publish (`lastGoodPublishAt`) plus the
// since-start ack tally (`publishAckCount`/`publishAttemptCount`).  The
// distinction matters: an operator looking at a FAILED row needs to know
// whether the pipeline is *broken* (no good publish yet) or just *recently
// degraded* (last good 30s ago, last attempt 1s ago).
// ---------------------------------------------------------------------------

interface LastGoodPublishCardProps {
  result: VerificationResult | null;
}

export function LastGoodPublishCard({ result }: LastGoodPublishCardProps) {
  if (!result) {
    return (
      <Card header={<strong>Lần publish thành công gần nhất</strong>}>
        <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "13px" }}>
          Chưa có phiên đang chạy — không có bằng chứng publish nào để hiển thị.
        </p>
      </Card>
    );
  }

  const hasGood = Boolean(result.lastGoodPublishAt);
  const ackRatio =
    result.publishAttemptCount > 0
      ? `${result.publishAckCount}/${result.publishAttemptCount} attempt`
      : "Chưa có lần publish nào";

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {hasGood ? (
            <CheckCircle2 size={14} style={{ color: "var(--severity-normal)" }} />
          ) : (
            <RefreshCw size={14} style={{ color: "var(--severity-warning)" }} />
          )}
          <strong>Lần publish thành công gần nhất</strong>
        </div>
      }
    >
      <dl style={dlStyle}>
        <Row label="Thiết bị" value={result.deviceId} />
        <Row
          label="Last good publish"
          value={hasGood ? formatTs(result.lastGoodPublishAt!) : "—"}
          tone={hasGood ? "ok" : "warn"}
        />
        <Row
          label="Last attempt"
          value={result.lastPublishAttemptAt ? formatTs(result.lastPublishAttemptAt) : "—"}
        />
        <Row label="Tỉ lệ ack" value={ackRatio} />
        <Row label="Latency lần cuối" value={`${result.latencyMs} ms`} />
      </dl>
      {result.failureReason && (
        <p
          style={{
            margin: "10px 0 0 0",
            padding: "8px 10px",
            fontSize: "12px",
            color: "var(--severity-critical)",
            background: "rgba(239,68,68,0.08)",
            border: "1px solid rgba(239,68,68,0.30)",
            borderRadius: "var(--radius-sm)",
            lineHeight: 1.5,
          }}
        >
          <strong>Failure reason:</strong> {result.failureReason}
        </p>
      )}
    </Card>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────

function Row({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn";
}) {
  const valueColor =
    tone === "ok"
      ? "var(--severity-normal)"
      : tone === "warn"
        ? "var(--severity-warning)"
        : "var(--text-primary)";
  return (
    <>
      <dt style={dtStyle}>{label}</dt>
      <dd style={{ ...ddStyle, color: valueColor }}>{value}</dd>
    </>
  );
}

function formatTs(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("vi-VN", { hour12: false });
  } catch {
    return iso;
  }
}

const dlStyle = {
  display: "grid",
  gridTemplateColumns: "auto 1fr",
  gap: "6px 12px",
  margin: 0,
  fontSize: "13px",
} as const;

const dtStyle = {
  color: "var(--text-secondary)",
  fontSize: "12px",
} as const;

const ddStyle = {
  margin: 0,
  fontFamily: "var(--font-mono)",
  fontSize: "12px",
  textAlign: "right" as const,
};
