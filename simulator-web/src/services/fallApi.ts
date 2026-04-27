import { apiClient } from "./api";
import type { FallState } from "../types/fall";

/**
 * Fetch the BE-derived fall pipeline state for `deviceId` in `sessionId`.
 *
 * Used by the Sessions page Fall Lab — replaces the FE-only setInterval
 * countdown with a `countdownRemainingSec` derived from the actual fall
 * event timestamp (Module C.2).
 */
export async function fetchFallState(
  sessionId: string,
  deviceId: string,
): Promise<FallState> {
  const response = await apiClient.get<FallState>(
    `/api/sim/sessions/${encodeURIComponent(sessionId)}/fall-state`,
    { params: { deviceId } },
  );
  return response.data;
}
