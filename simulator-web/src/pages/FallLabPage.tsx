import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock,
  CpuIcon,
  Info,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  Zap,
} from "lucide-react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Sparkline } from "../components/ui/Sparkline";
import { useDevices } from "../hooks/useDevices";
import { useSessions } from "../hooks/useSessions";
import { useFallState } from "../hooks/useFallState";
import { useLatestMotion } from "../hooks/useLatestMotion";
import { useRecentEvents } from "../hooks/useRecentEvents";
import { useConfirm } from "../hooks/useConfirm";
import { injectFallEvent, injectSosCancel } from "../services/eventApi";
import { useSessionStore } from "../stores/sessionStore";
import { runWithToast } from "../utils/toast";
import { describeFallVariant } from "../utils/motionLabels";
import { POLL_INTERVALS, FALL_LAB_RECENT_EVENTS_LIMIT } from "../config/defaults";
import {
  FALL_VARIANT_CATALOGUE,
  type AIPrediction,
  type AIPredictionLabel,
  type CountdownPolicy,
  type FallEventEntry,
  type FallState,
  type FallStateValue,
  type FallVariantId,
  type FallVariantSpec,
} from "../types/fall";
import type { MotionLatest } from "../types/motion";
import type { SimulatedDevice } from "../types/device";

// ---------------------------------------------------------------------------
// FallLabPage — Module FA dedicated full-page lab.
//
// Replaces the cramped Fall card on `SessionRunnerPage` for operators who
// specifically want to validate the fall AI pipeline.  Three columns:
//
//   ┌──────────── Variant Picker ──────────┬───── Live AI Verdict ──────┐
//   │  6 severity-coded buttons            │  Probability + risk band   │
//   │  Description card for hovered/active │  Top 3 SHAP features (VI)  │
//   │                                      │  Countdown + cancel        │
//   └──────────────────────────────────────┴────────────────────────────┘
//   ┌──────────────────────── Motion Window ────────────────────────────┐
//   │  Aligned to the window the AI scored, accel-magnitude hero +      │
//   │  collapsible 6-axis detail.                                       │
//   └───────────────────────────────────────────────────────────────────┘
//   ┌──────────────────── Recent Fall Events ───────────────────────────┐
//   │  Table of the last 15 fall_detected / sos_cancel events with the  │
//   │  AI verdict metadata captured at inject time.                     │
//   └───────────────────────────────────────────────────────────────────┘
//
// All state is BE-derived: variant policy, countdown total, AI verdict,
// motion window timestamp, and recent events.  The FE never invents the
// countdown or guesses what the AI will say — it shows what the BE
// reports and tints accordingly.
// ---------------------------------------------------------------------------

