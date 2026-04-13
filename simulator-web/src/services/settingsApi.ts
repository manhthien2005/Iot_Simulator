import { apiClient } from "./api";
import type { RuntimeConfig, RuntimeConfigUpdate, SimulatorSettingsResponse } from "../types/settings";

export async function fetchSettings(): Promise<SimulatorSettingsResponse> {
  const response = await apiClient.get<SimulatorSettingsResponse>("/api/sim/settings");
  return response.data;
}

export async function updateRuntimeConfig(body: RuntimeConfigUpdate): Promise<RuntimeConfig> {
  const response = await apiClient.put<RuntimeConfig>("/api/sim/settings/runtime", body);
  return response.data;
}
