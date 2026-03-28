export type VitalsSeverity = "normal" | "warning" | "critical" | "invalid";
export type ActivityLabelValue = "resting" | "walking" | "running" | "falling" | "recovery" | "sleeping" | "unknown";

export interface VitalsSample {
  timestamp: string;
  heartRate: number;
  spo2: number;
  temperature: number | null;
  bloodPressureSys: number | null;
  bloodPressureDia: number | null;
  respiratoryRate: number | null;
  hrv?: number;
  signalQuality?: number;
  motionArtifact?: boolean;
  isStale: boolean;
  severity: VitalsSeverity;
  activityLabel: ActivityLabelValue;
  motionTag: ActivityLabelValue;
  fieldProvenance?: Record<string, string> | null;
  bpObservationAgeSec?: number | null;
  bpIsStale?: boolean | null;
  sourceMode?: "synthetic" | "replay" | "assisted" | null;
}
