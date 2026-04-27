import { useQuery } from "@tanstack/react-query";
import { fetchLatestMotion } from "../services/motionApi";
import { POLL_INTERVALS } from "../config/defaults";

/**
 * Subscribe to the most recent motion window for a `(sessionId, deviceId)`
 * pair.  Polls at the same cadence as the legacy synthetic preview so
 * cutting over feels identical to the operator (Module C.5).
 *
 * Disabled when either id is missing — the caller renders an empty state.
 */
export function useLatestMotion(
  sessionId: string | null,
  deviceId: string | null,
) {
  return useQuery({
    queryKey: ["motion", "latest", sessionId, deviceId],
    queryFn: () => fetchLatestMotion(sessionId!, deviceId!),
    enabled: Boolean(sessionId && deviceId),
    refetchInterval: POLL_INTERVALS.motionPreview,
    staleTime: POLL_INTERVALS.motionPreview,
  });
}
