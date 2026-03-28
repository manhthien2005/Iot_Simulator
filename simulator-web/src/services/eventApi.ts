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

export async function injectDeviceStatus(deviceId: string, eventType: "device_offline" | "device_online" | "low_battery"): Promise<void> {
  await apiClient.post("/api/sim/events/device-status", {
    device_id: deviceId,
    event_type: eventType,
  });
}

export async function fetchRecentEvents(limit = 10): Promise<AlertEvent[]> {
  const response = await apiClient.get<AlertEvent[]>("/api/sim/events/recent", { params: { limit } });
  return response.data;
}
