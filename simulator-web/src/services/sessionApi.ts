import { apiClient } from "./api";
import type { SessionInfo } from "../types/session";

export async function fetchSessions(): Promise<SessionInfo[]> {
  const response = await apiClient.get<SessionInfo[]>("/api/sim/sessions");
  return response.data;
}

export async function createSession(deviceIds: string[], speed: 5 | 15 | 30 | 60): Promise<SessionInfo> {
  const response = await apiClient.post<SessionInfo>("/api/sim/sessions", {
    device_ids: deviceIds,
    speed
  });
  return response.data;
}

export async function startSession(sessionId: string): Promise<void> {
  await apiClient.post(`/api/sim/sessions/${sessionId}/start`);
}

export async function stopSession(sessionId: string): Promise<void> {
  await apiClient.post(`/api/sim/sessions/${sessionId}/stop`);
}
