// ---------------------------------------------------------------------------
// Module E mirror of `api_server/schemas.py::VerificationResult`.  Keep the
// shape 1:1 with the Pydantic model — the only translation is the camelCase
// alias mapping handled by FastAPI.
// ---------------------------------------------------------------------------

export type VerificationStatus = "PASS" | "DELAYED" | "FAILED" | "PENDING";

export type PipelineStageStatus = "ok" | "pending" | "failed" | "skipped";

export type PipelineStageKey =
  | "device_registered"
  | "session_started"
  | "telemetry_generated"
  | "telemetry_published"
  | "risk_evaluated"
  | "alert_dispatched";

export interface PipelineStage {
  key: PipelineStageKey;
  label: string;
  status: PipelineStageStatus;
  detail: string | null;
  at: string | null;
}

export interface VerificationResult {
  /** Injected by the FE after fetch — which session this result came from. */
  sessionId?: string;
  deviceId: string;
  vitalsReceived: boolean;
  alertReceived: boolean;
  riskScoreReceived: boolean;
  latencyMs: number;
  status: VerificationStatus;
  lastCheckedAt: string;
  // Module E additions ──────────────────────────────────────────────────
  stages: PipelineStage[];
  failureReason: string | null;
  lastGoodPublishAt: string | null;
  lastPublishAttemptAt: string | null;
  publishAckCount: number;
  publishAttemptCount: number;
}