export function FallLabPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const preselectedDeviceId = searchParams.get("deviceId");

  const { data: devices = [] } = useDevices();
  const { data: sessions = [] } = useSessions();
  const { activeSessionId } = useSessionStore();

  const activeDevices = useMemo(() => devices.filter((d) => d.isOnline), [devices]);

  // Pick the focal device.  Priority:
  //   1. ?deviceId= URL param (deep-link from SessionRunnerPage).
  //   2. Last-used (component state).
  //   3. First active device.
  const [focusDeviceId, setFocusDeviceId] = useState<string>("");
  useEffect(() => {
    if (focusDeviceId && activeDevices.some((d) => d.id === focusDeviceId)) return;
    const fallback =
      (preselectedDeviceId && activeDevices.some((d) => d.id === preselectedDeviceId)
        ? preselectedDeviceId
        : null)
      ?? activeDevices[0]?.id
      ?? "";
    setFocusDeviceId(fallback);
  }, [activeDevices, focusDeviceId, preselectedDeviceId]);

  const focusDevice = activeDevices.find((d) => d.id === focusDeviceId) ?? null;

  const activeSession = useMemo(() => {
    const explicit = sessions.find((s) => s.id === activeSessionId);
    if (explicit) return explicit;
    if (focusDeviceId) {
      const sessionForDevice = sessions.find(
        (s) => s.status === "running" && s.deviceIds.includes(focusDeviceId),
      );
      if (sessionForDevice) return sessionForDevice;
    }
    return sessions.find((s) => s.status === "running") ?? null;
  }, [activeSessionId, sessions, focusDeviceId]);

  const { data: fallState } = useFallState(activeSession?.id ?? null, focusDeviceId || null);
  const { data: motion } = useLatestMotion(activeSession?.id ?? null, focusDeviceId || null);
  const { data: recentEvents = [] } = useRecentEvents(
    FALL_LAB_RECENT_EVENTS_LIMIT,
    POLL_INTERVALS.fallLabEvents,
    {
      enabled: Boolean(focusDeviceId),
      select: (events) => events.filter((e) => e.deviceId === focusDeviceId).slice(0, 20),
    },
  );

  const [pendingVariant, setPendingVariant] = useState<FallVariantId | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [hoveredVariant, setHoveredVariant] = useState<FallVariantId | null>(null);
  const [confirm, confirmDialog] = useConfirm();

  const guardDisabled =
    !activeSession
    || !focusDeviceId
    || activeSession.status !== "running"
    || !!pendingVariant
    || cancelling;

  async function handleInjectVariant(variant: FallVariantSpec) {
    if (guardDisabled) return;
    if (variant.severity === "critical") {
      const ok = await confirm({
        severity: "critical",
        title: `Mô phỏng "${variant.label}"?`,
        description:
          `${variant.description}\n\n` +
          `Countdown: ${variant.countdownSec}s · ` +
          `Đẩy alert: ${variant.pushesAlert ? "có" : "không"} · ` +
          `Cho phép huỷ: ${variant.allowsCancel ? "có" : "không"}.`,
        confirmLabel: `Inject ${variant.label}`,
      });
      if (!ok) return;
    }
    setPendingVariant(variant.id);
    try {
      await runWithToast(injectFallEvent(focusDeviceId, variant.id), {
        loading: `Đang inject "${variant.label}"…`,
        success: `Đã inject "${variant.label}". Chờ AI…`,
        error: `Inject "${variant.label}" thất bại.`,
      });
    } catch {
      // toast already shown
    } finally {
      setPendingVariant(null);
    }
  }

  async function handleCancel() {
    if (!focusDeviceId) return;
    setCancelling(true);
    try {
      await runWithToast(injectSosCancel(focusDeviceId), {
        loading: "Đang gửi sos_cancel…",
        success: "Đã huỷ — BE FSM trở lại streaming.",
        error: "Huỷ SOS thất bại — BE có thể vẫn còn ở fall_countdown.",
      });
    } catch {
      // toast already shown
    } finally {
      setCancelling(false);
    }
  }

  const focalVariantSpec =
    (hoveredVariant && FALL_VARIANT_CATALOGUE.find((v) => v.id === hoveredVariant))
    ?? null;

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <header>
        <h1 className="page-title">Phòng thí nghiệm té ngã</h1>
        <p className="page-subtitle">
          Inject các kịch bản té ngã, theo dõi verdict của AI ({" "}
          <code>healthguard-model-api</code>) và xác minh BE escalation tương ứng.
          Tất cả số liệu (verdict, countdown, motion window) đều derive từ BE — FE
          không invent dữ liệu.
        </p>
      </header>

      <DeviceSessionBar
        focusDevice={focusDevice}
        focusDeviceId={focusDeviceId}
        activeDevices={activeDevices}
        activeSessionStatus={activeSession?.status ?? null}
        onChange={(id) => {
          setFocusDeviceId(id);
          if (id) {
            const next = new URLSearchParams(searchParams);
            next.set("deviceId", id);
            setSearchParams(next, { replace: true });
          }
        }}
      />

      {!activeSession || activeSession.status !== "running" ? (
        <Card>
          <EmptyState
            icon={Activity}
            title="Chưa có phiên đang chạy"
            description="Bật một phiên ở tab 'Mô phỏng tín hiệu sinh tồn' và đảm bảo có thiết bị đang online để bắt đầu inject té ngã."
          />
        </Card>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0,1.1fr) minmax(0,1fr)",
            gap: "14px",
          }}
        >
          <VariantPickerCard
            disabled={guardDisabled}
            pendingVariant={pendingVariant}
            onPick={handleInjectVariant}
            onHover={setHoveredVariant}
            focalVariantSpec={focalVariantSpec}
          />
          <AIVerdictPanel
            fallState={fallState ?? null}
            disabled={guardDisabled}
            onCancel={handleCancel}
            cancelling={cancelling}
          />
        </div>
      )}

      <MotionWindowCard motion={motion ?? null} fallState={fallState ?? null} />

      <RecentEventsCard events={recentEvents} />

      {confirmDialog}
    </section>
  );
}

