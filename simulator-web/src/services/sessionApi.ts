import { apiClient } from "./api";
import type { SessionInfo } from "../types/session";

export async function fetchSessions(): Promise<SessionInfo[]> {
  const response = await apiClient.get<SessionInfo[]>("/api/v1/sim/sessions");
  return response.data;
}

export async function stopSession(sessionId: string): Promise<void> {
  await apiClient.post(`/api/v1/sim/sessions/${sessionId}/stop`);
}
