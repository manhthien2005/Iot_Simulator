import { apiClient } from "./api";
import type {
  RuntimeConfigSaveResponse,
  RuntimeConfigUpdate,
  SimulatorSettingsResponse,
} from "../types/settings";

export async function fetchSettings(): Promise<SimulatorSettingsResponse> {
  const response = await apiClient.get<SimulatorSettingsResponse>("/api/sim/settings");
  return response.data;
}

/**
 * Persist runtime knobs to `runtime.json` on the BE.  The response now
 * carries the freshly saved config **plus** a `persistence` block (Module
 * F.2) so the UI can show "Đã lưu lúc HH:MM" without waiting for the next
 * settings poll.
 */
export async function updateRuntimeConfig(
  body: RuntimeConfigUpdate,
): Promise<RuntimeConfigSaveResponse> {
  const response = await apiClient.put<RuntimeConfigSaveResponse>(
    "/api/sim/settings/runtime",
    body,
  );
  return response.data;
}

/**
 * Delete `runtime.json` and reload defaults (Module F.5 "Khôi phục mặc định").
 * Idempotent — safe to call when no runtime file exists.
 */
export async function restoreRuntimeDefaults(): Promise<RuntimeConfigSaveResponse> {
  const response = await apiClient.post<RuntimeConfigSaveResponse>(
    "/api/sim/settings/runtime/reset",
  );
  return response.data;
}
