import type { CSSProperties, ReactNode } from "react";
import {
  Activity,
  BrainCircuit,
  Database,
  RefreshCw,
  Server,
  ShieldCheck,
} from "lucide-react";
import { Button } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import type {
  HealthBackendBlock,
  HealthDatabaseBlock,
  HealthModelApiBlock,
  HealthPayloadV2,
  HealthPreTriggerBlock,
  HealthRuntimeBlock,
} from "../../../types/health";

// ---------------------------------------------------------------------------
// SystemStatusCards — block-style 5-tile system status header.
//
// Layout per card:
//   1. Header row     : icon + title (large, primary) + ping (only when healthy).
//   2. State row      : human state copy in Vietnamese, colored by severity.
//   3. Key-value rows : 0–2 detail rows (e.g. "Phản hồi  8ms").  Label muted,
//      value primary.  Replaces the previous redundant `● value` body and
//      removes the duplicated dot next to numeric latency values.
// ---------------------------------------------------------------------------

type CardSeverity = "normal" | "warning" | "critical" | "offline" | "info";

interface KeyValueRow {
  label: string;
  value: string;
}

interface ServiceCard {
  key: string;
  icon: ReactNode;
  label: string;
  /** Main state phrase ("Đã kết nối", "30 phút", "Tắt"). Color follows severity. */
  state: string;
  /** Optional supporting details rendered as label/value rows. */
  rows: KeyValueRow[];
  severity: CardSeverity;
}

interface SystemStatusCardsProps {
  data: HealthPayloadV2 | undefined;
  isLoading: boolean;
  error: unknown;
  isFetching: boolean;
  onRetry: () => void;
}

export function SystemStatusCards({
  data,
  isLoading,
  error,
  isFetching,
  onRetry,
}: SystemStatusCardsProps) {
  if (isLoading && !data) {
    return (
      <div className="dashboard-status-grid">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} style={{ height: "144px", borderRadius: "var(--radius-lg)" }} />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={errorContainerStyle} role="alert">
        <div>
          <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>
            Chưa kết nối được Simulator API
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: "13px", marginTop: "4px" }}>
            Trạng thái hệ thống không khả dụng. Auto-retry sau 15s.
          </div>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          loading={isFetching}
          leftIcon={<RefreshCw size={14} />}
        >
          Thử lại
        </Button>
      </div>
    );
  }

  const cards = deriveCards(data);

  return (
    <div className="dashboard-status-grid" role="status" aria-label="Trạng thái hệ thống">
      {cards.map((card) => (
        <ServiceCardView key={card.key} card={card} />
      ))}
    </div>
  );
}

// ── Subviews ────────────────────────────────────────────────────────────

