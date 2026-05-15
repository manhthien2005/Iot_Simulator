import { apiClient } from "./api";
import type { VerificationResult } from "../types/verification";

export async function fetchVerification(sessionId: string): Promise<VerificationResult> {
  const response = await apiClient.get<VerificationResult>("/api/v1/sim/verification/latest", {
    params: { sessionId }
  });
  return { ...response.data, sessionId };
}

export async function fetchAllVerifications(sessionIds: string[]): Promise<VerificationResult[]> {
  const results = await Promise.allSettled(sessionIds.map(fetchVerification));
  return results
    .filter((r): r is PromiseFulfilledResult<VerificationResult> => r.status === "fulfilled")
    .map((r) => r.value);
}

