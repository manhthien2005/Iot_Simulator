import { apiClient } from "./api";
import type { VitalsSample } from "../types/vitals";

export async function fetchLatestVitals(deviceId: string): Promise<VitalsSample> {
  const response = await apiClient.get<VitalsSample>("/api/sim/vitals/latest", {
    params: { deviceId }
  });
  return response.data;
}

