import { Activity, Heart, Stethoscope, TrendingUp } from "lucide-react";
import { Card } from "../../ui/Card";
import { Skeleton } from "../../ui/Skeleton";
import { usePersonalization } from "../../../hooks/usePersonalization";
import type {
  AdaptiveThresholdEntry,
  BaselineMetric,
  News2LitePayload,
  PersonalizationPayload,
  TrendSlopeEntry,
} from "../../../types/personalization";

// ---------------------------------------------------------------------------
// PersonalizationStatusCard — read-only sim-web card showing how the
// health_system backend personalizes risk evaluation for the bound user.
//
// Goal: side-by-side với UserProfileCard, demo viên xem thấy SIM sinh
// SpO2=92% và backend nói "trong baseline COPD của bạn".
// ---------------------------------------------------------------------------

interface PersonalizationStatusCardProps {
  userId: number | null;
}

const VITAL_LABELS: Record<string, { label: string; unit: string }> = {
  heart_rate: { label: "Nhịp tim", unit: "BPM" },
  spo2: { label: "SpO₂", unit: "%" },
  blood_pressure_sys: { label: "HA tâm thu", unit: "mmHg" },
  blood_pressure_dia: { label: "HA tâm trương", unit: "mmHg" },
  hrv: { label: "HRV", unit: "ms" },
  respiratory_rate: { label: "Nhịp thở", unit: "/phút" },
};

