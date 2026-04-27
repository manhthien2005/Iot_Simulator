import type { CSSProperties, ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { Card } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Skeleton } from "../ui/Skeleton";
import type {
  HealthBackendBlock,
  HealthDatabaseBlock,
  HealthModelApiBlock,
  HealthPayloadV2,
  HealthPreTriggerBlock,
  HealthRuntimeBlock,
} from "../../types/health";

// ---------------------------------------------------------------------------
// SystemHealthHero — 5 status pills mapped 1:1 to §2 of the truth model.
// All copy + severity is derived from `HealthPayloadV2`; no local invented
// state.  Tooltips stay ≤2 lines per the Module A acceptance criterion.
// ---------------------------------------------------------------------------

type PillSeverity = "normal" | "warning" | "critical" | "offline" | "info";

interface Pill {
  label: string;
  state: string;
  display: string;
  severity: PillSeverity;
  detail: string;
}

interface SystemHealthHeroProps {
  data: HealthPayloadV2 | undefined;
  isLoading: boolean;
  error: unknown;
  /**
   * Optional manual refetch handler.  Wired by the dashboard page so the
   * waiting-state hero can give the operator a "Thử lại" button without
   * having to wait the full 15 s polling tick.
   */
  onRetry?: () => void;
  /** True when a manual or automatic refetch is currently in-flight. */
  isFetching?: boolean;
}

export function SystemHealthHero({ data, isLoading, error, onRetry, isFetching }: SystemHealthHeroProps) {
  if (isLoading && !data) {
    return (
      <Card>
        <HeroHeader subtitle="Đang đọc trạng thái hệ thống…" />
        <div style={pillRowStyle}>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} style={{ height: "60px", flex: "1 1 160px" }} />
          ))}
        </div>
      </Card>
    );
  }

  if (error || !data) {
    // Module H — friendlier "waiting" hero when /api/sim/health hasn't
    // responded yet.  Auto-poll keeps trying every 15 s; the explicit
    // "Thử lại" button gives the operator agency without waiting.
    return (
      <Card>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "12px",
            flexWrap: "wrap",
            marginBottom: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "baseline", gap: "12px", flexWrap: "wrap" }}>
            <strong style={{ fontSize: "14px", letterSpacing: "0.04em" }}>SỨC KHỎE HỆ THỐNG</strong>
            <span style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
              Đang chờ dữ liệu sức khỏe — Simulator API tạm thời chưa phản hồi. Hệ thống sẽ tự thử lại sau 15 giây.
            </span>
          </div>
          {onRetry && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onRetry}
              loading={Boolean(isFetching)}
              leftIcon={<RefreshCw size={14} />}
            >
              Thử lại
            </Button>
          )}
        </div>
        <div style={pillRowStyle}>
          <PillView
            pill={{
              label: "Runtime",
              state: "starting",
              display: "đang khởi động",
              severity: "offline",
              detail: "Simulator API chưa trả lời. Thường xảy ra khi BE đang khởi động hoặc mất kết nối ngắn.",
            }}
          />
        </div>
      </Card>
    );
  }

  const pills = derivePills(data);

  return (
    <Card>
      <HeroHeader subtitle={summarise(data)} />
      <div style={pillRowStyle}>
        {pills.map((pill) => (
          <PillView key={pill.label} pill={pill} />
        ))}
      </div>
    </Card>
  );
}

// ── Subviews ────────────────────────────────────────────────────────────

function HeroHeader({ subtitle }: { subtitle: ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: "12px", marginBottom: "12px", flexWrap: "wrap" }}>
      <strong style={{ fontSize: "14px", letterSpacing: "0.04em" }}>SỨC KHỎE HỆ THỐNG</strong>
      <span style={{ color: "var(--text-secondary)", fontSize: "13px" }}>{subtitle}</span>
    </div>
  );
}

function PillView({ pill }: { pill: Pill }) {
  return (
    <div
      title={`${pill.label}: ${pill.display}\n${pill.detail}`}
      style={pillStyle}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" }}>
        <span style={{ color: "var(--text-secondary)", fontSize: "11px", letterSpacing: "0.04em", textTransform: "uppercase" }}>
          {pill.label}
        </span>
        <Badge severity={pill.severity} dot pulse={pill.severity === "normal"}>
          {pill.display}
        </Badge>
      </div>
      <div style={{ marginTop: "6px", color: "var(--text-muted)", fontSize: "12px", lineHeight: 1.4 }}>
        {pill.detail}
      </div>
    </div>
  );
}

// ── Severity / copy derivation ─────────────────────────────────────────

function derivePills(data: HealthPayloadV2): Pill[] {
  return [
    runtimePill(data.runtime),
    databasePill(data.database),
    backendPill(data.backend),
    modelApiPill(data.modelApi),
    preTriggerPill(data.preTrigger),
  ];
}

