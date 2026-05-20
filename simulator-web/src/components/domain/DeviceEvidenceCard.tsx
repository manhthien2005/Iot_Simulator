import React, { useMemo } from "react";
import type { CSSProperties } from "react";
import { AlertTriangle, Check, Clock, MinusCircle } from "lucide-react";
import type { LogEntry } from "../../hooks/useLogStream";
import type {
  PipelineStage,
  PipelineStageStatus,
  VerificationResult,
} from "../../types/verification";
import { useRelativeTime } from "../../hooks/useRelativeTime";

// ---------------------------------------------------------------------------
// DeviceEvidenceCard — single-device evidence panel for the Trung tâm Bằng
// chứng page.  Encapsulates the four blocks defined in the mockup:
//   1. Header (device name + liveness pill).
//   2. Pipeline grid collapsed to 3 stages: Telemetry / Risk / Alert.
//   3. Evidence log strip (3 most recent log lines for this device).
//   4. Footer (ack ratio + last good ts + focus button).
// ---------------------------------------------------------------------------

const LIVENESS_OK_MS = 10_000;
const LIVENESS_WARN_MS = 60_000;

const PIPELINE_STAGE_KEYS = [
  "telemetry_published",
  "risk_evaluated",
  "alert_dispatched",
] as const;

const PIPELINE_STAGE_LABELS: Record<(typeof PIPELINE_STAGE_KEYS)[number], string> = {
  telemetry_published: "Telemetry",
  risk_evaluated: "Risk score",
  alert_dispatched: "Alert dispatch",
};

type Liveness = "ok" | "warn" | "fail";

interface DeviceEvidenceCardProps {
  result: VerificationResult;
  logs: LogEntry[];
  deviceName: string;
  onFocusLogs: (deviceId: string) => void;
}

function getLiveness(
  status: VerificationResult["status"],
  ageMs: number | null,
): Liveness {
  if (status === "FAILED") return "fail";
  if (ageMs == null) return "fail";
  if (ageMs < LIVENESS_OK_MS) return "ok";
  if (ageMs < LIVENESS_WARN_MS) return "warn";
  return "fail";
}

function livenessLabel(liveness: Liveness, status: VerificationResult["status"]): string {
  if (liveness === "ok") return "Đang hoạt động";
  if (liveness === "warn") return "Chậm cập nhật";
  if (status === "FAILED") return "Lỗi pipeline";
  return "Mất kết nối";
}

function formatTime(ts: string | undefined | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("vi-VN", { hour12: false });
}

