import type { ScenarioOption } from "../types/scenario";
import { apiClient } from "./api";

export async function fetchScenarios(): Promise<ScenarioOption[]> {
  const response = await apiClient.get<ScenarioOption[]>("/api/sim/scenarios");
  return response.data;
}

/**
 * Apply a scenario to a device.  Module B.4 — the entire side-effect
 * chain (fall event, sleep phase, risk inject) now lives behind this
 * single POST.  The previous `if (scenarioId === ...)` ladder fired
 * additional `events/fall` and `events/risk-inject` calls from the
 * browser, which:
 *   - silently doubled `fall_detected` events because the BE was
 *     already auto-injecting one for fall scenarios; and
 *   - hid the apply pipeline from any non-FE caller.
 *
 * The new manifest declares each side-effect via `ScenarioOption.followUp`
 * so consumers can introspect what a scenario will do without reading
 * code.  Render the chips from `keySignals` + `followUp` in the UI.
 */
export async function applyScenarioPreset(deviceId: string, scenarioId: string): Promise<void> {
  await apiClient.post("/api/sim/scenarios/apply", {
    device_id: deviceId,
    scenario_id: scenarioId,
  });
}
