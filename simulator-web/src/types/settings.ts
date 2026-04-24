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
  use_db_thresholds: boolean;
  pre_model_trigger_enabled: boolean;
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
}
