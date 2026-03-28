export type AlertSeverity = "normal" | "warning" | "critical" | "offline";

export interface AlertEvent {
  id: string;
  timestamp: string;
  deviceId: string;
  eventType: string;
  severity: AlertSeverity;
  message: string;
  metadata: Record<string, string>;
}

