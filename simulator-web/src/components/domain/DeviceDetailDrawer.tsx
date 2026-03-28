import { Copy, QrCode, Wifi, WifiOff } from "lucide-react";
import type { SimulatedDevice } from "../../types/device";
import { injectDeviceStatus, injectEvent } from "../../services/eventApi";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

interface DeviceDetailDrawerProps {
  device: SimulatedDevice | null;
  onClose: () => void;
}

export function DeviceDetailDrawer({ device, onClose }: DeviceDetailDrawerProps) {
  if (!device) return null;

  const personaConfig = device.personaConfig ?? device.persona_config ?? null;
  const copy = (value: string) => navigator.clipboard?.writeText(value);

  return (
    <aside
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "430px",
        height: "100vh",
        background: "var(--bg-elevated)",
        borderLeft: "1px solid var(--border-default)",
        padding: "18px",
        zIndex: 50,
        overflowY: "auto",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <h2 style={{ margin: 0 }}>{device.name}</h2>
        <Button variant="ghost" onClick={onClose}>
          Đóng
        </Button>
      </div>

      <Card padding="md">
        <div style={{ display: "grid", gap: "10px" }}>
          <div>
            <small style={{ color: "var(--text-secondary)" }}>Mã serial</small>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <code>{device.serialNumber}</code>
              <Button variant="ghost" size="sm" rightIcon={<Copy size={13} />} onClick={() => copy(device.serialNumber)}>
                Sao chép
              </Button>
            </div>
          </div>
          <div>
            <small style={{ color: "var(--text-secondary)" }}>MQTT ID</small>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <code>{device.mqttClientId}</code>
              <Button variant="ghost" size="sm" rightIcon={<Copy size={13} />} onClick={() => copy(device.mqttClientId)}>
                Sao chép
              </Button>
            </div>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <Badge severity={device.isOnline ? "normal" : "offline"} dot pulse={device.isOnline}>
              {device.isOnline ? "Trực tuyến" : "Ngoại tuyến"}
            </Badge>
            <Badge severity={device.bindStatus === "bound" ? "normal" : "warning"}>{bindStatusLabel(device.bindStatus)}</Badge>
            <Badge severity={device.boundDbDeviceId ? "normal" : "offline"}>
              {device.boundDbDeviceId ? `DB #${device.boundDbDeviceId}` : "UNBOUND"}
            </Badge>
          </div>
        </div>
      </Card>

      {personaConfig ? (
        <div style={{ marginTop: "12px" }}>
          <Card padding="md" header={<strong>Hồ sơ người dùng</strong>}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
              <PersonaField label="Tuổi" value={`${personaConfig.age ?? "?"} tuổi`} />
              <PersonaField
                label="Cân nặng"
                value={`${personaConfig.weightKg ?? personaConfig.weight_kg ?? "?"} kg`}
              />
              <PersonaField
                label="Chiều cao"
                value={`${personaConfig.heightCm ?? personaConfig.height_cm ?? "?"} cm`}
              />
              <PersonaField label="BMI" value={bmiLabel(personaConfig)} />
            </div>
          </Card>
        </div>
      ) : null}

      <div style={{ marginTop: "12px" }}>
        <Card padding="md" header={<strong>Thao tác nhanh</strong>}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            <Button variant="secondary" size="sm" leftIcon={<QrCode size={14} />}>
              Tạo QR
            </Button>
            <Button variant="outline" size="sm" leftIcon={<WifiOff size={14} />} onClick={() => injectDeviceStatus(device.id, "device_offline")}>
              Đánh dấu ngoại tuyến
            </Button>
            <Button variant="outline" size="sm" leftIcon={<Wifi size={14} />} onClick={() => injectDeviceStatus(device.id, "device_online")}>
              Đánh dấu trực tuyến
            </Button>
            <Button variant="danger" size="sm" onClick={() => injectEvent(device.id, "low_battery")}>
              Pin yếu
            </Button>
            <Button variant="danger" size="sm" onClick={() => injectEvent(device.id, "fall_detected", "confirmed")}>
              Tiêm sự kiện té ngã
            </Button>
            <Button variant="outline" size="sm" onClick={() => injectEvent(device.id, "stress")}>
              Gây căng thẳng
            </Button>
            <Button variant="ghost" size="sm" onClick={() => injectEvent(device.id, "neutral")}>
              Bình thường hóa
            </Button>
          </div>
        </Card>
      </div>
    </aside>
  );
}

function PersonaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <small style={{ color: "var(--text-secondary)" }}>{label}</small>
      <div style={{ fontWeight: 600, fontFamily: "var(--font-mono)" }}>{value}</div>
    </div>
  );
}

function bmiLabel(cfg: { weightKg?: number; weight_kg?: number; heightCm?: number; height_cm?: number }): string {
  const weight = cfg.weightKg ?? cfg.weight_kg ?? 0;
  const height = (cfg.heightCm ?? cfg.height_cm ?? 0) / 100;
  if (!weight || !height) return "?";
  const bmi = weight / (height * height);
  const category = bmi < 18.5 ? "Gầy" : bmi < 25 ? "BT" : bmi < 30 ? "Thừa cân" : "Béo phì";
  return `${bmi.toFixed(1)} (${category})`;
}

function bindStatusLabel(status: SimulatedDevice["bindStatus"]) {
  if (status === "bound") return "đã ghép";
  if (status === "bindable") return "có thể ghép";
  return "chưa ghép";
}