function DeviceEvidenceCardInner({
  result,
  logs,
  deviceName,
  onFocusLogs,
}: DeviceEvidenceCardProps) {
  const livenessSource = result.lastGoodPublishAt ?? result.lastCheckedAt;
  const { label: ageLabel, ageMs } = useRelativeTime(livenessSource);
  const liveness = getLiveness(result.status, ageMs);

  const stages = useMemo(() => buildPipeline(result.stages), [result.stages]);
  const recentLogs = useMemo(() => logs.slice(-3).reverse(), [logs]);

  const ackRatio =
    result.publishAttemptCount > 0
      ? `${result.publishAckCount}/${result.publishAttemptCount}`
      : "0/0";

  return (
    <li
      style={{
        ...rootStyle,
        borderColor:
          liveness === "fail"
            ? "var(--severity-critical-border)"
            : liveness === "warn"
              ? "var(--severity-warning-border)"
              : "var(--border-default)",
      }}
      title={result.deviceId}
    >
      <header style={headerStyle}>
        <div style={{ minWidth: 0, display: "grid", gap: "2px" }}>
          <h3 style={nameStyle}>{deviceName}</h3>
          <p style={metaStyle}>
            Tín hiệu cuối <code style={codeStyle}>{ageLabel}</code> trước
          </p>
        </div>
        <LivenessPill liveness={liveness} status={result.status} ageLabel={ageLabel} />
      </header>

      <ol style={pipelineStyle} aria-label="Tiến trình pipeline">
        {stages.map((stage) => (
          <PipelineStageNode key={stage.key} stage={stage} />
        ))}
      </ol>

      <ul style={logStripStyle} aria-label="3 dòng log gần nhất">
        {recentLogs.length === 0 ? (
          <li style={{ ...logRowStyle, color: "var(--text-muted)" }}>
            <span style={{ gridColumn: "1 / -1", textAlign: "center" }}>
              Chưa có log nào cho thiết bị này.
            </span>
          </li>
        ) : (
          recentLogs.map((log, idx) => (
            <li key={`${log.ts}-${idx}`} style={logRowStyle}>
              <span style={tsCellStyle}>{formatTime(log.ts ?? undefined)}</span>
              <span style={{ ...lvlCellStyle, color: levelColor(log.level) }}>[{log.level}]</span>
              <span style={msgCellStyle} title={log.message}>{log.message}</span>
            </li>
          ))
        )}
      </ul>

      {result.failureReason && (
        <p style={failureBannerStyle}>
          <strong>Nguyên nhân lỗi:</strong> {result.failureReason}
        </p>
      )}

      <footer style={footerStyle}>
        <span style={statStyle}>
          Ack&nbsp;<code style={codeStyle}>{ackRatio}</code>
          &nbsp;·&nbsp;last good&nbsp;
          <code style={codeStyle}>{formatTime(result.lastGoodPublishAt)}</code>
        </span>
        <button
          type="button"
          onClick={() => onFocusLogs(result.deviceId)}
          style={focusLinkStyle}
        >
          Xem log đầy đủ →
        </button>
      </footer>
    </li>
  );
}

export const DeviceEvidenceCard = React.memo(DeviceEvidenceCardInner);

// ── Helpers ──────────────────────────────────────────────────────────────

function buildPipeline(stages: PipelineStage[]): PipelineStage[] {
  const map = new Map<string, PipelineStage>();
  for (const s of stages) map.set(s.key, s);
  return PIPELINE_STAGE_KEYS.map((key) => {
    const found = map.get(key);
    if (found) {
      return { ...found, label: PIPELINE_STAGE_LABELS[key] };
    }
    return {
      key,
      label: PIPELINE_STAGE_LABELS[key],
      status: "pending",
      detail: null,
      at: null,
    } satisfies PipelineStage;
  });
}

function levelColor(level: string): string {
  if (level === "ERROR") return "var(--severity-critical)";
  if (level === "WARN") return "var(--severity-warning)";
  if (level === "INFO") return "var(--severity-info)";
  return "var(--text-muted)";
}

function LivenessPill({
  liveness,
  status,
  ageLabel,
}: {
  liveness: Liveness;
  status: VerificationResult["status"];
  ageLabel: string;
}) {
  const tone = LIVENESS_TONES[liveness];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "4px 10px",
        borderRadius: "var(--radius-full)",
        fontSize: "12px",
        fontWeight: 500,
        background: tone.bg,
        color: tone.fg,
        border: `1px solid ${tone.border}`,
        whiteSpace: "nowrap",
      }}
    >
      <span
        className={liveness === "ok" ? "live-dot" : undefined}
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: tone.fg,
          flexShrink: 0,
        }}
        aria-hidden
      />
      {livenessLabel(liveness, status)}
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-secondary)" }}>
        {ageLabel}
      </span>
    </span>
  );
}

