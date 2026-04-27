import { useQuery } from "@tanstack/react-query";
import { fetchHealthV2 } from "../services/healthApi";
import { POLL_INTERVALS } from "../config/defaults";

/**
 * Single source of truth for the dashboard hero, degraded banner, and
 * telemetry KPI cards.
 *
 * The query polls `/api/sim/health` every {@link POLL_INTERVALS.health} ms
 * (15 s by default — keeps the model-API pill flip detectable within one
 * polling window per the Module A acceptance criterion).
 *
 * Every consumer should read this hook instead of calling `fetchHealth()`
 * directly — that way React Query de-dupes the request across the hero,
 * banner, and KPI grid in one window.
 *
 * Module H — bug 1+2 fixes:
 *   * `staleTime` matches the polling window so navigating
 *     dashboard ↔ devices ↔ scenarios doesn't trigger a redundant fetch
 *     within the same 15 s tick (avoids the "loads forever" feel).
 *   * `refetchOnMount: false` on cached data — when persisted data is
 *     hydrated from localStorage on cold-load, the hero renders the
 *     last known good payload immediately instead of blinking through
 *     the skeleton/error states.  The next polling tick still updates
 *     it within 15 s.
 */
export function useSystemHealth() {
  return useQuery({
    queryKey: ["sim", "health", "v2"],
    queryFn: fetchHealthV2,
    refetchInterval: POLL_INTERVALS.health,
    refetchIntervalInBackground: false,
    retry: false,
    // Suppress refetch-on-mount when we already have fresh-enough data
    // from the persister or a previous poll.
    staleTime: POLL_INTERVALS.health,
    // Keep the previous payload visible while the next refetch is in
    // flight so the hero never blinks back to skeleton during polling.
    placeholderData: (prev) => prev,
  });
}