// ===========================================================================
// Device + session selector strip
// ===========================================================================

function DeviceSessionBar({
  focusDevice,
  focusDeviceId,
  activeDevices,
  activeSessionStatus,
  onChange,
}: {
  focusDevice: SimulatedDevice | null;
  focusDeviceId: string;
  activeDevices: SimulatedDevice[];
  activeSessionStatus: string | null;
  onChange: (id: string) => void;
}) {
  return (
    <Card padding="sm">
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "12px",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1 }}>
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Thiết bị mục tiêu:</span>
          <select
            value={focusDeviceId}
            onChange={(event) => onChange(event.target.value)}
            aria-label="Thiết bị mục tiêu"
            style={selectStyle}
            disabled={activeDevices.length === 0}
          >
            {activeDevices.length === 0 ? <option value="">Không có thiết bị nào online</option> : null}
            {activeDevices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name}
              </option>
            ))}
          </select>
          {focusDevice ? (
            <Badge severity={deviceStateSeverity(focusDevice.state)}>
              {deviceStateLabel(focusDevice.state)}
            </Badge>
          ) : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Phiên:</span>
          <Badge severity={activeSessionStatus === "running" ? "normal" : "offline"} dot pulse={activeSessionStatus === "running"}>
            {activeSessionStatus === "running" ? "Đang chạy" : activeSessionStatus ?? "Chưa khởi động"}
          </Badge>
        </div>
      </div>
    </Card>
  );
}

function deviceStateLabel(state: string): string {
  switch (state) {
    case "streaming":
      return "Streaming";
    case "fall_countdown":
      return "Đang đếm ngược";
    case "sos_active":
      return "SOS active";
    case "warning":
      return "Cảnh báo";
    case "critical":
      return "Critical";
    case "offline":
      return "Offline";
    default:
      return state;
  }
}

function deviceStateSeverity(state: string): "normal" | "warning" | "critical" | "offline" | "info" {
  if (state === "sos_active" || state === "critical") return "critical";
  if (state === "fall_countdown" || state === "warning") return "warning";
  if (state === "offline" || state === "retired") return "offline";
  return "normal";
}

// ===========================================================================
// Variant picker
// ===========================================================================

function VariantPickerCard({
  disabled,
  pendingVariant,
  onPick,
  onHover,
  focalVariantSpec,
}: {
  disabled: boolean;
  pendingVariant: FallVariantId | null;
  onPick: (variant: FallVariantSpec) => void;
  onHover: (id: FallVariantId | null) => void;
  focalVariantSpec: FallVariantSpec | null;
}) {
  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <strong>Kịch bản té ngã (6)</strong>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            Hover/click để xem chi tiết
          </span>
        </div>
      }
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "8px" }}>
        {FALL_VARIANT_CATALOGUE.map((variant) => (
          <VariantButton
            key={variant.id}
            variant={variant}
            disabled={disabled}
            pending={pendingVariant === variant.id}
            onPick={onPick}
            onHover={onHover}
          />
        ))}
      </div>
      <div style={{ marginTop: "12px" }}>
        <VariantDetailCard variant={focalVariantSpec} />
      </div>
    </Card>
  );
}

function VariantButton({
  variant,
  disabled,
  pending,
  onPick,
  onHover,
}: {
  variant: FallVariantSpec;
  disabled: boolean;
  pending: boolean;
  onPick: (v: FallVariantSpec) => void;
  onHover: (id: FallVariantId | null) => void;
}) {
  const palette = severityPalette(variant.severity);
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onPick(variant)}
      onMouseEnter={() => onHover(variant.id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(variant.id)}
      onBlur={() => onHover(null)}
      style={{
        display: "grid",
        gap: "4px",
        textAlign: "left",
        padding: "12px",
        borderRadius: "var(--radius-md)",
        border: `1px solid ${palette.border}`,
        background: pending ? palette.bg : "var(--bg-elevated)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        transition:
          "background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
        color: "var(--text-primary)",
      }}
      aria-label={`${variant.label} — ${variant.subtitle}`}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <strong style={{ fontSize: "13px" }}>{pending ? "Đang gửi…" : variant.label}</strong>
        <Badge severity={variant.severity}>{severityShortLabel(variant.severity)}</Badge>
      </div>
      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{variant.subtitle}</span>
    </button>
  );
}

