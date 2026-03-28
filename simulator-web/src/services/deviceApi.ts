import { apiClient } from "./api";
import type { BindDeviceResponse, SimulatedDevice } from "../types/device";
import type { DeviceType } from "../types/device";

export async function fetchDevices(): Promise<SimulatedDevice[]> {
  const response = await apiClient.get<SimulatedDevice[]>("/api/sim/devices");
  return response.data;
}

export async function createDevice(payload: {
  name: string;
  type: DeviceType;
  persona_config?: { age: number; weight_kg: number; height_cm: number; seed: number };
}): Promise<SimulatedDevice> {
  const response = await apiClient.post<SimulatedDevice>("/api/sim/devices", payload);
  return response.data;
}

export async function deleteDevice(deviceId: string): Promise<void> {
  await apiClient.delete(`/api/sim/devices/${deviceId}`);
}

export async function bindDevice(deviceId: string, dbDeviceId: number): Promise<BindDeviceResponse> {
  const response = await apiClient.post<BindDeviceResponse>(`/api/sim/devices/${deviceId}/bind`, {
    db_device_id: dbDeviceId,
  });
  return response.data;
}

export async function unbindDevice(deviceId: string): Promise<BindDeviceResponse> {
  const response = await apiClient.delete<BindDeviceResponse>(`/api/sim/devices/${deviceId}/bind`);
  return response.data;
}
