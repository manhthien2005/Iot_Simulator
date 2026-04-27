import { useQuery } from "@tanstack/react-query";
import { fetchFallState } from "../services/fallApi";
import { POLL_INTERVALS } from "../config/defaults";

/**
 * Subscribe to the BE-derived fall pipeline state for a `(sessionId,
 * deviceId)` pair.  Polls at the Fall Lab cadence so the countdown bar
 * advances roughly once a second (Module C.6).
 */
export function useFallState(
  sessionId: string | null,
  deviceId: string | null,
) {
  return useQuery({
    queryKey: ["fall", "state", sessionId, deviceId],
    queryFn: () => fetchFallState(sessionId!, deviceId!),
    enabled: Boolean(sessionId && deviceId),
    refetchInterval: POLL_INTERVALS.fallLabEvents,
    staleTime: POLL_INTERVALS.fallLabEvents,
  });
}