function VariantDetailCard({ variant }: { variant: FallVariantSpec | null }) {
  if (!variant) {
    return (
      <div
        style={{
          padding: "10px 12px",
          fontSize: "12px",
          color: "var(--text-muted)",
          background: "var(--bg-base)",
          border: "1px dashed var(--border-default)",
          borderRadius: "var(--radius-md)",
        }}
      >
        Hover hoặc click một kịch bản để xem chi tiết policy + countdown.
      </div>
    );
  }
  return (
    <div
      style={{
        display: "grid",
        gap: "8px",
        padding: "10px 12px",
        background: "var(--bg-base)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <strong style={{ fontSize: "13px" }}>{variant.label}</strong>
      <p style={{ margin: 0, fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
        {variant.description}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
        <PolicyChip
          icon={<Clock size={12} />}
          label={
            variant.countdownSec === 0
              ? "Không countdown"
              : `Countdown ${variant.countdownSec}s`
          }
        />
        <PolicyChip
          icon={<Zap size={12} />}
          label={variant.pushesAlert ? "Đẩy alert webhook" : "Không đẩy alert"}
          tone={variant.pushesAlert ? "warning" : "normal"}
        />
        {variant.autoResolve && (
          <PolicyChip
            icon={<CheckCircle2 size={12} />}
            label="Tự huỷ countdown"
            tone="normal"
          />
        )}
        <PolicyChip
          icon={<ShieldAlert size={12} />}
          label={variant.allowsCancel ? "Cho phép 'Tôi ổn'" : "Không cho huỷ"}
          tone={variant.allowsCancel ? "normal" : "critical"}
        />
      </div>
    </div>
  );
}

function PolicyChip({
  icon,
  label,
  tone = "info",
}: {
  icon: ReactNode;
  label: string;
  tone?: "normal" | "warning" | "critical" | "offline" | "info";
}) {
  const palette = severityPalette(tone === "info" ? "normal" : tone);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "3px 8px",
        fontSize: "11px",
        borderRadius: "var(--radius-full)",
        border: `1px solid ${palette.border}`,
        background: "var(--bg-elevated)",
        color: palette.text,
      }}
    >
      {icon}
      {label}
    </span>
  );
}

// ===========================================================================
// AI verdict + countdown panel
// ===========================================================================

function AIVerdictPanel({
  fallState,
  disabled,
  onCancel,
  cancelling,
}: {
  fallState: FallState | null;
  disabled: boolean;
  onCancel: () => void;
  cancelling: boolean;
}) {
  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <Brain size={14} />
            <strong>AI verdict + countdown</strong>
          </span>
          <FallStateBadge value={fallState?.fallState ?? "idle"} />
        </div>
      }
    >
      <div style={{ display: "grid", gap: "12px" }}>
        <AIVerdictBlock prediction={fallState?.aiPrediction ?? null} />
        <CountdownBlock
          fallState={fallState}
          disabled={disabled || cancelling}
          cancelling={cancelling}
          onCancel={onCancel}
        />
      </div>
    </Card>
  );
}

function FallStateBadge({ value }: { value: FallStateValue }) {
  const map: Record<FallStateValue, { label: string; severity: "normal" | "warning" | "critical" | "offline" | "info" }> = {
    idle: { label: "Sẵn sàng", severity: "offline" },
    fall_detected: { label: "Đã ghi nhận", severity: "warning" },
    fall_countdown: { label: "Đang đếm ngược", severity: "warning" },
    sos_active: { label: "SOS kích hoạt", severity: "critical" },
    fall_resolved: { label: "Đã hủy / phục hồi", severity: "normal" },
  };
  const entry = map[value];
  return <Badge severity={entry.severity}>{entry.label}</Badge>;
}