export function PersonalizationStatusCard({
  userId,
}: PersonalizationStatusCardProps) {
  const { data, isLoading, error } = usePersonalization(userId);

  if (userId == null) {
    return (
      <Card>
        <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "13px" }}>
          Chọn thiết bị có user gắn để xem trạng thái cá nhân hóa.
        </p>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <div style={{ display: "grid", gap: "8px" }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} style={{ height: "44px" }} />
          ))}
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <div style={{ padding: "12px", color: "var(--severity-warning)", fontSize: "13px" }}>
          Không tải được trạng thái cá nhân hóa.
        </div>
      </Card>
    );
  }

  if (!data || !data.enabled) {
    return (
      <Card>
        <div style={{ padding: "8px 0", color: "var(--text-muted)", fontSize: "13px" }}>
          Cá nhân hóa đang TẮT cho user này (feature flag OFF).
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div style={{ display: "grid", gap: "14px" }}>
        <Header status={data.baseline_status} message={data.personal_context_message} />
        <BaselineSection baselines={data.baselines} />
        <AdaptiveSection adaptive={data.adaptive_thresholds} />
        {data.news2_lite ? <News2Section news2={data.news2_lite} /> : null}
        <TrendSection trends={data.trend_slopes} />
        {data.hard_floor_violations.length > 0 ? (
          <HardFloorAlert vitals={data.hard_floor_violations} />
        ) : null}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function Header({
  status,
  message,
}: {
  status: PersonalizationPayload["baseline_status"];
  message: string | null;
}) {
  const isLearning = status === "learning";
  const accent = isLearning ? "var(--severity-warning)" : "var(--severity-success)";
  const label = isLearning ? "Đang học baseline" : "Cá nhân hóa sẵn sàng";

  return (
    <div style={{ display: "grid", gap: "6px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Stethoscope size={16} color={accent} />
        <span style={{ fontSize: "13px", fontWeight: 700, color: accent }}>
          {label}
        </span>
      </div>
      {message ? (
        <p
          style={{
            margin: 0,
            fontSize: "12.5px",
            color: "var(--text-secondary)",
            lineHeight: 1.5,
          }}
        >
          {message}
        </p>
      ) : null}
    </div>
  );
}

function BaselineSection({ baselines }: { baselines: Record<string, BaselineMetric> }) {
  const entries = Object.entries(baselines).filter(([k]) => k in VITAL_LABELS);
  if (entries.length === 0) return null;

  return (
    <div>
      <SectionTitle icon={<Heart size={13} />} text="Baseline cá nhân" />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
          gap: "6px",
        }}
      >
        {entries.map(([key, metric]) => {
          const label = VITAL_LABELS[key];
          const meanText = metric.mean != null
            ? `${metric.mean.toFixed(key === "spo2" ? 1 : 0)} ${label.unit}`
            : "—";
          const stdText = metric.std != null ? `± ${metric.std.toFixed(1)}` : "";
          const statusColor = metric.status === "ready"
            ? "var(--severity-success)" : "var(--severity-warning)";

          return (
            <div
              key={key}
              style={{
                padding: "8px 10px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-elevated)",
              }}
            >
              <div style={{ fontSize: "10.5px", color: "var(--text-muted)", textTransform: "uppercase" }}>
                {label.label}
              </div>
              <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                {meanText} {stdText}
              </div>
              <div style={{ fontSize: "10.5px", color: statusColor }}>
                {metric.status === "ready" ? "ready" : "learning"} · n={metric.sample_size}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AdaptiveSection({
  adaptive,
}: {
  adaptive: Record<string, AdaptiveThresholdEntry>;
}) {
  const entries = Object.entries(adaptive);
  if (entries.length === 0) return null;

  return (
    <div>
      <SectionTitle icon={<Activity size={13} />} text="Ngưỡng cá nhân theo bệnh nền" />
      <div style={{ display: "grid", gap: "6px" }}>
        {entries.map(([vital, mod]) => (
          <div
            key={vital}
            style={{
              padding: "6px 10px",
              borderRadius: "var(--radius-md)",
              background: "var(--bg-elevated)",
              fontSize: "12px",
              color: "var(--text-secondary)",
            }}
          >
            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{vital}</span>{" "}
            min {mod.modifier_min >= 0 ? "+" : ""}{mod.modifier_min} · max {mod.modifier_max >= 0 ? "+" : ""}{mod.modifier_max}{" "}
            <span style={{ color: "var(--text-muted)" }}>({mod.source_conditions.join(", ")})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function News2Section({ news2 }: { news2: News2LitePayload }) {
  const color = news2.risk_level === "critical"
    ? "var(--severity-critical)"
    : news2.risk_level === "high" || news2.risk_level === "medium"
      ? "var(--severity-warning)"
      : "var(--severity-success)";

  return (
    <div>
      <SectionTitle icon={<Activity size={13} />} text="NEWS2-Lite" />
      <div
        style={{
          padding: "8px 10px",
          borderRadius: "var(--radius-md)",
          background: "var(--bg-elevated)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <span style={{ fontSize: "20px", fontWeight: 800, color }}>{news2.total_score}</span>
        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>/ 15</span>
        <span style={{ fontSize: "12px", color: "var(--text-secondary)", flex: 1 }}>
          {news2.note}
        </span>
      </div>
    </div>
  );
}

function TrendSection({
  trends,
}: {
  trends: Record<string, TrendSlopeEntry[]>;
}) {
  const entries = Object.entries(trends);
  if (entries.length === 0) return null;

  return (
    <div>
      <SectionTitle icon={<TrendingUp size={13} />} text="Xu hướng" />
      <div style={{ display: "grid", gap: "4px" }}>
        {entries.map(([vital, slopes]) => (
          <div key={vital} style={{ fontSize: "11.5px", color: "var(--text-secondary)" }}>
            <strong style={{ color: "var(--text-primary)" }}>{vital}:</strong>{" "}
            {slopes.map((s) => `${s.window}=${s.direction}`).join(" · ")}
          </div>
        ))}
      </div>
    </div>
  );
}

function HardFloorAlert({ vitals }: { vitals: string[] }) {
  return (
    <div
      style={{
        padding: "8px 10px",
        borderRadius: "var(--radius-md)",
        background: "rgba(239,68,68,0.08)",
        border: "1px solid rgba(239,68,68,0.32)",
        color: "var(--severity-critical)",
        fontSize: "12px",
      }}
    >
      <strong>Hard floor vi phạm:</strong> {vitals.join(", ")} — luôn critical bất kể cá nhân hóa.
    </div>
  );
}

function SectionTitle({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        marginBottom: "6px",
        color: "var(--text-muted)",
        fontSize: "10.5px",
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.06em",
      }}
    >
      {icon}
      {text}
    </div>
  );
}
