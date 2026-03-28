export interface VerificationResult {
  deviceId: string;
  vitalsReceived: boolean;
  alertReceived: boolean;
  riskScoreReceived: boolean;
  latencyMs: number;
  status: "PASS" | "DELAYED" | "FAILED" | "PENDING";
  lastCheckedAt: string;
}