function AIVerdictBlock({ prediction }: { prediction: AIPrediction | null }) {
  if (!prediction) {
    return (
      <div style={emptyVerdictStyle}>
        <Info size={14} style={{ color: "var(--text-muted)" }} />
        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
          Chưa có verdict — inject một kịch bản té ngã ở bên trái để nhận AI prediction.
        </span>
      </div>
    );
  }

  const probabilityPct = Math.round(prediction.probability * 100);
  const confidencePct = Math.round(prediction.confidence * 100);
  const palette = severityPalette(prediction.riskBand);

  if (prediction.modelStatus !== "ok") {
    return (
      <div
        style={{
          display: "grid",
          gap: "6px",
          padding: "10px 12px",
          background: "var(--bg-elevated)",
          border: "1px dashed var(--border-default)",
          borderRadius: "var(--radius-md)",
        }}
      >
        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <CpuIcon size={14} style={{ color: "var(--text-muted)" }} />
          <strong style={{ fontSize: "13px" }}>{aiStatusLabel(prediction.modelStatus)}</strong>
        </div>
        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
          {prediction.explanationSummary
            ?? "AI không trả về verdict — hệ thống đang dựa vào pre-trigger fallback."}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gap: "10px",
        padding: "12px",
        background: palette.bg,
        border: `1px solid ${palette.border}`,
        borderRadius: "var(--radius-md)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {prediction.riskBand === "critical" ? (
            <ShieldAlert size={18} style={{ color: palette.text }} />
          ) : prediction.riskBand === "warning" ? (
            <AlertTriangle size={18} style={{ color: palette.text }} />
          ) : (
            <ShieldCheck size={18} style={{ color: palette.text }} />
          )}
          <strong style={{ fontSize: "14px", color: palette.text }}>
            {aiLabelText(prediction.label)}
          </strong>
        </div>
        <Badge severity={prediction.riskBand}>{prediction.riskBand}</Badge>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }}>
        <ProbabilityMeter
          label="Xác suất té ngã"
          value={probabilityPct}
          tone={prediction.riskBand}
        />
        <ProbabilityMeter
          label="Độ tin cậy"
          value={confidencePct}
          tone={prediction.riskBand}
        />
      </div>
      {prediction.explanationSummary ? (
        <p style={{ margin: 0, fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
          {prediction.explanationSummary}
        </p>
      ) : null}
      {prediction.topFeatures.length > 0 ? (
        <div style={{ display: "grid", gap: "6px", marginTop: "4px" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Đặc trưng đóng góp lớn nhất
          </span>
          {prediction.topFeatures.map((feature, idx) => (
            <div
              key={`${feature.featureName}-${idx}`}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: "8px",
                alignItems: "center",
                padding: "6px 8px",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "var(--radius-sm)",
                borderLeft: `3px solid ${severityPalette(feature.severity).text}`,
              }}
            >
              <span style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                {feature.vietnameseExplanation || feature.featureName}
              </span>
              <code style={{ fontSize: "11px", color: severityPalette(feature.severity).text }}>
                {feature.contribution >= 0 ? "+" : ""}
                {feature.contribution.toFixed(3)}
              </code>
            </div>
          ))}
        </div>
      ) : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px",
          fontSize: "11px",
          color: "var(--text-muted)",
        }}
      >
        <span>
          Ghi nhận lúc:{" "}
          <code style={{ color: "var(--text-secondary)" }}>
            {new Date(prediction.predictedAt).toLocaleTimeString("vi-VN", { hour12: false })}
          </code>
        </span>
        {prediction.requiresAttention ? <Badge severity="warning">Cần chú ý</Badge> : null}
        {prediction.highPriorityAlert ? <Badge severity="critical">High priority</Badge> : null}
      </div>
    </div>
  );
}

function ProbabilityMeter({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "normal" | "warning" | "critical";
}) {
  const palette = severityPalette(tone);
  return (
    <div style={{ display: "grid", gap: "4px" }}>
      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{label}</span>
      <div
        style={{
          height: "8px",
          background: "var(--bg-base)",
          border: "1px solid var(--border-default)",
          borderRadius: "999px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.max(0, Math.min(100, value))}%`,
            height: "100%",
            background: palette.text,
          }}
        />
      </div>
      <strong style={{ fontFamily: "var(--font-mono)", fontSize: "13px", color: palette.text }}>
        {value}%
      </strong>
    </div>
  );
}

