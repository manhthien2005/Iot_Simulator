import { useQuery } from "@tanstack/react-query";
import { fetchVerification } from "../services/verificationApi";

export function useVerification(sessionId: string | null) {
  return useQuery({
    queryKey: ["verification", sessionId],
    queryFn: () => fetchVerification(sessionId as string),
    refetchInterval: sessionId ? 3000 : false,
    enabled: Boolean(sessionId)
  });
}

