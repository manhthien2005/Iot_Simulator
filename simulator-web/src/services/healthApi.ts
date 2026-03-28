import { apiClient } from "./api";

export interface HealthPayload {
  status: string;
  api: string;
  mqtt: string;
  db: string;
  version: string;
}

export async function fetchHealth(): Promise<HealthPayload> {
  const response = await apiClient.get<HealthPayload>("/api/sim/health");
  return response.data;
}