function ServiceCardView({ card }: { card: ServiceCard }) {
  const palette = severityPalette[card.severity];
  return (
    <article style={cardStyle}>
      {/* Header — title icon + label + ping (only when healthy). */}
      <header style={cardHeaderStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
          <span style={{ display: "inline-flex", color: palette.fg, flexShrink: 0 }}>
            {card.icon}
          </span>
          <span style={titleStyle}>{card.label}</span>
        </div>
        {card.severity === "normal" ? <PingDot color={palette.fg} /> : null}
      </header>

      {/* State row — color follows severity, no leading dot. */}
      <div style={{ ...stateStyle, color: palette.fg }}>{card.state}</div>

      {/* Optional key-value details, separated from the state by a subtle
       *  divider so the visual hierarchy reads: title → state → details. */}
      {card.rows.length > 0 ? (
        <div style={rowsContainerStyle}>
          {card.rows.map((row) => (
            <div key={row.label} style={kvRowStyle}>
              <span style={kvLabelStyle}>{row.label}</span>
              <span style={kvValueStyle}>{row.value}</span>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function PingDot({ color }: { color: string }) {
  return (
    <span
      className="live-dot"
      style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
        animation: "live-pulse 2s infinite",
      }}
      aria-hidden="true"
    />
  );
}

// ── Card derivation ─────────────────────────────────────────────────────

function deriveCards(data: HealthPayloadV2): ServiceCard[] {
  return [
    runtimeCard(data.runtime),
    databaseCard(data.database),
    backendCard(data.backend),
    modelApiCard(data.modelApi),
    preTriggerCard(data.preTrigger),
  ];
}

function runtimeCard(runtime: HealthRuntimeBlock): ServiceCard {
  const base = {
    key: "runtime",
    icon: <Activity size={18} />,
    label: "Runtime",
  };
  switch (runtime.state) {
    case "running":
      return {
        ...base,
        state: formatUptimeVi(runtime.uptimeSeconds),
        rows: [{ label: "Tình trạng", value: "Đang chạy" }],
        severity: "normal",
      };
    case "idle":
      return {
        ...base,
        state: "Nghỉ",
        rows: [{ label: "Tình trạng", value: "Không có phiên" }],
        severity: "info",
      };
    case "degraded":
      return {
        ...base,
        state: "Suy giảm",
        rows: [{ label: "Tình trạng", value: "Dịch vụ phụ thuộc fail" }],
        severity: "warning",
      };
    case "stopped":
    default:
      return {
        ...base,
        state: "Dừng",
        rows: [{ label: "Tình trạng", value: "Không phát dữ liệu" }],
        severity: "critical",
      };
  }
}

function databaseCard(db: HealthDatabaseBlock): ServiceCard {
  const base = {
    key: "db",
    icon: <Database size={18} />,
    label: "Database",
  };
  if (db.state === "connected") {
    const latency = db.lastCheckMs == null ? "—" : `${db.lastCheckMs} ms`;
    return {
      ...base,
      state: "Đã kết nối",
      rows: [
        { label: "Phản hồi", value: latency },
        { label: "Tình trạng", value: "Ổn định" },
      ],
      severity: "normal",
    };
  }
  return {
    ...base,
    state: "Mất kết nối",
    rows: [{ label: "Tình trạng", value: "Heartbeat fail" }],
    severity: "critical",
  };
}

function backendCard(backend: HealthBackendBlock): ServiceCard {
  const base = {
    key: "backend",
    icon: <Server size={18} />,
    label: "Backend Mobile",
  };
  const latency = backend.lastLatencyMs == null ? "—" : `${backend.lastLatencyMs} ms`;
  switch (backend.state) {
    case "connected":
      return {
        ...base,
        state: "Đã kết nối",
        rows: [
          { label: "Phản hồi", value: latency },
          { label: "Tình trạng", value: "Ổn định" },
        ],
        severity: "normal",
      };
    case "slow":
      return {
        ...base,
        state: "Phản hồi chậm",
        rows: [
          { label: "Phản hồi", value: latency },
          { label: "Tình trạng", value: "Vượt ngưỡng" },
        ],
        severity: "warning",
      };
    case "down":
      return {
        ...base,
        state: "Không kết nối",
        rows: [{ label: "Tình trạng", value: "Telemetry không đẩy" }],
        severity: "critical",
      };
    case "unknown":
    default:
      return {
        ...base,
        state: "Chưa probe",
        rows: [{ label: "Tình trạng", value: "Đang chờ kiểm tra" }],
        severity: "offline",
      };
  }
}

function modelApiCard(model: HealthModelApiBlock): ServiceCard {
  const base = {
    key: "model",
    icon: <BrainCircuit size={18} />,
    label: "Model AI",
  };
  const sourceCopy = model.lastScoreSource === "ai" ? "AI" : "Heuristic";
  switch (model.state) {
    case "ready":
      return {
        ...base,
        state: "Đã kết nối",
        rows: [
          { label: "Tình trạng", value: "Sẵn sàng" },
          { label: "Nguồn chấm", value: sourceCopy },
        ],
        severity: "normal",
      };
    case "unavailable":
      return {
        ...base,
        state: "Không khả dụng",
        rows: [{ label: "Tình trạng", value: "Đang dùng heuristic" }],
        severity: "warning",
      };
    case "unknown":
    default:
      return {
        ...base,
        state: "Chưa probe",
        rows: [{ label: "Tình trạng", value: "Đang chờ kiểm tra" }],
        severity: "offline",
      };
  }
}

function preTriggerCard(pre: HealthPreTriggerBlock): ServiceCard {
  const base = {
    key: "pre",
    icon: <ShieldCheck size={18} />,
    label: "Pre-Trigger",
  };
  const thresholdShort =
    pre.thresholdSource === "db"
      ? "DB"
      : pre.thresholdSource === "fallback"
        ? "Fallback"
        : "—";
  switch (pre.mode) {
    case "active":
      return {
        ...base,
        state: "Active",
        rows: [{ label: "Ngưỡng", value: thresholdShort }],
        severity: "normal",
      };
    case "shadow":
      return {
        ...base,
        state: "Shadow",
        rows: [{ label: "Ngưỡng", value: thresholdShort }],
        severity: "info",
      };
    case "off":
    default:
      return {
        ...base,
        state: "Tắt",
        rows: [],
        severity: "offline",
      };
  }
}

function formatUptimeVi(seconds: number): string {
  if (seconds < 60) return `${seconds} giây`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} phút`;
  const hours = Math.floor(minutes / 60);
  const remMins = minutes % 60;
  if (hours < 24) {
    return remMins > 0 ? `${hours} giờ ${remMins} phút` : `${hours} giờ`;
  }
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return remHours > 0 ? `${days} ngày ${remHours} giờ` : `${days} ngày`;
}

// ── Styles ──────────────────────────────────────────────────────────────

const severityPalette: Record<CardSeverity, { fg: string; bg: string; border: string }> = {
  normal: {
    fg: "var(--severity-normal)",
    bg: "var(--severity-normal-bg)",
    border: "var(--severity-normal-border)",
  },
  warning: {
    fg: "var(--severity-warning)",
    bg: "var(--severity-warning-bg)",
    border: "var(--severity-warning-border)",
  },
  critical: {
    fg: "var(--severity-critical)",
    bg: "var(--severity-critical-bg)",
    border: "var(--severity-critical-border)",
  },
  offline: {
    fg: "var(--severity-offline)",
    bg: "var(--severity-offline-bg)",
    border: "var(--severity-offline-border)",
  },
  info: {
    fg: "var(--severity-info)",
    bg: "var(--severity-info-bg)",
    border: "var(--severity-info-border)",
  },
};

const cardStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "16px 18px",
  borderRadius: "var(--radius-lg)",
  background: "var(--bg-elevated)",
  border: "1px solid rgba(255, 255, 255, 0.06)",
  boxShadow: "var(--shadow-card)",
  minHeight: "160px",
};

const cardHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "8px",
};

const titleStyle: CSSProperties = {
  fontSize: "11px",
  fontWeight: 600,
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.09em",
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const stateStyle: CSSProperties = {
  marginTop: "14px",
  fontSize: "24px",
  fontWeight: 700,
  letterSpacing: "-0.02em",
  lineHeight: 1.15,
};

const rowsContainerStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
  marginTop: "14px",
  paddingTop: "12px",
  borderTop: "1px solid rgba(255, 255, 255, 0.06)",
};

const kvRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  gap: "12px",
  lineHeight: 1.4,
};

const kvLabelStyle: CSSProperties = {
  color: "var(--text-muted)",
  fontSize: "11px",
  fontWeight: 500,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const kvValueStyle: CSSProperties = {
  color: "var(--text-primary)",
  fontSize: "13px",
  fontWeight: 600,
  fontVariantNumeric: "tabular-nums",
  textAlign: "right",
};

const errorContainerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  padding: "14px 16px",
  borderRadius: "var(--radius-lg)",
  background: "var(--bg-elevated)",
  border: "1px solid var(--severity-critical-border)",
};
