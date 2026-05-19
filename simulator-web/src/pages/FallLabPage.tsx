import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Activity, Info } from "lucide-react";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { DeviceSessionBar } from "../components/domain/fall-lab/DeviceSessionBar";
import { ScenarioMatrixCard } from "../components/domain/fall-lab/ScenarioMatrixCard";
import { AIVerdictPanel } from "../components/domain/fall-lab/AIVerdictPanel";
import { AIPipelineStrip } from "../components/domain/fall-lab/AIPipelineStrip";
import { MotionWindowDetailCard } from "../components/domain/fall-lab/MotionWindowDetailCard";
import { VitalsAfterFallCard } from "../components/domain/fall-lab/VitalsAfterFallCard";
import { FallEventsTimelineCard } from "../components/domain/fall-lab/FallEventsTimelineCard";
import { FailureReasonBanner } from "../components/domain/fall-lab/FailureReasonBanner";
import { useDevices } from "../hooks/useDevices";
import { useSessions } from "../hooks/useSessions";
import { useFallState } from "../hooks/useFallState";
import { useLatestMotion } from "../hooks/useLatestMotion";
import { useRecentEvents } from "../hooks/useRecentEvents";
import { injectFallEvent, injectSosCancel } from "../services/eventApi";
import { useSessionStore } from "../stores/sessionStore";
import { runWithToast } from "../utils/toast";
import { POLL_INTERVALS, FALL_LAB_RECENT_EVENTS_LIMIT } from "../config/defaults";
import {
  FALL_VARIANT_CATALOGUE,
  type FallEventEntry,
  type CountdownPolicy,
  type FallVariantId,
  type FallVariantSpec,
} from "../types/fall";

// ---------------------------------------------------------------------------
// FallLabPage — Module FA Phase 1 redesigned layout (6 sections).
//
//   A. KỊCH BẢN          — bảng so sánh 6 variants + evidence checklist
//   B. QUY TRÌNH AI      — 4-stage pipeline (window → pre-trigger → API → verdict)
//   C. CỬA SỔ 50 MẪU     — accelMag với threshold lines + peak marker + sub-traces
//   D. BIẾN THIÊN VITALS — HR/SpO2/BP/RR ±60s quanh fall, pre/post 30s baseline
//   E. AI VERDICT        — band + probability + confidence + SHAP top 3 + countdown
//   F. LỊCH SỬ           — events grouped by session, expand snapshot, compare 2
//
// Pre-inject confirm dialog removed: production mobile flow has no confirm
// step, so the 1-3s operator pause inflated end-to-end latency measurements
// during research.  SOS cancel ("Tôi ổn") kept because production mobile UI
// has the same button.  All numeric expectations come from
// `FALL_VARIANT_CATALOGUE` which mirrors the BE pre-trigger thresholds and
// `simulator_core.fall_ai_client.FALL_VARIANT_CONTEXT`.
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

  const guardDisabled =
    !activeSession
    || !focusDeviceId
    || activeSession.status !== "running"
    || !!pendingVariant
    || cancelling;

  async function handleInjectVariant(variant: FallVariantSpec) {
    if (guardDisabled) return;
    // Pre-inject confirm dialog removed deliberately — production mobile
    // flow has no confirm step, so a 1-3s operator-side pause inflates
    // end-to-end latency measurements during research.  Toast loading +
    // SOS countdown + "Tôi ổn" cancel are enough.
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

  // Derive motion peak |a| (used by AIPipelineStrip stage 2 — replaced by
  // BE evidence in Phase 2 once `FallState.preTriggerResult` lands).
  const motionPeakG = useMemo(() => {
    if (!motion || motion.accelMag.length === 0) return null;
    return Math.max(...motion.accelMag);
  }, [motion]);

  const noSession = !activeSession || activeSession.status !== "running";

  return (
    <section className="page-section">
      <PageHeader
        title="Phòng nghiên cứu té ngã"
        subtitle="Inject các kịch bản té ngã, theo dõi quy trình AI đánh giá (pre-trigger → model API → verdict), quan sát biến thiên sinh hiệu sau té ngã và xác minh BE escalation tương ứng. Mọi số liệu đều derive từ BE — không invent dữ liệu."
      />

      <LatencyDisclaimer />

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

      {noSession ? (
        <Card>
          <EmptyState
            icon={Activity}
            title="Chưa có phiên đang chạy"
            description="Bật một phiên ở tab 'Mô phỏng sinh tồn' và đảm bảo có thiết bị đang online để bắt đầu inject té ngã."
          />
        </Card>
      ) : (
        <>
          <SectionLabel>A · Kịch bản té ngã</SectionLabel>
          <ScenarioMatrixCard
            disabled={guardDisabled}
            pendingVariant={pendingVariant}
            onPick={handleInjectVariant}
            onHover={setHoveredVariant}
            focalVariant={focalVariantSpec}
          />

          <SectionLabel>B · Quy trình AI đánh giá</SectionLabel>
          <AIPipelineStrip
            fallState={fallState ?? null}
            motionPeakG={motionPeakG}
            motionSampleCount={motion?.accelMag.length ?? null}
            motionSampleRate={motion?.sampleRate ?? null}
            expectedVariant={focalVariantSpec}
          />

          <SectionLabel>C · Cửa sổ chuyển động 50 mẫu</SectionLabel>
          <MotionWindowDetailCard motion={motion ?? null} fallState={fallState ?? null} />

          <SectionLabel>D · Biến thiên sinh hiệu sau té ngã</SectionLabel>
          <VitalsAfterFallCard
            deviceId={focusDeviceId || null}
            lastFallEventAt={fallState?.lastFallEventAt ?? null}
          />

          <SectionLabel>E · AI verdict + countdown SOS</SectionLabel>
          <FailureReasonBanner prediction={fallState?.aiPrediction ?? null} />
          <AIVerdictPanel
            fallState={fallState ?? null}
            disabled={guardDisabled}
            onCancel={handleCancel}
            cancelling={cancelling}
          />

          <SectionLabel>F · Lịch sử sự kiện té ngã</SectionLabel>
          <FallEventsTimelineCard events={recentEvents} />
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Inline helpers (small, page-local only).
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: string }) {
  return (
    <div
      style={{
        fontSize: "11px",
        fontWeight: 700,
        color: "var(--text-muted)",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        marginTop: "4px",
      }}
    >
      {children}
    </div>
  );
}

function LatencyDisclaimer() {
  return (
    <Card padding="sm">
      <div style={{ display: "flex", gap: "10px", alignItems: "flex-start", borderLeft: "3px solid var(--severity-info)", paddingLeft: "10px" }}>
        <Info size={16} style={{ color: "var(--severity-info)", flexShrink: 0, marginTop: "1px" }} />
        <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.55 }}>
          <strong style={{ color: "var(--severity-info)" }}>Lưu ý độ trễ trong giả lập:</strong>{" "}
          Trên simulator, <code>inject_event</code> chạy đồng bộ tới Model API (port 8001) và trả verdict trong <strong>~50–200ms</strong>.
          Trên mobile thực, độ trễ end-to-end là <strong>1–3s</strong> (MQTT → BE buffer → model API → push notif).
          Pre-inject confirm dialog đã được loại bỏ (gây delay không tồn tại trong production flow).
          Hủy SOS bằng nút "Tôi ổn" giữ nguyên — vì mobile production cũng có nút này.
        </div>
      </div>
    </Card>
  );
}

// Re-export types consumed downstream (e.g. SessionRunnerPage).
export type { FallEventEntry, CountdownPolicy };
