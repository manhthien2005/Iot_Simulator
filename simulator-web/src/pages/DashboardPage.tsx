import { AlertTimeline } from "../components/domain/AlertTimeline";
import { Card } from "../components/ui/Card";
import { KpiCard } from "../components/ui/KpiCard";
import { Skeleton } from "../components/ui/Skeleton";
import { useDashboardSummary } from "../hooks/useDashboardSummary";
import { useRecentEvents } from "../hooks/useRecentEvents";

export function DashboardPage() {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: events = [] } = useRecentEvents(10, 3000);

  return (
    <section style={{ display: "grid", gap: "20px" }}>
      <div>
        <h1 className="page-title">Bảng điều khiển</h1>
        <p className="page-subtitle">Tổng quan KPI và dòng sự kiện. Phần sinh hiệu trực tiếp được hiển thị trong trang Phiên mô phỏng.</p>
      </div>

      {/* KPI Grid — responsive via .kpi-grid class (4→2→1 columns) */}
      <div className="kpi-grid">
        {summaryLoading ? (
          <>
            <Skeleton style={{ height: "88px" }} />
            <Skeleton style={{ height: "88px" }} />
            <Skeleton style={{ height: "88px" }} />
            <Skeleton style={{ height: "88px" }} />
          </>
        ) : (
          <>
            <KpiCard title="Thiết bị" value={summary?.totalDevices ?? 0} subtitle="đã đăng ký" />
            <KpiCard title="Đang hoạt động" value={summary?.activeDevices ?? 0} subtitle="đang truyền dữ liệu" />
            <KpiCard title="Cảnh báo" value={summary?.alertsLastHour ?? 0} subtitle="trong 1 giờ gần nhất" />
            <KpiCard title="Độ trễ" value={`${summary?.avgLatencyMs ?? 0}ms`} subtitle="độ trễ phát dữ liệu" />
          </>
        )}
      </div>

      <Card>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>
          Để theo dõi HR, SpO2, nhiệt độ và huyết áp theo thời gian thực, hãy vào trang <strong>Phiên mô phỏng</strong>.
        </p>
      </Card>

      {/* Section header cho timeline */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div
          style={{
            width: "3px",
            height: "18px",
            borderRadius: "2px",
            background: "var(--accent-cyan)",
          }}
        />
        <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>Dòng sự kiện gần đây</h2>
      </div>

      <AlertTimeline events={events} />
    </section>
  );
}
