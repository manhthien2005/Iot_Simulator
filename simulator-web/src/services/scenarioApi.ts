import type { ScenarioOption } from "../types/scenario";
import { apiClient } from "./api";

export async function fetchScenarios(): Promise<ScenarioOption[]> {
  const response = await apiClient.get<ScenarioOption[]>("/api/sim/scenarios");
  return response.data;
}

export async function applyScenarioPreset(deviceId: string, scenarioId: string): Promise<void> {
  await apiClient.post("/api/sim/scenarios/apply", {
    device_id: deviceId,
    scenario_id: scenarioId,
  });

  if (scenarioId === "fall_high_confidence") {
    await apiClient.post("/api/sim/events/fall", { device_id: deviceId, event_type: "fall_detected", variant: "confirmed" });
    return;
  }
  if (scenarioId === "fall_false_alarm") {
    await apiClient.post("/api/sim/events/fall", { device_id: deviceId, event_type: "fall_detected", variant: "false_fall" });
    return;
  }
  if (scenarioId === "fall_no_response") {
    await apiClient.post("/api/sim/events/fall", { device_id: deviceId, event_type: "fall_detected", variant: "confirmed" });
    await apiClient.post("/api/sim/events", { device_id: deviceId, event_type: "sos_triggered", variant: "no_response" });
    return;
  }
  if (scenarioId === "hypoxia_critical") {
    await apiClient.post("/api/sim/events/risk-inject", {
      device_id: deviceId,
      risk_type: "general",
      risk_level: "HIGH",
      score: 0.78,
    });
    return;
  }
  if (scenarioId === "high_risk_cardiac") {
    await apiClient.post("/api/sim/events/risk-inject", {
      device_id: deviceId,
      risk_type: "cardiac",
      risk_level: "CRITICAL",
      score: 0.9,
    });
    return;
  }
  if (scenarioId === "medium_risk_general") {
    await apiClient.post("/api/sim/events/risk-inject", {
      device_id: deviceId,
      risk_type: "general",
      risk_level: "MEDIUM",
      score: 0.58,
    });
    return;
  }
}
