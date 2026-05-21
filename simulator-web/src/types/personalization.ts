// ---------------------------------------------------------------------------
// Personalization types — mirror health_system backend schema v0.6.0.
//
// Sim web is read-only consumer: chỉ render baseline + adaptive thresholds
// + NEWS2-Lite + trend slopes để demo viên đối chiếu input (sim sinh) vs
// output (backend personalization phản hồi).
// ---------------------------------------------------------------------------

export interface BaselineMetric {
  mean: number | null;
  std: number | null;
  p05: number | null;
  p95: number | null;
  sample_size: number;
  is_group_default: boolean;
  status: "ready" | "learning";
}

export interface AdaptiveThresholdEntry {
  modifier_min: number;
  modifier_max: number;
  source_conditions: string[];
  medical_references: string[];
}

export interface News2LitePayload {
  total_score: number;
  component_scores: Record<string, number>;
  risk_level: "low" | "medium" | "high" | "critical";
  note: string;
  scale: string;
}

export interface TrendSlopeEntry {
  window: "30m" | "2h" | "7d" | string;
  slope_per_hour: number | null;
  sample_count: number;
  direction: "rising" | "falling" | "stable" | "insufficient_data";
}

export interface PersonalizationPayload {
  enabled: boolean;
  baseline_status: "ready" | "learning" | "disabled";
  baselines: Record<string, BaselineMetric>;
  adaptive_thresholds: Record<string, AdaptiveThresholdEntry>;
  news2_lite: News2LitePayload | null;
  trend_slopes: Record<string, TrendSlopeEntry[]>;
  hard_floor_violations: string[];
  personal_context_message: string | null;
}
