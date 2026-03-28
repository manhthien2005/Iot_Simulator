import { apiClient } from "./api";
import type { RiskInjectPayload, RiskScoreResponse, SleepSessionResponse } from "../types/analytics";

export async function getSleepSession(deviceId: string): Promise<SleepSessionResponse> {
  const response = await apiClient.get<SleepSessionResponse>("/api/sim/analytics/sleep", {
    params: { deviceId },
  });
  return response.data;
}

export async function getRiskScore(deviceId: string): Promise<RiskScoreResponse> {
  const response = await apiClient.get<RiskScoreResponse>("/api/sim/analytics/risk", {
    params: { deviceId },
  });
  return response.data;
}

export async function injectRiskScore(payload: RiskInjectPayload): Promise<void> {
  await apiClient.post("/api/sim/events/risk-inject", payload);
}

export async function triggerRiskCalculation(deviceId: string): Promise<void> {
  await apiClient.post("/api/sim/analytics/risk/trigger", {
    device_id: deviceId,
  });
}
