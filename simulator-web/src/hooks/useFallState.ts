import { useQuery } from "@tanstack/react-query";
import { fetchFallState } from "../services/fallApi";
import { POLL_INTERVALS } from "../config/defaults";

/**
 * Subscribe to the BE-derived fall pipeline state for a `(sessionId,
 * deviceId)` pair.
 *
 * Adaptive polling (Module C.6):
 *   - `fall_countdown` active → 1 000 ms so the countdown bar advances ~1 s.
 *   - All other states       → `POLL_INTERVALS.fallLabEvents` (1 500 ms) to
 *     avoid hammering the BE when nothing is happening.
 */
export function useFallState(
  sessionId: string | null,
  deviceId: string | null,
) {
  return useQuery({
    queryKey: ["fall", "state", sessionId, deviceId],
    queryFn: () => fetchFallState(sessionId!, deviceId!),
    enabled: Boolean(sessionId && deviceId),
    refetchInterval: (query) =>
      query.state.data?.deviceState === "fall_countdown"
        ? 1_000
        : POLL_INTERVALS.fallLabEvents,
    staleTime: 800,
  });
}
