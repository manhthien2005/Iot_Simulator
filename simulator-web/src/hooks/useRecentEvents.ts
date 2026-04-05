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
) {
  return useQuery({
    queryKey: ["events", "recent", limit],
    queryFn: () => fetchRecentEvents(limit),
    refetchInterval,
    ...options,
  });
}

