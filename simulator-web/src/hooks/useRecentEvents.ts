import { useQuery } from "@tanstack/react-query";
import { fetchRecentEvents } from "../services/eventApi";
import type { AlertEvent } from "../types/event";

interface UseRecentEventsOptions {
  enabled?: boolean;
  select?: (data: AlertEvent[]) => AlertEvent[];
}

export function useRecentEvents(
  limit = 10,
  refetchInterval = 3000,
  options?: UseRecentEventsOptions,
) {
  return useQuery({
    queryKey: ["events", "recent", limit],
    queryFn: () => fetchRecentEvents(limit),
    refetchInterval,
    ...options,
  });
}

