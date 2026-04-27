// ---------------------------------------------------------------------------
// Module B mirror of `api_server/routers/scenarios.py::ScenarioOption`.
// Keep this file in sync whenever the BE manifest evolves.
// ---------------------------------------------------------------------------

export type ScenarioCategory = "vitals" | "fall" | "sleep" | "risk";
export type ScenarioSeverity = "normal" | "warning" | "critical";
export type KeySignalDirection = "up" | "down" | "flat";
export type ScenarioFollowUpKind = "fall_event" | "risk_inject" | "sleep_phase" | "wake";

export interface KeySignal {
  label: string;
  direction: KeySignalDirection | null;
  target: string | null;
  severity: ScenarioSeverity;
}

export interface ScenarioFollowUp {
  kind: ScenarioFollowUpKind;
  detail: string;
}

export interface ScenarioOption {
  id: string;
  name: string;
  category: ScenarioCategory;
  description: string;
  expectedOutcome: string;
  severity: ScenarioSeverity;
  keySignals: KeySignal[];
  followUp: ScenarioFollowUp[];
}
