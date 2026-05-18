import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { DevicePicker } from "../components/domain/session/DevicePicker";
import { ScenarioSelector } from "../components/domain/session/ScenarioSelector";
import { UserProfileCard } from "../components/domain/session/UserProfileCard";
import { SessionVitalsPanel } from "../components/domain/SessionVitalsPanel";
import { PageHeader } from "../components/ui/PageHeader";
import { SequenceDiagramLive } from "../components/sequence_diagram/SequenceDiagramLive";

import { useDbDevices, useDevices } from "../hooks/useDevices";
import { useSessions } from "../hooks/useSessions";
import { useUserProfile } from "../hooks/useUserProfile";
import { applyScenarioPreset, fetchScenarios } from "../services/scenarioApi";

import { useSessionStore } from "../stores/sessionStore";
import { runWithToast } from "../utils/toast";
import { useConfirm } from "../hooks/useConfirm";

// ---------------------------------------------------------------------------
// SessionRunnerPage — redesigned per "device-first" UX (May 2026).
//
// Flow:
//   1. Operator picks a device card from DevicePicker.  We use DbDevice
//      as the source of truth (filtered to `is_sim_running === true`)
//      because that's where user-binding + medical data lives.
//   2. UserProfileCard fetches `/admin/users/{user_id}/profile` and
//      renders avatar (Supabase public URL) + demographics + medical
//      info + emergency contacts.
//   3. ScenarioSelector + SessionVitalsPanel give per-device control:
//      pick a non-fall scenario via dropdown or open the library modal.
//
// Fall scenarios still live on `/fall-lab`; selecting one from the
// library modal navigates there with the chosen device pre-selected.
// ---------------------------------------------------------------------------

