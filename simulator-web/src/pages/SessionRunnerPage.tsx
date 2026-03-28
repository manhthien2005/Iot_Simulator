import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DeviceAssignPanel } from "../components/domain/DeviceAssignPanel";
import { FallLab } from "../components/domain/FallLab";
import { MotionPreviewPanel } from "../components/domain/MotionPreviewPanel";
import { SessionVitalsPanel } from "../components/domain/SessionVitalsPanel";
import { SessionToolbar } from "../components/domain/SessionToolbar";
import { useDevices } from "../hooks/useDevices";
import { useSessions } from "../hooks/useSessions";
import { applyScenarioPreset, fetchScenarios } from "../services/scenarioApi";
import { createSession, startSession, stopSession } from "../services/sessionApi";
import { useSessionVitalsStore } from "../stores/sessionVitalsStore";
import { useSessionStore } from "../stores/sessionStore";
import type { ScenarioOption } from "../types/scenario";
import type { VitalsSample } from "../types/vitals";
import { notify } from "../utils/toast";

export function SessionRunnerPage() {
  const [searchParams] = useSearchParams();
  const preselectedDeviceId = searchParams.get("deviceId") ?? searchParams.get("device");
  const preselectedScenarioId = searchParams.get("scenario");
  const { data: devices = [] } = useDevices(1000);
  const { data: sessions = [], refetch: refetchSessions } = useSessions();
  const [scenarios, setScenarios] = useState<ScenarioOption[]>([]);
  const [scenarioByDevice, setScenarioByDevice] = useState<Record<string, string>>({});
  const [monitorDeviceId, setMonitorDeviceId] = useState<string>("");

  const { activeSessionId, setActiveSession, selectedDeviceIds, toggleDeviceSelection, setSelectedDeviceIds, streamSpeed, setSpeed, isPaused, setPaused } = useSessionStore();

  useEffect(() => {
    fetchScenarios().then(setScenarios).catch(() => setScenarios([]));
  }, []);

  const defaultScenarioId = useMemo(
    () => scenarios.find((scenario) => scenario.category !== "fall")?.id ?? scenarios[0]?.id ?? "normal_rest",
    [scenarios]
  );

  const normalizeScenarioId = (scenarioId?: string | null) => {
    if (!scenarioId) return defaultScenarioId;
    const scenario = scenarios.find((item) => item.id === scenarioId);
    if (!scenario || scenario.category === "fall") {
      return defaultScenarioId;
    }
    return scenario.id;
  };

  useEffect(() => {
    const validIds = selectedDeviceIds.filter((id) => devices.some((device) => device.id === id));
    if (validIds.length !== selectedDeviceIds.length) {
      setSelectedDeviceIds(validIds);
      return;
    }

    if (!devices.length) {
      if (selectedDeviceIds.length > 0) {
        setSelectedDeviceIds([]);
      }
      return;
    }

    if (preselectedDeviceId && devices.some((device) => device.id === preselectedDeviceId) && !selectedDeviceIds.includes(preselectedDeviceId)) {
      setSelectedDeviceIds([preselectedDeviceId, ...selectedDeviceIds]);
      return;
    }

    if (!preselectedDeviceId && selectedDeviceIds.length === 0) {
      setSelectedDeviceIds([devices[0].id]);
    }
  }, [devices, preselectedDeviceId, selectedDeviceIds, setSelectedDeviceIds]);

  useEffect(() => {
    if (!preselectedDeviceId || !preselectedScenarioId) return;
    setScenarioByDevice((prev) => ({
      ...prev,
      [preselectedDeviceId]: normalizeScenarioId(preselectedScenarioId),
    }));
  }, [defaultScenarioId, preselectedDeviceId, preselectedScenarioId, scenarios]);

  useEffect(() => {
    if (!devices.length) {
      setMonitorDeviceId("");
      return;
    }
    const validCurrent = monitorDeviceId && devices.some((device) => device.id === monitorDeviceId);
    if (validCurrent) return;

    const fallback =
      selectedDeviceIds.find((id) => devices.some((device) => device.id === id))
      ?? (preselectedDeviceId && devices.some((device) => device.id === preselectedDeviceId) ? preselectedDeviceId : null)
      ?? devices[0].id;
    setMonitorDeviceId(fallback);
  }, [devices, monitorDeviceId, preselectedDeviceId, selectedDeviceIds]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? sessions.find((session) => session.status === "running") ?? null,
    [activeSessionId, sessions]
  );
  const running = activeSession?.status === "running" && !isPaused;
  const currentVitals = useSessionVitalsStore((state) => {
    if (state.activeDeviceId !== monitorDeviceId) {
      return null;
    }
    return state.streamData[state.streamData.length - 1] ?? null;
  }) as VitalsSample | null;

  const start = async () => {
    const target = selectedDeviceIds.length
      ? selectedDeviceIds.filter((id) => devices.some((device) => device.id === id))
      : [monitorDeviceId || devices[0]?.id].filter(Boolean) as string[];
    if (!target.length) {
      notify.error("Hãy thêm ít nhất một thiết bị trước khi chạy.");
      return;
    }
    const created = await createSession(target, streamSpeed);

    const applyResults = await Promise.allSettled(
      target.map((deviceId) => {
        const selectedScenarioId = normalizeScenarioId(
          scenarioByDevice[deviceId]
          ?? (deviceId === preselectedDeviceId ? preselectedScenarioId : undefined)
          ?? defaultScenarioId
        );
        return applyScenarioPreset(deviceId, selectedScenarioId);
      })
    );
    const failedCount = applyResults.filter((result) => result.status === "rejected").length;
    if (failedCount > 0) {
      notify.warning("Một số kịch bản chưa áp dụng được đầy đủ.");
    }

    setActiveSession(created.id);
    await startSession(created.id);
    setPaused(false);
    await refetchSessions();
    notify.success("Đã bắt đầu phiên mô phỏng");
  };

  const stop = async () => {
    if (!activeSession) return;
    await stopSession(activeSession.id);
    setPaused(false);
    setActiveSession(null);
    await refetchSessions();
    notify.success("Đã dừng phiên mô phỏng");
  };

  const changeScenario = async (deviceId: string, scenarioId: string) => {
    setScenarioByDevice((prev) => ({ ...prev, [deviceId]: scenarioId }));
    if (activeSession?.status !== "running") return;
    try {
      await applyScenarioPreset(deviceId, scenarioId);
      notify.success("Đã áp dụng kịch bản cho thiết bị đang chạy.");
    } catch {
      notify.error("Không áp dụng được kịch bản cho thiết bị này.");
    }
  };

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div>
        <h1 className="page-title">Phiên mô phỏng</h1>
        <p className="page-subtitle">Điều khiển trạng thái phiên, gán kịch bản theo thiết bị và chạy mô phỏng té ngã.</p>
      </div>

      <SessionToolbar
        hasSession={Boolean(devices.length)}
        running={running}
        paused={isPaused}
        sessionId={activeSession?.id ?? null}
        speed={streamSpeed}
        onStart={start}
        onStop={stop}
        onPause={() => setPaused(true)}
        onResume={() => setPaused(false)}
        onSpeedChange={setSpeed}
      />

      <DeviceAssignPanel
        devices={devices}
        scenarios={scenarios}
        scenarioByDevice={scenarioByDevice}
        selectedDeviceIds={selectedDeviceIds}
        onToggleDevice={toggleDeviceSelection}
        onScenarioChange={changeScenario}
      />

      <SessionVitalsPanel devices={devices} deviceId={monitorDeviceId} onDeviceChange={setMonitorDeviceId} />

      <FallLab devices={devices} />
      <MotionPreviewPanel selectedDevice={devices.find((item) => item.id === monitorDeviceId) ?? null} currentVitals={currentVitals} />
    </section>
  );
}
