import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DeviceAssignPanel } from "../components/domain/DeviceAssignPanel";
import { FallLab } from "../components/domain/FallLab";
import { MotionPreviewPanel } from "../components/domain/MotionPreviewPanel";
import { SessionVitalsPanel } from "../components/domain/SessionVitalsPanel";

import { useDevices } from "../hooks/useDevices";
import { useSessions } from "../hooks/useSessions";
import { applyScenarioPreset, fetchScenarios } from "../services/scenarioApi";

import { useSessionVitalsStore } from "../stores/sessionVitalsStore";
import { useSessionStore } from "../stores/sessionStore";
import type { VitalsSample } from "../types/vitals";
import { notify } from "../utils/toast";

export function SessionRunnerPage() {
  const [searchParams] = useSearchParams();
  const preselectedDeviceId = searchParams.get("deviceId") ?? searchParams.get("device");
  const preselectedScenarioId = searchParams.get("scenario");
  const { data: devices = [] } = useDevices(2000);
  const { data: sessions = [], refetch: refetchSessions } = useSessions();
  const { data: scenarios = [] } = useQuery({
    queryKey: ["scenarios"],
    queryFn: fetchScenarios,
    staleTime: 60_000,
  });
  const [scenarioByDevice, setScenarioByDevice] = useState<Record<string, string>>({});
  const [monitorDeviceId, setMonitorDeviceId] = useState<string>("");

  const { activeSessionId, setActiveSession, streamSpeed, setSpeed, isPaused, setPaused } = useSessionStore();

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
      (preselectedDeviceId && devices.some((device) => device.id === preselectedDeviceId) ? preselectedDeviceId : null)
      ?? devices[0].id;
    setMonitorDeviceId(fallback);
  }, [devices, monitorDeviceId, preselectedDeviceId]);

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

  // Removing obsolete start/stop logic since sessions are managed per device from the DevicesPage

  const changeScenario = useCallback(async (deviceId: string, scenarioId: string) => {
    setScenarioByDevice((prev) => ({ ...prev, [deviceId]: scenarioId }));
    if (activeSession?.status !== "running") return;
    try {
      await applyScenarioPreset(deviceId, scenarioId);
      notify.success("Đã áp dụng kịch bản cho thiết bị đang chạy.");
    } catch {
      notify.error("Không áp dụng được kịch bản cho thiết bị này.");
    }
  }, [activeSession?.status]);

  const activeDevices = useMemo(() => devices.filter((d) => d.isOnline), [devices]);

  if (!activeDevices.length) {
    return (
      <section style={{ display: "grid", gap: "14px", placeItems: "center", minHeight: "60vh", opacity: 0.8 }}>
        <div style={{ textAlign: "center", display: "grid", gap: "8px" }}>
          <h2 style={{ color: "var(--text-primary)", fontSize: "1.2rem" }}>Chưa có thiết bị nào được bật SIM</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", maxWidth: "400px", lineHeight: 1.5 }}>
            Bạn cần sang tab <strong>Thiết bị</strong> và chọn <strong>Bật SIM</strong> cho thiết bị muốn mô phỏng. Sau đó, danh sách sẽ hiển thị tại đây để bạn điều khiển kịch bản.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div>
        <h1 className="page-title">Phiên mô phỏng</h1>
        <p className="page-subtitle">Điều khiển trạng thái phiên, gán kịch bản và chạy té ngã cho các thiết bị đang bật SIM.</p>
      </div>

      <DeviceAssignPanel
        devices={activeDevices}
        scenarios={scenarios}
        scenarioByDevice={scenarioByDevice}
        onScenarioChange={changeScenario}
      />

      <SessionVitalsPanel devices={activeDevices} deviceId={monitorDeviceId} onDeviceChange={setMonitorDeviceId} />

      <FallLab devices={activeDevices} />
      <MotionPreviewPanel selectedDevice={activeDevices.find((item) => item.id === monitorDeviceId) ?? null} currentVitals={currentVitals} />
    </section>
  );
}
