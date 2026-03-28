import { useQuery } from "@tanstack/react-query";
import { fetchRecentEvents } from "../services/eventApi";

export function useRecentEvents(limit = 10, refetchInterval = 3000) {
  return useQuery({
    queryKey: ["events", "recent", limit],
    queryFn: () => fetchRecentEvents(limit),
    refetchInterval,
  });
}

