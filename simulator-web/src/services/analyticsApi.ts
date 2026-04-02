import { apiClient } from "./api";
import type {
  BackfillSleepRequest,
  BackfillSleepResponse,
  DbSleepHistoryRow,
  PushSleepDateRequest,
  PushSleepDateResponse,
  RiskInjectPayload,
  RiskScoreResponse,
  SleepSessionResponse,
} from "../types/analytics";

export async function getSleepSession(deviceId: string): Promise<SleepSessionResponse> {
  const response = await apiClient.get<SleepSessionResponse>("/api/sim/analytics/sleep", {
    params: { deviceId },
  });
  return response.data;
}

export async function pushSleepSession(deviceId: string): Promise<void> {
  await apiClient.post(`/api/sim/analytics/sleep/${deviceId}/push`);
}

export async function getDbSleepHistory(deviceId: string, days: number = 30): Promise<DbSleepHistoryRow[]> {
  const response = await apiClient.get<DbSleepHistoryRow[]>("/api/sim/analytics/sleep/history", {
    params: { deviceId, days },
  });
  return response.data;
}

export async function pushSleepForDate(request: PushSleepDateRequest): Promise<PushSleepDateResponse> {
  const response = await apiClient.post<PushSleepDateResponse>("/api/sim/scenarios/sleep/push-date", request);
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

export async function backfillSleep(
  request: BackfillSleepRequest
): Promise<BackfillSleepResponse> {
  const response = await apiClient.post<BackfillSleepResponse>(
    "/api/sim/scenarios/sleep/backfill",
    request
  );
  return response.data;
}
