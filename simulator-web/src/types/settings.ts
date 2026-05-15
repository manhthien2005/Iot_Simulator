// ---------------------------------------------------------------------------
// Settings types — mirror `api_server/schemas.py`.
// Update both files together when the Pydantic schema changes.
// ---------------------------------------------------------------------------

export type TriggerMode = "off" | "shadow" | "active";
export type PersistenceSource = "file" | "defaults";

export interface RuntimeConfig {
  tick_interval_seconds: number;
  push_interval_seconds: number;
  sleep_speed_factor: number;
  health_backend_url: string;
}

export interface RuntimeConfigUpdate {
  tick_interval_seconds?: number;
  push_interval_seconds?: number;
  sleep_speed_factor?: number;
}

export interface FeatureFlags {
  /** Legacy boolean — keep reading until Module F adoption pass retires it. */
  use_db_thresholds: boolean;
  /** Legacy boolean — replaced by `trigger_mode`. */
  pre_model_trigger_enabled: boolean;
  /**
   * Canonical pre-trigger mode derived server-side. Module F.6 forbids the
   * UI from recomputing this from booleans.
   *  - `off`    pipeline disabled or orchestrator failed to wire.
   *  - `shadow` rules run locally, model API is *not* called.
   *  - `active` rules run locally and the simulator escalates to the model API.
   */
  trigger_mode: TriggerMode;
  /** Mirrors `enable_model_calls` on the trigger orchestrator. */
  enable_model_calls: boolean;
}

/** Where the live runtime config came from (Module F.1). */
export interface RuntimePersistenceBlock {
  source: PersistenceSource;
  path: string;
  last_saved_at: string | null;
  last_error: string | null;
}

export interface SimulatorSettingsResponse {
  runtime: RuntimeConfig;
  daytime_thresholds: Record<string, number>;
  sleep_thresholds: Record<string, number>;
  rules_config: Record<string, unknown> | null;
  fall_config: Record<string, unknown> | null;
  feature_flags: FeatureFlags;
  db_daytime_thresholds: Record<string, number> | null;
  db_sleep_thresholds: Record<string, number> | null;
  threshold_source: string;
  persistence: RuntimePersistenceBlock;
}

/**
 * Response shape for `PUT /api/v1/sim/settings/runtime` and
 * `POST /api/v1/sim/settings/runtime/reset` — carries the live config plus
 * the persistence echo so the FE can show "Đã lưu lúc HH:MM" immediately.
 */
export interface RuntimeConfigSaveResponse {
  runtime: RuntimeConfig;
  persistence: RuntimePersistenceBlock;
}
