import type { SimulatedDevice } from "../../types/device";
import type { VitalsSample } from "../../types/vitals";
import { getVitalSeverity } from "../../utils/severity";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

interface DeviceStatusCardProps {
  device: SimulatedDevice;
  vitals: VitalsSample | null;
  onOpenSession: (deviceId: string) => void;
}

function severityBadge(value: "normal" | "warning" | "critical") {
  if (value === "critical") return "critical" as const;
  if (value === "warning") return "warning" as const;
  return "normal" as const;
}

export function DeviceStatusCard({ device, vitals, onOpenSession }: DeviceStatusCardProps) {
  return (
    <Card hoverable>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <strong>{device.name}</strong>
        <Badge severity={device.isOnline ? "normal" : "offline"} dot pulse={device.isOnline}>
          {deviceStateLabel(device.state)}
        </Badge>
      </div>
      {vitals ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "12px" }}>
          <Metric name="HR" value={`${Math.round(vitals.heartRate)} bpm`} severity={severityBadge(getVitalSeverity("heartRate", vitals.heartRate))} />
          <Metric name="SpO2" value={`${Math.round(vitals.spo2)}%`} severity={severityBadge(getVitalSeverity("spo2", vitals.spo2))} />
          <Metric
            name="Temp"
            value={formatTemperature(vitals.temperature)}
            severity={vitals.temperature != null ? severityBadge(getVitalSeverity("temperature", vitals.temperature)) : null}
          />
          <Metric
            name="BP"
            value={formatBloodPressure(vitals.bloodPressureSys, vitals.bloodPressureDia)}
            severity={vitals.bloodPressureSys != null ? severityBadge(getVitalSeverity("bloodPressureSys", vitals.bloodPressureSys)) : null}
          />
        </div>
      ) : (
        <p style={{ color: "var(--text-secondary)", margin: "0 0 12px" }}>Chưa có dữ liệu sinh hiệu</p>
      )}
      <button
        onClick={() => onOpenSession(device.id)}
        style={{ border: "none", background: "transparent", color: "var(--accent-cyan)", cursor: "pointer", padding: 0 }}
      >
        Mở phiên mô phỏng →
      </button>
    </Card>
  );
}

function Metric(props: { name: string; value: string; severity: "normal" | "warning" | "critical" | null }) {
  return (
    <div style={{ border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "8px" }}>
      <small style={{ color: "var(--text-secondary)" }}>{props.name}</small>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <strong>{props.value}</strong>
        {props.severity ? <Badge severity={props.severity}>{severityLabel(props.severity)}</Badge> : null}
      </div>
    </div>
  );
}

function severityLabel(value: "normal" | "warning" | "critical") {
  if (value === "normal") return "bình thường";
  if (value === "warning") return "cảnh báo";
  return "nguy cấp";
}

function deviceStateLabel(state: SimulatedDevice["state"]) {
  const labels: Record<SimulatedDevice["state"], string> = {
    draft: "nháp",
    provisioned: "đã cấp phát",
    bindable: "có thể ghép",
    bound: "đã ghép",
    streaming: "đang truyền",
    warning: "cảnh báo",
    critical: "nguy cấp",
    fall_countdown: "đếm ngược té ngã",
    sos_active: "SOS đang bật",
    offline: "ngoại tuyến",
    retired: "ngừng sử dụng",
  };
  return labels[state];
}

function formatTemperature(value: number | null | undefined): string {
  return value != null ? `${value.toFixed(1)}°C` : "—";
}

function formatBloodPressure(sys: number | null | undefined, dia: number | null | undefined): string {
  return sys != null && dia != null ? `${Math.round(sys)}/${Math.round(dia)}` : "—";
}
