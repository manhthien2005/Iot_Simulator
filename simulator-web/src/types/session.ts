export interface SessionInfo {
  id: string;
  deviceIds: string[];
  speed: 5 | 15 | 30 | 60;
  status: "idle" | "running" | "stopped";
  createdAt: string;
  lastTickAt: string | null;
}
