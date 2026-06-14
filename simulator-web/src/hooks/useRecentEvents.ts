import { useQuery } from "@tanstack/react-query";
import { fetchRecentEvents } from "../services/eventApi";
import type { AlertEvent } from "../types/event";
import { POLL_INTERVALS } from "../config/defaults";

interface UseRecentEventsOptions {
  enabled?: boolean;
  select?: (data: AlertEvent[]) => AlertEvent[];
}

export function useRecentEvents(
  limit = 10,
  refetchInterval: number = POLL_INTERVALS.events,
  options?: UseRecentEventsOptions,
  deviceId?: string | null,
) {
  return useQuery({
    // deviceId is included so switching devices invalidates the cache and
    // triggers a fresh fetch rather than returning the previous device's events.
    queryKey: ["events", "recent", limit, deviceId ?? null],
    queryFn: () => fetchRecentEvents(limit),
    refetchInterval,
    ...options,
  });
}
