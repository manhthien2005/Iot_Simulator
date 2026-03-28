export interface ScenarioOption {
  id: string;
  name: string;
  category: "vitals" | "fall" | "sleep" | "risk";
  description: string;
  expectedOutcome: string;
}
