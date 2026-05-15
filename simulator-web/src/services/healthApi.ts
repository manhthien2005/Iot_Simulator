import { apiClient } from "./api";
import type { HealthPayload, HealthPayloadV2 } from "../types/health";
import { isHealthPayloadV2 } from "../types/health";

export type { HealthPayload, HealthPayloadV2 } from "../types/health";

/**
 * Fetch the v2-compatible health payload from `/api/v1/sim/health`.
 *
 * The response object contains the structured v2 blocks (`runtime`,
 * `database`, `backend`, `modelApi`, `preTrigger`, `telemetry`,
 * `degradedReasons`). Legacy flat keys are still emitted by the BE for
 * backwards compatibility but are no longer surfaced on the FE type.
 */
export async function fetchHealth(): Promise<HealthPayload> {
  const response = await apiClient.get<HealthPayload>("/api/v1/sim/health");
  return response.data;
}

/**
 * Strict v2 fetch that throws when the backend has not been upgraded.
 *
 * Useful for the new dashboard hero (Module A) where the v2 contract is a
 * hard prerequisite. Existing call sites should keep using `fetchHealth()`
 * until they migrate.
 */
export async function fetchHealthV2(): Promise<HealthPayloadV2> {
  const data = await fetchHealth();
  if (!isHealthPayloadV2(data)) {
    throw new Error(
      "Simulator API returned a legacy /api/v1/sim/health payload (schemaVersion missing).",
    );
  }
  return data;
}
