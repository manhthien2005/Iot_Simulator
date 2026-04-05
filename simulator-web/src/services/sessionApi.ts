import { apiClient } from "./api";
import type { SessionInfo } from "../types/session";

export async function fetchSessions(): Promise<SessionInfo[]> {
  const response = await apiClient.get<SessionInfo[]>("/api/sim/sessions");
  return response.data;
}

export async function stopSession(sessionId: string): Promise<void> {
  await apiClient.post(`/api/sim/sessions/${sessionId}/stop`);
}
