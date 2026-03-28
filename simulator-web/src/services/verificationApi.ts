import { apiClient } from "./api";
import type { VerificationResult } from "../types/verification";

export async function fetchVerification(sessionId: string): Promise<VerificationResult> {
  const response = await apiClient.get<VerificationResult>("/api/sim/verification/latest", {
    params: { sessionId }
  });
  return response.data;
}