function CountdownBlock({
  fallState,
  disabled,
  cancelling,
  onCancel,
}: {
  fallState: FallState | null;
  disabled: boolean;
  cancelling: boolean;
  onCancel: () => void;
}) {
  if (!fallState) return null;
  const { countdownRemainingSec, countdownTotalSec, countdownPolicy } = fallState;
  const inCountdown = countdownTotalSec > 0 && fallState.deviceState === "fall_countdown";

  if (!inCountdown) {
    if (fallState.fallState === "fall_resolved" && countdownRemainingSec === 0) {
      return (
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 12px",
            fontSize: "12px",
            color: "var(--severity-normal)",
            background: "rgba(34,197,94,0.08)",
            border: "1px solid rgba(34,197,94,0.30)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <CheckCircle2 size={14} />
          BE đã ra khỏi fall_countdown — quay về streaming.
        </div>
      );
    }
    return null;
  }

  const policy = countdownPolicy;
  const percent = countdownTotalSec > 0
    ? Math.max(0, Math.min(100, (countdownRemainingSec / countdownTotalSec) * 100))
    : 0;
  const critical = countdownRemainingSec <= 10;
  const palette = severityPalette(critical ? "critical" : "warning");

  return (
    <div
      style={{
        display: "grid",
        gap: "8px",
        padding: "12px",
        background: palette.bg,
        border: `1px solid ${palette.border}`,
        borderRadius: "var(--radius-md)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontSize: "13px" }}>SOS countdown đang chạy</strong>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "13px", color: palette.text }}>
          {countdownRemainingSec} / {countdownTotalSec}s
        </span>
      </div>
      <div
        style={{
          height: "8px",
          background: "var(--bg-base)",
          borderRadius: "999px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${percent}%`,
            height: "100%",
            background: palette.text,
            transition: "width 0.4s linear",
          }}
        />
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", fontSize: "11px" }}>
        {policy?.autoResolve ? (
          <PolicyChip icon={<CheckCircle2 size={12} />} label="Sẽ tự huỷ" tone="normal" />
        ) : null}
        {policy && !policy.allowsCancel ? (
          <PolicyChip icon={<XCircle size={12} />} label="Không cho huỷ" tone="critical" />
        ) : null}
      </div>
      {policy?.allowsCancel ? (
        <Button variant="secondary" disabled={disabled} onClick={onCancel}>
          {cancelling ? "Đang gửi…" : "Tôi ổn — Hủy SOS"}
        </Button>
      ) : (
        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          Variant này không cho phép huỷ — countdown sẽ chạy đến 0.
        </span>
      )}
    </div>
  );
}

// ===========================================================================
// Motion window card
// ===========================================================================

function MotionWindowCard({
  motion,
  fallState,
}: {
  motion: MotionLatest | null;
  fallState: FallState | null;
}) {
  const [showDetails, setShowDetails] = useState(false);

  const summary = useMemo(() => {
    if (!motion || motion.accelMag.length === 0) return null;
    const peak = Math.max(...motion.accelMag);
    const mean = motion.accelMag.reduce((a, b) => a + b, 0) / motion.accelMag.length;
    return { peak, mean, count: motion.accelMag.length };
  }, [motion]);

  const variantBadge = describeFallVariant(motion?.fallVariant);
  const isFalling = motion?.activityState?.toLowerCase() === "fall";
  const heroStroke = isFalling ? "var(--severity-critical)" : "var(--accent-cyan)";

  const aiAlignedAt = fallState?.motionWindowRef?.emittedAt;
  const motionAt = motion?.emittedAt;
  const aligned = Boolean(aiAlignedAt && motionAt && aiAlignedAt === motionAt);

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <Activity size={14} />
            <strong>Cửa sổ chuyển động (50 mẫu)</strong>
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
            {variantBadge && <Badge severity="info">{variantBadge}</Badge>}
            {fallState?.aiPrediction?.modelStatus === "ok" ? (
              <Badge severity={aligned ? "normal" : "warning"}>
                {aligned ? "Cùng cửa sổ với AI" : "Cửa sổ mới (sau AI)"}
              </Badge>
            ) : null}
          </div>
        </div>
      }
    >
      {!motion || !summary ? (
        <EmptyState
          icon={Activity}
          title="Chưa có dữ liệu chuyển động"
          description="Phiên đang chạy nhưng chưa có window nào được publish cho thiết bị này."
        />
      ) : (
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "8px",
              padding: "10px 12px",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <MetricCell label="Đỉnh |a|" value={`${summary.peak.toFixed(2)} m/s²`} highlight={summary.peak >= 20} />
            <MetricCell label="Trung bình |a|" value={`${summary.mean.toFixed(2)} m/s²`} />
            <MetricCell label="Số mẫu" value={`${summary.count}`} />
            <MetricCell
              label="Tần số"
              value={motion.sampleRate ? `${motion.sampleRate} Hz` : "—"}
            />
          </div>
          <Sparkline
            values={motion.accelMag}
            stroke={heroStroke}
            height={84}
            ariaLabel="Gia tốc tổng |a| theo thời gian"
          />
          <button
            type="button"
            onClick={() => setShowDetails((s) => !s)}
            aria-expanded={showDetails}
            style={detailsToggleStyle}
          >
            <ChevronRight
              size={14}
              style={{
                transform: showDetails ? "rotate(90deg)" : "none",
                transition: "transform 200ms",
              }}
            />
            {showDetails ? "Ẩn chi tiết 6 trục" : "Hiện chi tiết 6 trục"}
          </button>
          {showDetails && (
            <div style={{ display: "grid", gap: "6px", paddingTop: "6px", borderTop: "1px dashed var(--border-default)" }}>
              <TraceRow label="Gia tốc trục X" values={motion.accelX} stroke="var(--text-secondary)" />
              <TraceRow label="Gia tốc trục Y" values={motion.accelY} stroke="var(--text-secondary)" />
              <TraceRow label="Gia tốc trục Z" values={motion.accelZ} stroke="var(--text-secondary)" />
              <TraceRow label="Vận tốc góc trục X" values={motion.gyroX} stroke="var(--severity-warning)" />
              <TraceRow label="Vận tốc góc trục Y" values={motion.gyroY} stroke="var(--severity-warning)" />
              <TraceRow label="Vận tốc góc trục Z" values={motion.gyroZ} stroke="var(--severity-warning)" />
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function MetricCell({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{label}</span>
      <strong
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "13px",
          color: highlight ? "var(--severity-critical)" : "var(--text-primary)",
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        {highlight && <AlertTriangle size={12} aria-hidden="true" />}
        {value}
      </strong>
    </div>
  );
}

function TraceRow({ label, values, stroke }: { label: string; values: number[]; stroke: string }) {
  const last = values[values.length - 1];
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "150px 1fr 70px",
        gap: "8px",
        alignItems: "center",
      }}
    >
      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{label}</span>
      <Sparkline values={values} stroke={stroke} height={22} ariaLabel={`Trace ${label}`} />
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          textAlign: "right",
          color: "var(--text-secondary)",
        }}
      >
        {last !== undefined ? last.toFixed(2) : "—"}
      </span>
    </div>
  );
}

// ===========================================================================
// Recent events card
// ===========================================================================

interface RecentEventViewModel {
  id: string;
  timestamp: string;
  deviceId: string;
  eventType: string;
  severity: string;
  message: string;
  metadata: Record<string, string>;
}

function RecentEventsCard({ events }: { events: RecentEventViewModel[] }) {
  const fallEvents = useMemo(
    () =>
      events.filter(
        (e) => e.eventType === "fall_detected" || e.eventType === "sos_cancel",
      ),
    [events],
  );

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <strong>Sự kiện gần đây ({fallEvents.length})</strong>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            BE-recorded · không invent
          </span>
        </div>
      }
    >
      {fallEvents.length === 0 ? (
        <EmptyState
          icon={Info}
          title="Chưa có sự kiện té ngã"
          description="Các fall_detected / sos_cancel cho thiết bị này sẽ xuất hiện ở đây."
        />
      ) : (
        <div style={{ display: "grid", gap: "6px" }}>
          {fallEvents.map((event) => (
            <FallEventRow key={event.id} event={event} />
          ))}
        </div>
      )}
    </Card>
  );
}

