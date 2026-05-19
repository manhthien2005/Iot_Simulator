import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Activity } from "lucide-react";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { DeviceSessionBar } from "../components/domain/fall-lab/DeviceSessionBar";
import { VariantPickerCard } from "../components/domain/fall-lab/VariantPickerCard";
import { AIVerdictPanel } from "../components/domain/fall-lab/AIVerdictPanel";
import { MotionWindowCard } from "../components/domain/fall-lab/MotionWindowCard";
import { RecentEventsCard } from "../components/domain/fall-lab/RecentEventsCard";
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

  const guardDisabled =
    !activeSession
    || !focusDeviceId
    || activeSession.status !== "running"
    || !!pendingVariant
    || cancelling;

  async function handleInjectVariant(variant: FallVariantSpec) {
    if (guardDisabled) return;
    // Note: pre-inject confirm dialog deliberately removed for variant `critical`
    // — production mobile flow has no confirm step, so a 1-3s operator-side
    // pause inflates end-to-end latency measurements.  Operators get a clear
    // toast (loading / success / error) and can rely on the SOS countdown +
    // "Tôi ổn" cancel button to abort an injected fall.  The cancel path is
    // kept because the production mobile UI also has it (parity preserved).
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
    <section className="page-section">
      <PageHeader
        title="Phòng thí nghiệm té ngã"
        subtitle="Inject các kịch bản té ngã, theo dõi verdict của AI (healthguard-model-api) và xác minh BE escalation tương ứng. Tất cả số liệu (verdict, countdown, motion window) đều derive từ BE — FE không invent dữ liệu."
      />

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
    </section>
  );
}

// Re-export types consumed downstream (e.g. SessionRunnerPage).
export type { FallEventEntry, CountdownPolicy };
