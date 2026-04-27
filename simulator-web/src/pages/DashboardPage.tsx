import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { AlertTimeline } from "../components/domain/AlertTimeline";
import { DegradedBanner } from "../components/domain/DegradedBanner";
import { SystemHealthHero } from "../components/domain/SystemHealthHero";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { KpiCard, type KpiSeverity } from "../components/ui/KpiCard";
import { Skeleton } from "../components/ui/Skeleton";
import { useRecentEvents } from "../hooks/useRecentEvents";
import { useSystemHealth } from "../hooks/useSystemHealth";
import type {
  HealthPayloadV2,
  HealthPreTriggerBlock,
  HealthTelemetryBlock,
} from "../types/health";

// ---------------------------------------------------------------------------
// DashboardPage — Module A: health-first information architecture.
//   1. SystemHealthHero (5 truth pills)
//   2. DegradedBanner (only when degradedReasons.length > 0)
//   3. Telemetry KPIs derived from `health.telemetry` + `health.preTrigger`
//   4. Recent events timeline
// All KPI severity comes from the v2 payload — no local invented state.
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    isFetching: healthFetching,
    refetch: refetchHealth,
  } = useSystemHealth();
  const { data: events = [] } = useRecentEvents(10, 3000);

  return (
    <section style={{ display: "grid", gap: "20px" }}>
      <div>
        <h1 className="page-title">Bảng điều khiển</h1>
        <p className="page-subtitle">
          Tổng quan sức khỏe hệ thống mô phỏng và dòng sự kiện. Phần sinh hiệu trực tiếp được hiển thị trong trang Phiên mô phỏng.
        </p>
      </div>

      {/* 1. Hero — single source of truth for system health */}
      <SystemHealthHero
        data={health}
        isLoading={healthLoading}
        error={healthError}
        isFetching={healthFetching}
        onRetry={() => {
          void refetchHealth();
        }}
      />

      {/* 2. Degraded banner — only renders when reasons present */}
      {health ? <DegradedBanner reasons={health.degradedReasons} /> : null}

      {/* 3. Telemetry KPIs — derived from health.telemetry + preTrigger */}
      <SectionHeader>Chỉ số vận hành</SectionHeader>
      <TelemetryKpiGrid
        health={health}
        loading={healthLoading}
        error={healthError}
        isFetching={healthFetching}
        onRetry={() => {
          void refetchHealth();
        }}
      />

      <Card>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>
          Để theo dõi HR, SpO2, nhiệt độ và huyết áp theo thời gian thực, hãy vào trang <strong>Phiên mô phỏng</strong>.
        </p>
      </Card>

      {/* 4. Recent events timeline */}
      <SectionHeader>Dòng sự kiện gần đây</SectionHeader>
      <AlertTimeline events={events} />
    </section>
  );
}

// ── Subcomponents ───────────────────────────────────────────────────────

function SectionHeader({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div
        style={{
          width: "3px",
          height: "18px",
          borderRadius: "2px",
          background: "var(--accent-cyan)",
        }}
      />
      <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>{children}</h2>
    </div>
  );
}

function TelemetryKpiGrid({
  health,
  loading,
  error,
  isFetching,
  onRetry,
}: {
  health: HealthPayloadV2 | undefined;
  loading: boolean;
  error: unknown;
  isFetching: boolean;
  onRetry: () => void;
}) {
  // Module H — bug 2 fix: when /api/sim/health hasn't responded yet,
  // render the skeleton + a retry CTA instead of a row of "0"s.  Showing
  // zeros while the BE is down looked like "all metrics are quiet" —
  // misleading the operator into thinking the system was healthy.
  if ((loading && !health) || (error && !health)) {
    return (
      <Card>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "12px",
            flexWrap: "wrap",
            marginBottom: "10px",
          }}
        >
          <span style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
            {error
              ? "Chưa có chỉ số vận hành — đang chờ Simulator API."
              : "Đang tải chỉ số vận hành…"}
          </span>
          {Boolean(error) && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onRetry}
              loading={isFetching}
              leftIcon={<RefreshCw size={14} />}
            >
              Thử lại
            </Button>
          )}
        </div>
        <div className="kpi-grid">
          <Skeleton style={{ height: "108px" }} />
          <Skeleton style={{ height: "108px" }} />
          <Skeleton style={{ height: "108px" }} />
          <Skeleton style={{ height: "108px" }} />
          <Skeleton style={{ height: "108px" }} />
        </div>
      </Card>
    );
  }

  const telemetry: HealthTelemetryBlock = health?.telemetry ?? {
    devicesSimulated: 0,
    sessionsRunning: 0,
    alertsLastHour: 0,
    avgPublishLatencyMs: 0,
  };
  const pre: HealthPreTriggerBlock = health?.preTrigger ?? {
    mode: "off",
    enableModelCalls: false,
    thresholdSource: "unavailable",
  };

  const latencySeverity: KpiSeverity =
    telemetry.avgPublishLatencyMs >= 1500
      ? "critical"
      : telemetry.avgPublishLatencyMs >= 500
        ? "warning"
        : "ok";

  const alertsSeverity: KpiSeverity =
    telemetry.alertsLastHour >= 20 ? "critical" : telemetry.alertsLastHour >= 5 ? "warning" : "neutral";

  const thresholdLabel: Record<HealthPreTriggerBlock["thresholdSource"], { value: string; severity: KpiSeverity; subtitle: string }> = {
    db: { value: "DB", severity: "ok", subtitle: "ngưỡng đọc từ database" },
    fallback: { value: "Fallback", severity: "warning", subtitle: "đang dùng ngưỡng dự phòng" },
    unavailable: { value: "—", severity: "critical", subtitle: "không truy vấn được provider" },
  };
  const threshold = thresholdLabel[pre.thresholdSource];

  return (
    <div className="kpi-grid">
      <KpiCard
        title="Thiết bị mô phỏng"
        value={telemetry.devicesSimulated}
        subtitle="đã đăng ký trong runtime"
      />
      <KpiCard
        title="Phiên đang chạy"
        value={telemetry.sessionsRunning}
        subtitle={telemetry.sessionsRunning === 0 ? "không có phiên hoạt động" : "đang truyền vitals"}
      />
      <KpiCard
        title="Cảnh báo 1 giờ"
        value={telemetry.alertsLastHour}
        subtitle="cảnh báo gần nhất"
        severity={alertsSeverity}
      />
      <KpiCard
        title="Độ trễ phát"
        value={`${telemetry.avgPublishLatencyMs}ms`}
        subtitle="trung bình các phiên đang chạy"
        severity={latencySeverity}
      />
      <KpiCard
        title="Nguồn ngưỡng"
        value={threshold.value}
        subtitle={threshold.subtitle}
        severity={threshold.severity}
      />
    </div>
  );
}