function FallEventRow({ event }: { event: RecentEventViewModel }) {
  const variant = event.metadata.variant || null;
  const variantLabel = variant ? describeFallVariant(variant) ?? variant : null;
  const aiLabel = event.metadata.ai_label ?? null;
  const aiBand = event.metadata.ai_band ?? null;
  const aiProbability = event.metadata.ai_probability;
  const aiStatus = event.metadata.ai_status ?? null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "100px 130px 1fr auto",
        gap: "8px",
        alignItems: "center",
        padding: "6px 10px",
        borderRadius: "var(--radius-sm)",
        background: severityRowBackground(event.severity),
        borderLeft: `3px solid ${severityRowColor(event.severity)}`,
      }}
    >
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-muted)" }}>
        {new Date(event.timestamp).toLocaleTimeString("vi-VN", { hour12: false })}
      </span>
      <span style={{ fontSize: "12px" }}>
        {event.eventType === "fall_detected" ? "🔴 Fall detected" : "🟢 SOS cancelled"}
      </span>
      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
        {variantLabel ? <code>{variantLabel}</code> : event.message}
      </span>
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", justifyContent: "flex-end" }}>
        {aiLabel ? (
          <Badge
            severity={aiBand === "critical" ? "critical" : aiBand === "warning" ? "warning" : "normal"}
          >
            AI: {aiLabelText(aiLabel as AIPredictionLabel)}
            {aiProbability ? ` · ${Math.round(parseFloat(aiProbability) * 100)}%` : ""}
          </Badge>
        ) : null}
        {aiStatus && aiStatus !== "ok" ? <Badge severity="offline">{aiStatusLabel(aiStatus)}</Badge> : null}
      </div>
    </div>
  );
}

