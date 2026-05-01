import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DeviceAssignPanel } from "../components/domain/DeviceAssignPanel";
import { SessionVitalsPanel } from "../components/domain/SessionVitalsPanel";

import { useDevices } from "../hooks/useDevices";
import { useSessions } from "../hooks/useSessions";
import { applyScenarioPreset, fetchScenarios } from "../services/scenarioApi";

import { useSessionStore } from "../stores/sessionStore";
import { runWithToast } from "../utils/toast";
import { useConfirm } from "../hooks/useConfirm";

export function SessionRunnerPage() {
  const [searchParams] = useSearchParams();
  const preselectedDeviceId = searchParams.get("deviceId") ?? searchParams.get("device");
  const preselectedScenarioId = searchParams.get("scenario");
  const { data: devices = [] } = useDevices(2000);
  const { data: sessions = [] } = useSessions();
  const { data: scenarios = [] } = useQuery({
    queryKey: ["scenarios"],
    queryFn: fetchScenarios,
    staleTime: 60_000,
  });
  const [scenarioByDevice, setScenarioByDevice] = useState<Record<string, string>>({});
  const [monitorDeviceId, setMonitorDeviceId] = useState<string>("");

  const { activeSessionId, setActiveSession } = useSessionStore();

  const defaultScenarioId = useMemo(
    () => scenarios.find((scenario) => scenario.category !== "fall")?.id ?? scenarios[0]?.id ?? "normal_rest",
    [scenarios]
  );

  const normalizeScenarioId = useCallback((scenarioId?: string | null) => {
    if (!scenarioId) return defaultScenarioId;
    const scenario = scenarios.find((item) => item.id === scenarioId);
    if (!scenario || scenario.category === "fall") {
      return defaultScenarioId;
    }
    return scenario.id;
  }, [scenarios, defaultScenarioId]);

  useEffect(() => {
    if (!preselectedDeviceId || !preselectedScenarioId) return;
    setScenarioByDevice((prev) => ({
      ...prev,
      [preselectedDeviceId]: normalizeScenarioId(preselectedScenarioId),
    }));
  }, [normalizeScenarioId, preselectedDeviceId, preselectedScenarioId]);

  useEffect(() => {
    if (!devices.length) return;
    setScenarioByDevice((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const device of devices) {
        const scenarioId = normalizeScenarioId(device.currentScenarioId);
        if (!scenarioId) continue;
        if (next[device.id] !== scenarioId) {
          next[device.id] = scenarioId;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [devices, normalizeScenarioId]);

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

  // Module C: motion data comes from `useLatestMotion(sessionId, deviceId)`
  // inside `<MotionPreviewPanel/>`; the page no longer plumbs a synthetic
  // VitalsSample through props.

  const [isApplying, setIsApplying] = useState(false);
  // Module G.5 — confirm before applying critical scenarios so an
  // accidental dropdown change doesn't push a real device into HIGH /
  // CRITICAL risk or fall_countdown.
  const [confirm, confirmDialog] = useConfirm();

  const changeScenario = useCallback(
    async (deviceId: string, scenarioId: string) => {
      const scenario = scenarios.find((item) => item.id === scenarioId) ?? null;
      const previousScenarioId = scenarioByDevice[deviceId];

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

      setScenarioByDevice((prev) => ({ ...prev, [deviceId]: scenarioId }));
      if (activeSession?.status !== "running") return;
      setIsApplying(true);
      try {
        await runWithToast(applyScenarioPreset(deviceId, scenarioId), {
          loading: `Đang áp dụng kịch bản "${scenario?.name ?? scenarioId}"…`,
          success: `Đã áp dụng "${scenario?.name ?? scenarioId}" cho thiết bị đang chạy.`,
          error: "Không áp dụng được kịch bản cho thiết bị này.",
        });
      } catch {
        // runWithToast surfaced the error toast — roll back optimistic
        // assignment so the dropdown returns to the previous scenario.
        if (previousScenarioId) {
          setScenarioByDevice((prev) => ({ ...prev, [deviceId]: previousScenarioId }));
        }
      } finally {
        setIsApplying(false);
      }
    },
    [activeSession?.status, confirm, scenarios, scenarioByDevice]
  );

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
        <h1 className="page-title">Mô phỏng tín hiệu sinh tồn</h1>
        <p className="page-subtitle">
          Theo dõi vitals + chuyển động trực tiếp và gán kịch bản cho các thiết bị đang bật SIM. Inject té ngã đã
          chuyển sang trang <strong>Phòng thí nghiệm té ngã</strong>.
        </p>
      </div>

      <DeviceAssignPanel
        devices={activeDevices}
        scenarios={scenarios}
        scenarioByDevice={scenarioByDevice}
        onScenarioChange={changeScenario}
        isApplying={isApplying}
      />

      <SessionVitalsPanel
        devices={activeDevices}
        deviceId={monitorDeviceId}
        runtimeTickAt={
          sessions.find((session) => session.status === "running" && session.deviceIds.includes(monitorDeviceId))?.lastTickAt
          ?? sessions.find((session) => session.id === activeSessionId && session.deviceIds.includes(monitorDeviceId))?.lastTickAt
          ?? null
        }
        onDeviceChange={setMonitorDeviceId}
      />

      {confirmDialog}
    </section>
  );
}
