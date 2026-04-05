import { useQuery } from "@tanstack/react-query";
import { fetchSessions } from "../services/sessionApi";
import { POLL_INTERVALS } from "../config/defaults";

export function useSessions(enabled = true) {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    refetchInterval: enabled ? POLL_INTERVALS.sessions : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
    enabled,
  });
}