// ===========================================================================
// Helpers
// ===========================================================================

function aiLabelText(label: AIPredictionLabel | string): string {
  switch (label) {
    case "normal":
      return "Bình thường";
    case "possible_fall":
      return "Có thể té ngã";
    case "likely_fall":
      return "Khả năng té ngã cao";
    case "critical_fall":
      return "Té ngã nghiêm trọng";
    default:
      return String(label);
  }
}

function aiStatusLabel(status: string): string {
  switch (status) {
    case "offline":
      return "AI offline";
    case "no_window":
      return "Không đủ mẫu";
    case "skipped":
      return "Bỏ qua AI";
    case "ok":
      return "AI sẵn sàng";
    default:
      return status;
  }
}

function severityShortLabel(severity: "normal" | "warning" | "critical"): string {
  if (severity === "critical") return "critical";
  if (severity === "warning") return "warning";
  return "safe";
}

function severityPalette(severity: "normal" | "warning" | "critical" | "offline"): {
  bg: string;
  text: string;
  border: string;
} {
  switch (severity) {
    case "critical":
      return {
        bg: "rgba(220,38,38,0.10)",
        text: "var(--severity-critical)",
        border: "rgba(239,68,68,0.35)",
      };
    case "warning":
      return {
        bg: "rgba(217,119,6,0.10)",
        text: "var(--severity-warning)",
        border: "rgba(245,158,11,0.35)",
      };
    case "offline":
      return {
        bg: "rgba(75,85,99,0.10)",
        text: "var(--text-muted)",
        border: "rgba(107,114,128,0.35)",
      };
    case "normal":
    default:
      return {
        bg: "rgba(34,197,94,0.10)",
        text: "var(--severity-normal)",
        border: "rgba(34,197,94,0.30)",
      };
  }
}

function severityRowBackground(sev: string): string {
  if (sev === "critical") return "rgba(239,68,68,0.06)";
  if (sev === "warning") return "rgba(245,158,11,0.06)";
  return "rgba(255,255,255,0.02)";
}

function severityRowColor(sev: string): string {
  if (sev === "critical") return "var(--severity-critical)";
  if (sev === "warning") return "var(--severity-warning)";
  return "var(--border-default)";
}

// ===========================================================================
// Styles
// ===========================================================================

const selectStyle: CSSProperties = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "6px 10px",
  minWidth: "200px",
};

const emptyVerdictStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  padding: "10px 12px",
  background: "var(--bg-elevated)",
  border: "1px dashed var(--border-default)",
  borderRadius: "var(--radius-md)",
};

const detailsToggleStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  alignSelf: "flex-start",
  padding: "6px 10px",
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--border-default)",
  background: "transparent",
  color: "var(--text-secondary)",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 500,
};

// Avoid TS unused-import warnings for type-only imports above.
export type { FallEventEntry, CountdownPolicy };
