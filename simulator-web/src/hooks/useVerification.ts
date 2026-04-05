import { useQuery } from "@tanstack/react-query";
import { fetchVerification } from "../services/verificationApi";
import { POLL_INTERVALS } from "../config/defaults";

export function useVerification(sessionId: string | null) {
  return useQuery({
    queryKey: ["verification", sessionId],
    queryFn: () => fetchVerification(sessionId as string),
    refetchInterval: sessionId ? POLL_INTERVALS.verification : false,
    enabled: Boolean(sessionId)
  });
}