export function SessionRunnerPage() {
  const [searchParams] = useSearchParams();
  const preselectedDeviceParam = searchParams.get("deviceId") ?? searchParams.get("device");

  // DB device list (carries user_id, demographics, is_sim_running).
  // Polled at the dbDevices default interval so SIM-on/off updates flow
  // through without a manual refresh.
  const { data: dbDevices = [] } = useDbDevices();

  // Sim runtime devices — still needed to map a DB device id (number) to
  // the simulator-side string id used by /scenarios/apply and the
  // vitals/motion endpoints.
  const { data: simDevices = [] } = useDevices(2000);

  const { data: sessions = [] } = useSessions();
  const { data: scenarios = [] } = useQuery({
    queryKey: ["scenarios"],
    queryFn: fetchScenarios,
    staleTime: 60_000,
  });

  const [selectedDbDeviceId, setSelectedDbDeviceId] = useState<number | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [isApplying, setIsApplying] = useState(false);

  const { activeSessionId } = useSessionStore();
  const [confirm, confirmDialog] = useConfirm();

  const activeDbDevices = useMemo(
    () => dbDevices.filter((device) => device.is_sim_running),
    [dbDevices]
  );

  const defaultScenarioId = useMemo(
    () => scenarios.find((scenario) => scenario.category !== "fall")?.id ?? scenarios[0]?.id ?? "",
    [scenarios]
  );

  // Map a DB device id (FE state) to the simulator's string id (BE API).
  const selectedSimDevice = useMemo(
    () =>
      selectedDbDeviceId == null
        ? null
        : simDevices.find((device) => device.boundDbDeviceId === selectedDbDeviceId) ?? null,
    [selectedDbDeviceId, simDevices]
  );

  const selectedDbDevice = useMemo(
    () => activeDbDevices.find((device) => device.id === selectedDbDeviceId) ?? null,
    [activeDbDevices, selectedDbDeviceId]
  );

  // User profile is fetched on-demand once a device is picked.  We pass
  // null when the device has no bound user so the hook stays disabled.
  const {
    data: userProfile,
    isFetching: isProfileFetching,
    error: profileError,
  } = useUserProfile(selectedDbDevice?.user_id ?? null);

  // Auto-select on first load: URL param if present, otherwise first
  // available device.  Runs only when nothing is selected yet — picking
  // manually later doesn't get clobbered.
  useEffect(() => {
    if (selectedDbDeviceId != null || activeDbDevices.length === 0) return;
    const preselectedId = Number(preselectedDeviceParam);
    const fromUrl = !Number.isNaN(preselectedId)
      ? activeDbDevices.find((device) => device.id === preselectedId)
      : null;
    setSelectedDbDeviceId((fromUrl ?? activeDbDevices[0]).id);
  }, [activeDbDevices, preselectedDeviceParam, selectedDbDeviceId]);

  // When the device list changes (e.g. operator stops SIM elsewhere),
  // drop the selection if it no longer exists.
  useEffect(() => {
    if (selectedDbDeviceId == null) return;
    if (!activeDbDevices.some((device) => device.id === selectedDbDeviceId)) {
      setSelectedDbDeviceId(activeDbDevices[0]?.id ?? null);
    }
  }, [activeDbDevices, selectedDbDeviceId]);

  // Mirror BE's current scenario into local state when the selection
  // changes — so a freshly-picked device shows what's actually running.
  useEffect(() => {
    if (!selectedSimDevice) {
      setSelectedScenarioId("");
      return;
    }
    const beScenarioId = selectedSimDevice.currentScenarioId ?? null;
    const matched = scenarios.find(
      (scenario) => scenario.id === beScenarioId && scenario.category !== "fall"
    );
    setSelectedScenarioId(matched?.id ?? defaultScenarioId);
  }, [selectedSimDevice, scenarios, defaultScenarioId]);

  const activeSession = useMemo(
    () =>
      sessions.find((session) => session.id === activeSessionId)
      ?? sessions.find((session) => session.status === "running")
      ?? null,
    [activeSessionId, sessions]
  );

  // Apply a scenario to the currently-selected device.  Mirrors the
  // previous changeScenario() with one key simplification: only one
  // device at a time, so the optimistic state is a single string, not
  // a Record.
  const applyScenario = useCallback(
    async (scenarioId: string) => {
      if (!selectedSimDevice) return;
      const scenario = scenarios.find((item) => item.id === scenarioId) ?? null;
      const previousScenarioId = selectedScenarioId;

      if (activeSession?.status === "running" && scenario?.severity === "critical") {
        const ok = await confirm({
          severity: "critical",
          title: `Áp dụng kịch bản "${scenario.name}"?`,
          description: `Kịch bản này được đánh dấu nguy cấp và sẽ kích hoạt side-effect: ${
            scenario.followUp.map((f) => f.detail).join(", ") || "không có side-effect bổ sung"
          }. Có chắc chắn không?`,
          confirmLabel: "Áp dụng",
        });
        if (!ok) return;
      }

      setSelectedScenarioId(scenarioId);
      if (activeSession?.status !== "running") return;

      setIsApplying(true);
      try {
        await runWithToast(applyScenarioPreset(selectedSimDevice.id, scenarioId), {
          loading: `Đang áp dụng kịch bản "${scenario?.name ?? scenarioId}"…`,
          success: `Đã áp dụng "${scenario?.name ?? scenarioId}" cho thiết bị đang chạy.`,
          error: "Không áp dụng được kịch bản cho thiết bị này.",
        });
      } catch {
        // Rollback to previous on failure — runWithToast already showed
        // the error toast.
        if (previousScenarioId) {
          setSelectedScenarioId(previousScenarioId);
        }
      } finally {
        setIsApplying(false);
      }
    },
    [activeSession?.status, confirm, scenarios, selectedScenarioId, selectedSimDevice]
  );

  // Empty state — no device has SIM running.
  if (activeDbDevices.length === 0) {
    return (
      <section className="page-section">
        <PageHeader
          title="Mô phỏng tín hiệu sinh tồn"
          subtitle="Chọn thiết bị, xem hồ sơ người dùng, sau đó áp dụng kịch bản và quan sát sinh hiệu thời gian thực."
        />
        <div
          style={{
            placeItems: "center",
            minHeight: "40vh",
            opacity: 0.8,
            display: "grid",
          }}
        >
          <div style={{ textAlign: "center", display: "grid", gap: "8px" }}>
            <h2 style={{ color: "var(--text-primary)", fontSize: "1.1rem" }}>
              Chưa có thiết bị nào được bật SIM
            </h2>
            <p
              style={{
                color: "var(--text-secondary)",
                fontSize: "0.9rem",
                maxWidth: "440px",
                lineHeight: 1.5,
              }}
            >
              Bạn cần sang tab <strong>Thiết bị</strong> và <strong>Bật SIM</strong> cho ít nhất một thiết bị. Sau đó quay lại đây để chọn và mô phỏng.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="page-section">
      <PageHeader
        title="Mô phỏng tín hiệu sinh tồn"
        subtitle="Chọn thiết bị, xem hồ sơ người dùng, sau đó áp dụng kịch bản và quan sát sinh hiệu thời gian thực."
      />

      {/* Section 1 — Device picker */}
      <div style={{ display: "grid", gap: "8px" }}>
        <SectionHeading label="1. Chọn thiết bị" />
        <DevicePicker
          devices={activeDbDevices}
          selectedDeviceId={selectedDbDeviceId}
          onSelect={setSelectedDbDeviceId}
        />
      </div>

      {/* Section 2 — Profile (only after a device is selected) */}
      {selectedDbDeviceId != null ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <SectionHeading label="2. Hồ sơ người dùng" />
          {selectedDbDevice?.user_id != null ? (
            <UserProfileCard
              profile={userProfile}
              isLoading={isProfileFetching && !userProfile}
              error={profileError as Error | null}
            />
          ) : (
            <UserProfileCard profile={undefined} isLoading={false} error={null} />
          )}
        </div>
      ) : null}

      {/* Section 3 — Scenario + Vitals (only after a device is selected) */}
      {selectedSimDevice ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <SectionHeading label="3. Mô phỏng & sinh hiệu" />
          <ScenarioSelector
            scenarios={scenarios}
            selectedScenarioId={selectedScenarioId}
            onChange={(scenarioId) => void applyScenario(scenarioId)}
            isApplying={isApplying}
            disabled={!selectedSimDevice}
          />
          <SessionVitalsPanel
            devices={[selectedSimDevice]}
            deviceId={selectedSimDevice.id}
            runtimeTickAt={
              sessions.find(
                (session) => session.status === "running" && session.deviceIds.includes(selectedSimDevice.id)
              )?.lastTickAt
              ?? sessions.find(
                (session) => session.id === activeSessionId && session.deviceIds.includes(selectedSimDevice.id)
              )?.lastTickAt
              ?? null
            }
            onDeviceChange={() => {
              /* page-level picker owns device selection; vitals dropdown disabled */
            }}
          />
        </div>
      ) : null}

      {/* Section 4 — Live sequence diagram (only when session is running) */}
      {activeSession ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <SectionHeading label="4. Flow Events — Sequence Diagram" />
          <SequenceDiagramLive sessionId={activeSession.id} />
        </div>
      ) : null}

      {confirmDialog}
    </section>
  );
}

// ---------------------------------------------------------------------------
// SectionHeading — small uppercase label between page sections.  Inline
// here because it's only used inside this page and matches the section
// hierarchy elsewhere (DashboardPage, DevicesPage).
// ---------------------------------------------------------------------------

function SectionHeading({ label }: { label: string }) {
  return (
    <div
      style={{
        fontSize: "11px",
        fontWeight: 700,
        color: "var(--text-muted)",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
      }}
    >
      {label}
    </div>
  );
}
