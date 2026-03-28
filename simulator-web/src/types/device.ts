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