function runtimePill(runtime: HealthRuntimeBlock): Pill {
  const map: Record<HealthRuntimeBlock["state"], { display: string; severity: PillSeverity; detail: string }> = {
    running: {
      display: "đang chạy",
      severity: "normal",
      detail: `Mô phỏng phát dữ liệu ổn định • uptime ${formatUptime(runtime.uptimeSeconds)}.`,
    },
    idle: {
      display: "rảnh",
      severity: "info",
      detail: "Không có phiên nào đang chạy. Khởi động một phiên ở trang Phiên mô phỏng.",
    },
    degraded: {
      display: "suy giảm",
      severity: "warning",
      detail: "Vẫn phục vụ vitals nhưng có dịch vụ phụ thuộc đang gặp sự cố.",
    },
    stopped: {
      display: "đã dừng",
      severity: "critical",
      detail: "Mô phỏng không phát dữ liệu. Kiểm tra log/console để biết chi tiết.",
    },
  };
  const m = map[runtime.state] ?? { display: runtime.state, severity: "info" as PillSeverity, detail: "Trạng thái không xác định." };
  return { label: "Runtime", state: runtime.state, display: m.display, severity: m.severity, detail: m.detail };
}

function databasePill(db: HealthDatabaseBlock): Pill {
  if (db.state === "connected") {
    const latency = db.lastCheckMs == null ? "" : ` • ${db.lastCheckMs}ms`;
    return {
      label: "Database",
      state: db.state,
      display: "kết nối",
      severity: "normal",
      detail: `Truy vấn cục bộ phản hồi nhanh${latency}.`,
    };
  }
  return {
    label: "Database",
    state: db.state,
    display: "ngắt",
    severity: "critical",
    detail: "Không truy vấn được DB cục bộ. Heartbeat + tick publish sẽ thất bại.",
  };
}

function backendPill(backend: HealthBackendBlock): Pill {
  const url = backend.url ? backend.url : "health-system";
  switch (backend.state) {
    case "connected":
      return {
        label: "Backend",
        state: backend.state,
        display: "kết nối",
        severity: "normal",
        detail: `${url} phản hồi ${backend.lastLatencyMs ?? "?"}ms.`,
      };
    case "slow":
      return {
        label: "Backend",
        state: backend.state,
        display: "chậm",
        severity: "warning",
        detail: `${url} phản hồi ${backend.lastLatencyMs ?? "?"}ms — vượt ngưỡng cho phép.`,
      };
    case "down":
      return {
        label: "Backend",
        state: backend.state,
        display: "ngắt",
        severity: "critical",
        detail: `Không gọi được ${url}. Telemetry/alerts sẽ không đẩy được.`,
      };
    case "unknown":
    default:
      return {
        label: "Backend",
        state: backend.state,
        display: "không rõ",
        severity: "offline",
        detail: "Chưa có lần probe nào hoàn tất.",
      };
  }
}

function modelApiPill(model: HealthModelApiBlock): Pill {
  const sourceCopy = model.lastScoreSource === "ai" ? "AI" : "heuristic";
  switch (model.state) {
    case "ready":
      return {
        label: "Model API",
        state: model.state,
        display: "sẵn sàng",
        severity: "normal",
        detail: `Sleep AI tại ${model.url} đang hoạt động • lần chấm điểm gần nhất: ${sourceCopy}.`,
      };
    case "unavailable":
      return {
        label: "Model API",
        state: model.state,
        display: "không sẵn sàng",
        severity: "warning",
        detail: "Sleep AI chưa phản hồi — đang dùng heuristic dự phòng cho điểm giấc ngủ.",
      };
    case "unknown":
    default:
      return {
        label: "Model API",
        state: model.state,
        display: "không rõ",
        severity: "offline",
        detail: "Đang chờ probe đầu tiên hoàn tất.",
      };
  }
}

function preTriggerPill(pre: HealthPreTriggerBlock): Pill {
  const thresholdCopy =
    pre.thresholdSource === "db"
      ? "ngưỡng đọc từ DB"
      : pre.thresholdSource === "fallback"
        ? "ngưỡng dự phòng (fallback)"
        : "không truy vấn được provider";
  switch (pre.mode) {
    case "active":
      return {
        label: "Pre-Trigger",
        state: pre.mode,
        display: "active",
        severity: "normal",
        detail: `Rule local + gọi model • ${thresholdCopy}.`,
      };
    case "shadow":
      return {
        label: "Pre-Trigger",
        state: pre.mode,
        display: "shadow",
        severity: "info",
        detail: `Chỉ chạy rule local, không gọi model • ${thresholdCopy}.`,
      };
    case "off":
    default:
      return {
        label: "Pre-Trigger",
        state: pre.mode,
        display: "tắt",
        severity: "offline",
        detail: `Pre-trigger không được kích hoạt • ${thresholdCopy}.`,
      };
  }
}

// ── Aggregate copy ─────────────────────────────────────────────────────

function summarise(data: HealthPayloadV2): string {
  if (data.degradedReasons.length === 0) {
    return "Tất cả hệ thống phụ trợ đang hoạt động.";
  }
  return `${data.degradedReasons.length} dấu hiệu suy giảm — xem chi tiết bên dưới.`;
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remMins = minutes % 60;
  if (hours < 24) return `${hours}h ${remMins}m`;
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return `${days}d ${remHours}h`;
}

// ── Styles ─────────────────────────────────────────────────────────────

const pillRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "12px",
};

const pillStyle: CSSProperties = {
  padding: "10px 12px",
  borderRadius: "var(--radius-md)",
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
};
