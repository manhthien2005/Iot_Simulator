import { apiClient } from "./api";
import type {
  BatchActivateResult,
  DbDevice,
  DeviceType,
  PersonaConfig,
  SimulatedDevice,
} from "../types/device";

// ── Transform helpers ─────────────────────────────────────────────────────────
// Backend PersonaConfig uses snake_case (weight_kg, height_cm).
// Frontend standardizes on camelCase (weightKg, heightCm).

interface RawPersonaConfig {
  age?: number;
  weight_kg?: number;
  height_cm?: number;
  gender?: string | null;
  seed?: number;
}

interface RawSimulatedDevice extends Omit<SimulatedDevice, "personaConfig"> {
  personaConfig?: RawPersonaConfig | null;
}

function normalizePersonaConfig(raw: RawPersonaConfig | null | undefined): PersonaConfig | undefined {
  if (!raw) return undefined;
  return {
    age: raw.age,
    weightKg: raw.weight_kg,
    heightCm: raw.height_cm,
    gender: raw.gender,
    seed: raw.seed,
  };
}

function normalizeSimDevice(raw: RawSimulatedDevice): SimulatedDevice {
  const { personaConfig: rawPersona, ...rest } = raw;
  return { ...rest, personaConfig: normalizePersonaConfig(rawPersona) };
}

// ── Device APIs ───────────────────────────────────────────────────────────────

export async function fetchDevices(): Promise<SimulatedDevice[]> {
  const response = await apiClient.get<RawSimulatedDevice[]>("/api/sim/devices");
  return response.data.map(normalizeSimDevice);
}

// ── Admin DB Device APIs ──────────────────────────────────────────────────────
// Các hàm này thao tác trực tiếp với production DB qua Simulator API.
// Không liên quan đến SimulatedDevice (RAM runtime).

export async function fetchDbDevices(): Promise<DbDevice[]> {
  const { data } = await apiClient.get<DbDevice[]>("/api/sim/admin/db-devices");
  return data;
}

export async function createDbDevice(payload: {
  device_name: string;
  device_type: string;
  user_email?: string;
}): Promise<DbDevice> {
  const { data } = await apiClient.post<DbDevice>("/api/sim/admin/db-devices", payload);
  return data;
}

export async function assignDbDevice(deviceId: number, userEmail: string): Promise<DbDevice> {
  const { data } = await apiClient.post<DbDevice>(`/api/sim/admin/db-devices/${deviceId}/assign`, {
    user_email: userEmail,
  });
  return data;
}

export async function activateDbDevice(deviceId: number): Promise<DbDevice> {
  const { data } = await apiClient.post<DbDevice>(`/api/sim/admin/db-devices/${deviceId}/activate`);
  return data;
}

export async function deactivateDbDevice(deviceId: number): Promise<DbDevice> {
  const { data } = await apiClient.post<DbDevice>(`/api/sim/admin/db-devices/${deviceId}/deactivate`);
  return data;
}

export async function deleteDbDevice(deviceId: number): Promise<void> {
  await apiClient.delete(`/api/sim/admin/db-devices/${deviceId}`);
}

export async function batchActivateDbDevices(deviceIds: number[]): Promise<BatchActivateResult[]> {
  const { data } = await apiClient.post<BatchActivateResult[]>(
    "/api/sim/admin/db-devices/batch-activate",
    { device_ids: deviceIds },
    { timeout: 30000 }
  );
  return data;
}
