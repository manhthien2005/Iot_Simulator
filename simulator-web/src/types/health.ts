// ---------------------------------------------------------------------------
// Health payload v2 — mirrors `api_server/schemas.py::HealthPayloadV2`.
// Keep this file in sync whenever the backend schema evolves.
//
// Module E.10 — The legacy flat keys (`status`, `api`, `backend`, `mqtt`,
// `db`, `version`) are still emitted by the backend for backwards
// compatibility but no FE consumer reads them anymore (HealthStatusPanel
// retired). We drop them from the FE type surface so callers can no longer
// reach for stale fields. Extra runtime keys are simply ignored.
// ---------------------------------------------------------------------------

export type HealthRuntimeState = "running" | "idle" | "stopped" | "degraded";
export type HealthBackendState = "connected" | "down" | "slow" | "unknown";
export type HealthDatabaseState = "connected" | "down";
export type HealthModelApiState = "ready" | "unavailable" | "unknown";
export type HealthPreTriggerMode = "off" | "shadow" | "active";
export type HealthThresholdSource = "db" | "fallback" | "unavailable";
export type HealthScoreSource = "ai" | "heuristic";

export interface HealthRuntimeBlock {
  state: HealthRuntimeState;
  version: string;
  uptimeSeconds: number;
}

export interface HealthDatabaseBlock {
  state: HealthDatabaseState;
  lastCheckMs: number | null;
}

export interface HealthBackendBlock {
  state: HealthBackendState;
  url: string;
  lastLatencyMs: number | null;
  lastError: string | null;
}

export interface HealthModelApiBlock {
  state: HealthModelApiState;
  url: string;
  lastCheckedAt: string | null;
  lastScoreSource: HealthScoreSource;
  lastError: string | null;
}

export interface HealthPreTriggerBlock {
  mode: HealthPreTriggerMode;
  enableModelCalls: boolean;
  thresholdSource: HealthThresholdSource;
}

export interface HealthTelemetryBlock {
  devicesSimulated: number;
  sessionsRunning: number;
  alertsLastHour: number;
  avgPublishLatencyMs: number;
}

/** Stable v2 payload — schemaVersion `"2.0"`. */
export interface HealthPayloadV2 {
  schemaVersion: "2.0";
  runtime: HealthRuntimeBlock;
  database: HealthDatabaseBlock;
  backend: HealthBackendBlock;
  modelApi: HealthModelApiBlock;
  preTrigger: HealthPreTriggerBlock;
  telemetry: HealthTelemetryBlock;
  degradedReasons: string[];
}

/** Canonical response shape — equivalent to {@link HealthPayloadV2}. */
export type HealthPayload = HealthPayloadV2;

/** Type guard used by callers that may have received a v1 response. */
export function isHealthPayloadV2(value: unknown): value is HealthPayloadV2 {
  return (
    !!value &&
    typeof value === "object" &&
    "schemaVersion" in value &&
    (value as { schemaVersion?: unknown }).schemaVersion === "2.0"
  );
}
