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
  realismMode: "fallback" | "edf";
  score: number;
  efficiency: number;
  durationMinutes: number;
  avgHeartRate: number;
  minSpo2: number;
  phases: SleepStageSegment[];
  history: SleepHistoryRow[];
  banner: string;
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

export interface RiskInjectPayload {
  device_id: string;
  risk_type: RiskType;
  risk_level: RiskLevel;
  score: number;
}
