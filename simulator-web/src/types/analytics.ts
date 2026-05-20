export type SleepStage = "deep" | "light" | "rem" | "awake";

export interface SleepStageSegment {
  stage: SleepStage;
  start: string;
  end: string;
}

export interface SleepHistoryRow {
  date: string;
  score: number;
  efficiency: number;
  durationMinutes: number;
  avgHeartRate: number;
  minSpo2: number;
}

export interface SleepSessionResponse {
  deviceId: string;
  date: string;
  realismMode: "fallback" | "real" | "edf";
  score: number;
  efficiency: number;
  durationMinutes: number;
  avgHeartRate: number;
  minSpo2: number;
  phases: SleepStageSegment[];
  history: SleepHistoryRow[];
  banner: string;
}

export interface DbSleepHistoryRow {
  date: string;
  score: number;
  efficiency: number;
  durationMinutes: number;
  wakeCount: number;
  phases: Record<string, number>;
  startTime: string;
  endTime: string;
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type RiskType = "general" | "stroke" | "cardiac";

export interface RiskContribution {
  feature: string;
  value: string;
  weight: number;
  direction: "up" | "down" | "flat";
}

export interface RiskHistoryPoint {
  date: string;
  score: number;
}

export interface RiskScoreResponse {
  deviceId: string;
  score: number;
  riskLevel: RiskLevel;
  model: string;
  algorithm: string;
  calculatedAt: string;
  explanation: RiskContribution[];
  history: RiskHistoryPoint[];
}

export interface BackfillSleepRequest {
  device_id: string;
  days_behind: number;
  scenario_id?: string;
}

export interface BackfillSleepResponse {
  pushed: number;
  skipped: number;
  errors: string[];
  total_days: number;
}

export interface PushSleepDateRequest {
  device_id: string;
  target_date: string;
  scenario_id?: string;
}

export interface PushSleepDateResponse {
  success: boolean;
  target_date: string;
  scenario_id: string;
  duration_minutes: number;
  sleep_score: number;
  disorder_tags: string[];
  was_overwritten: boolean;
  message: string;
}
