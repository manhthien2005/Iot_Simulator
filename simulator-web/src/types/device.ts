export type DeviceState =
  | "draft"
  | "provisioned"
  | "bindable"
  | "bound"
  | "streaming"
  | "warning"
  | "critical"
  | "fall_countdown"
  | "sos_active"
  | "offline"
  | "retired";

export type DeviceType = "smartwatch" | "fitness_band" | "medical_device";

export interface PersonaConfig {
  age?: number;
  weightKg?: number;
  weight_kg?: number;
  heightCm?: number;
  height_cm?: number;
  gender?: string | null;
  seed?: number;
}

export interface SimulatedDevice {
  id: string;
  name: string;
  serialNumber: string;
  mqttClientId: string;
  deviceType: DeviceType;
  batteryLevel: number;
  isOnline: boolean;
  bindStatus: "unbound" | "bindable" | "bound";
  lastSeenAt: string | null;
  hasPendingSync: boolean;
  state: DeviceState;
  boundDbDeviceId: number | null;
  personaConfig?: PersonaConfig;
  persona_config?: PersonaConfig;
}

export interface BindDeviceResponse {
  sim_device_id: string;
  db_device_id: number | null;
  status: string;
}

export interface BatchActivateResult {
  id: number;
  status: "activated" | "not_found" | "error";
  detail?: string;
  device_name?: string;
}

/**
 * Thiết bị từ production DB, enriched với sim runtime status.
 * Source: GET /api/sim/admin/db-devices
 */
export interface DbDevice {
  id: number;
  uuid: string;
  user_id: number | null;
  user_email: string | null;
  user_full_name: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  date_of_birth: string | null;
  gender: string | null;
  device_name: string;
  device_type: string;
  model: string | null;
  firmware_version: string | null;
  serial_number: string | null;
  mac_address: string | null;
  mqtt_client_id: string | null;
  /** TRUE = thiết bị đang là active device của user trên mobile app */
  is_active: boolean;
  battery_level: number | null;
  signal_strength: number | null;
  last_seen_at: string | null;
  last_sync_at: string | null;
  registered_at: string | null;
  updated_at: string | null;
  /** TRUE = simulator runtime đang push vital qua localhost:8000 */
  is_sim_running: boolean;
}