function PipelineStageNode({ stage }: { stage: PipelineStage }) {
  const tone = STAGE_TONES[stage.status];
  return (
    <li
      title={stage.detail ?? undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "6px 9px",
        borderRadius: "var(--radius-md)",
        background: tone.bg,
        border: `1px solid ${tone.border}`,
        minWidth: 0,
      }}
    >
      <StageIcon status={stage.status} fg={tone.fg} />
      <span
        style={{
          fontSize: "11px",
          fontWeight: 600,
          color: tone.fg,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {stage.label}
      </span>
    </li>
  );
}

function StageIcon({ status, fg }: { status: PipelineStageStatus; fg: string }) {
  const props = { size: 13, color: fg, "aria-hidden": true } as const;
  switch (status) {
    case "ok":
      return <Check {...props} />;
    case "failed":
      return <AlertTriangle {...props} />;
    case "skipped":
      return <MinusCircle {...props} />;
    case "pending":
    default:
      return <Clock {...props} />;
  }
}

// ── Styles ───────────────────────────────────────────────────────────────

const rootStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
  padding: "14px",
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-lg)",
  listStyle: "none",
  transition: "border-color 150ms ease",
};

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: "10px",
};

const nameStyle: CSSProperties = {
  margin: 0,
  fontSize: "15px",
  fontWeight: 600,
  lineHeight: 1.2,
  color: "var(--text-primary)",
};

const metaStyle: CSSProperties = {
  margin: 0,
  fontSize: "11px",
  color: "var(--text-muted)",
};

const codeStyle: CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "11px",
  color: "var(--text-primary)",
};

const pipelineStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(3, 1fr)",
  gap: "6px",
  margin: 0,
  padding: 0,
  listStyle: "none",
};

const logStripStyle: CSSProperties = {
  margin: 0,
  padding: 0,
  listStyle: "none",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  background: "var(--bg-base)",
  overflow: "hidden",
};

const logRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "64px 52px 1fr",
  gap: "8px",
  padding: "5px 10px",
  fontFamily: "var(--font-mono)",
  fontSize: "11px",
  color: "var(--text-secondary)",
  borderBottom: "1px solid var(--border-default)",
  lineHeight: 1.4,
};

const tsCellStyle: CSSProperties = { color: "var(--text-muted)" };
const lvlCellStyle: CSSProperties = { fontWeight: 600 };
const msgCellStyle: CSSProperties = {
  color: "var(--text-primary)",
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const failureBannerStyle: CSSProperties = {
  margin: 0,
  padding: "8px 10px",
  fontSize: "12px",
  color: "var(--severity-critical)",
  background: "var(--severity-critical-bg)",
  border: "1px solid var(--severity-critical-border)",
  borderRadius: "var(--radius-sm)",
  lineHeight: 1.5,
};

const footerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
  fontSize: "11px",
};

const statStyle: CSSProperties = { color: "var(--text-secondary)" };

const focusLinkStyle: CSSProperties = {
  background: "none",
  border: "none",
  color: "var(--severity-info)",
  fontSize: "12px",
  cursor: "pointer",
  padding: 0,
};

interface Tone {
  fg: string;
  bg: string;
  border: string;
}

const STAGE_TONES: Record<PipelineStageStatus, Tone> = {
  ok: {
    fg: "var(--severity-normal)",
    bg: "var(--severity-normal-bg)",
    border: "var(--severity-normal-border)",
  },
  pending: {
    fg: "var(--text-secondary)",
    bg: "var(--bg-base)",
    border: "var(--border-default)",
  },
  failed: {
    fg: "var(--severity-critical)",
    bg: "var(--severity-critical-bg)",
    border: "var(--severity-critical-border)",
  },
  skipped: {
    fg: "var(--text-muted)",
    bg: "transparent",
    border: "var(--border-default)",
  },
};

const LIVENESS_TONES: Record<Liveness, Tone> = {
  ok: {
    fg: "var(--severity-normal)",
    bg: "var(--severity-normal-bg)",
    border: "var(--severity-normal-border)",
  },
  warn: {
    fg: "var(--severity-warning)",
    bg: "var(--severity-warning-bg)",
    border: "var(--severity-warning-border)",
  },
  fail: {
    fg: "var(--severity-critical)",
    bg: "var(--severity-critical-bg)",
    border: "var(--severity-critical-border)",
  },
};
