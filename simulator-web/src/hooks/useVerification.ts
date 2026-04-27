import { useQuery } from "@tanstack/react-query";
import { fetchVerification, fetchAllVerifications } from "../services/verificationApi";
import { POLL_INTERVALS } from "../config/defaults";

export function useVerification(sessionId: string | null) {
  return useQuery({
    queryKey: ["verification", sessionId],
    queryFn: () => fetchVerification(sessionId as string),
    refetchInterval: sessionId ? POLL_INTERVALS.verification : false,
    enabled: Boolean(sessionId)
  });
}

export function useAllVerifications(sessionIds: string[]) {
  const stableKey = [...sessionIds].sort().join(",");
  return useQuery({
    queryKey: ["verification", "all", stableKey],
    queryFn: () => fetchAllVerifications(sessionIds),
    refetchInterval: sessionIds.length > 0 ? POLL_INTERVALS.verification : false,
    enabled: sessionIds.length > 0,
  });
}

