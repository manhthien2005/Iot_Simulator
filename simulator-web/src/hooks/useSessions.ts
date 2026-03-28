import { useQuery } from "@tanstack/react-query";
import { fetchSessions } from "../services/sessionApi";

export function useSessions(enabled = true) {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    refetchInterval: enabled ? 2000 : false,
    enabled,
  });
}

