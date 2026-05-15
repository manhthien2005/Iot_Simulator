import type { CSSProperties } from "react";
import { AlertTriangle, Gauge, RefreshCw, Radio, Watch } from "lucide-react";
import { DegradedBanner } from "../components/domain/DegradedBanner";
import { LiveFeed } from "../components/domain/dashboard/LiveFeed";
import { MetricTile, type MetricSeverity } from "../components/domain/dashboard/MetricTile";
import { SystemStatusCards } from "../components/domain/dashboard/SystemStatusCards";
import { Button } from "../components/ui/Button";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useKpiHistory } from "../hooks/useKpiHistory";
import { useRecentEvents } from "../hooks/useRecentEvents";
import { useSystemHealth } from "../hooks/useSystemHealth";
import type { HealthTelemetryBlock } from "../types/health";

// ---------------------------------------------------------------------------
// DashboardPage — Cockpit Hybrid layout.
//
// Information hierarchy, top → bottom:
//   1. Header bar — title + manual refresh.
//   2. SystemStatusCards — 5-block service status grid with title,
//      description, status, and a pulsing ping when healthy.
//   3. DegradedBanner — conditional, unchanged.
//   4. Two-column working area:
//        • left  : 2×2 MetricTile grid (devices / sessions / alerts /
//          latency) with client-side sparkline trends.
//        • right : LiveFeed — dense compact event list, replaces the
//          old AlertTimeline card.
//
// Removed from the legacy layout:
//   * Long PageHeader subtitle (info was duplicated in the reminder card).
//   * Card reminder "Để theo dõi HR, SpO2…" (pro operator doesn't need
//     a navigation breadcrumb).
//   * KPI "Nguồn ngưỡng" — already covered by the Pre-Trigger chip.
//   * KPI subtitle text — sparkline + tooltip carry the trend story.
//   * Duplicated section headers around the metric grid + event feed.
// ---------------------------------------------------------------------------

const FALLBACK_TELEMETRY: HealthTelemetryBlock = {
  devicesSimulated: 0,
  sessionsRunning: 0,
  alertsLastHour: 0,
  avgPublishLatencyMs: 0,
};

export function DashboardPage() {
  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    isFetching: healthFetching,
    refetch: refetchHealth,
  } = useSystemHealth();
  const { data: events = [] } = useRecentEvents(12, 3000);

  const history = useKpiHistory(health?.telemetry);
  const telemetry = health?.telemetry ?? FALLBACK_TELEMETRY;

  const latencySeverity: MetricSeverity =
    telemetry.avgPublishLatencyMs >= 1500
      ? "critical"
      : telemetry.avgPublishLatencyMs >= 500
        ? "warning"
        : "ok";

  const alertsSeverity: MetricSeverity =
    telemetry.alertsLastHour >= 20 ? "critical" : telemetry.alertsLastHour >= 5 ? "warning" : "neutral";

  return (
    <section className="page-section" style={{ gap: "16px" }}>
      {/* 1. Header bar — title + manual refresh */}
      <header style={headerStyle}>
        <h1 className="page-title" style={{ fontSize: "30px", letterSpacing: "-0.02em" }}>
          Bảng điều khiển
        </h1>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void refetchHealth();
          }}
          loading={healthFetching}
          leftIcon={<RefreshCw size={14} />}
        >
          Làm mới
        </Button>
      </header>

      {/* 2. System status — 5 service cards (block layout) */}
      <SectionHeader>Trạng thái hệ thống</SectionHeader>
      <SystemStatusCards
        data={health}
        isLoading={healthLoading}
        error={healthError}
        isFetching={healthFetching}
        onRetry={() => {
          void refetchHealth();
        }}
      />

      {/* 3. Degraded banner — only renders when reasons present */}
      {health ? <DegradedBanner reasons={health.degradedReasons} /> : null}

      {/* 4. Working area — 2x2 metric tile grid + live feed column */}
      <SectionHeader>Chỉ số vận hành</SectionHeader>
      <div className="dashboard-cockpit-grid">
        <div className="dashboard-cockpit-metrics">
          <MetricTile
            icon={<Watch size={16} />}
            label="Thiết bị"
            value={telemetry.devicesSimulated}
            history={history.devicesSimulated}
            tooltip="Số thiết bị đã đăng ký trong runtime."
          />
          <MetricTile
            icon={<Radio size={16} />}
            label="Phiên chạy"
            value={telemetry.sessionsRunning}
            history={history.sessionsRunning}
            tooltip={
              telemetry.sessionsRunning === 0
                ? "Không có phiên hoạt động."
                : "Số phiên đang truyền vitals."
            }
          />
          <MetricTile
            icon={<AlertTriangle size={16} />}
            label="Cảnh báo 1h"
            value={telemetry.alertsLastHour}
            severity={alertsSeverity}
            history={history.alertsLastHour}
            tooltip="Tổng cảnh báo trong 60 phút gần nhất."
          />
          <MetricTile
            icon={<Gauge size={16} />}
            label="Độ trễ phát"
            value={`${telemetry.avgPublishLatencyMs}ms`}
            severity={latencySeverity}
            history={history.avgPublishLatencyMs}
            tooltip="Trung bình độ trễ publish của các phiên đang chạy."
          />
        </div>
        <LiveFeed events={events} maxRows={12} />
      </div>
    </section>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  flexWrap: "wrap",
  gap: "12px",
};
