import { apiClient } from "./api";
import type { AlertEvent } from "../types/event";

export async function injectEvent(deviceId: string, eventType: string, variant?: string): Promise<void> {
  await apiClient.post("/api/sim/events", {
    device_id: deviceId,
    event_type: eventType,
    variant
  });
}

export async function injectFallEvent(deviceId: string, variant = "confirmed"): Promise<void> {
  await apiClient.post("/api/sim/events/fall", {
    device_id: deviceId,
    event_type: "fall_detected",
    variant,
  });
}

/**
 * Operator confirmed they're OK — clear the BE FSM and stop the SOS
 * countdown.  Replaces the old FE-only `clearInterval` (Module C.3).
 */
export async function injectSosCancel(deviceId: string): Promise<void> {
  await apiClient.post("/api/sim/events", {
    device_id: deviceId,
    event_type: "sos_cancel",
  });
}

export async function fetchRecentEvents(limit = 10): Promise<AlertEvent[]> {
  const response = await apiClient.get<AlertEvent[]>("/api/sim/events/recent", { params: { limit } });
  return response.data;
}
