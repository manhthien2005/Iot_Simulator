import { apiClient } from "./api";
import type { MotionLatest } from "../types/motion";

/**
 * Fetch the most recent motion window for `deviceId` in `sessionId`.
 *
 * Resolves with empty arrays when the simulator hasn't produced a tick
 * yet — the caller renders a "no data yet" empty state rather than
 * fabricating a synthetic preview (Module C.1).
 */
export async function fetchLatestMotion(
  sessionId: string,
  deviceId: string,
): Promise<MotionLatest> {
  const response = await apiClient.get<MotionLatest>(
    `/api/v1/sim/sessions/${encodeURIComponent(sessionId)}/motion/latest`,
    { params: { deviceId } },
  );
  return response.data;
}
