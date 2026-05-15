import type { CSSProperties } from "react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import type { SimulatedDevice } from "../../../types/device";

interface Props {
  focusDevice: SimulatedDevice | null;
  focusDeviceId: string;
  activeDevices: SimulatedDevice[];
  activeSessionStatus: string | null;
  onChange: (id: string) => void;
}

export function DeviceSessionBar({
  focusDevice,
  focusDeviceId,
  activeDevices,
  activeSessionStatus,
  onChange,
}: Props) {
  return (
    <Card padding="sm">
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "12px",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1 }}>
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Thiết bị mục tiêu:</span>
          <select
            value={focusDeviceId}
            onChange={(e) => onChange(e.target.value)}
            aria-label="Thiết bị mục tiêu"
            style={selectStyle}
            disabled={activeDevices.length === 0}
          >
            {activeDevices.length === 0
              ? <option value="">Không có thiết bị nào online</option>
              : null}
            {activeDevices.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          {focusDevice
            ? <Badge severity={deviceStateSeverity(focusDevice.state)}>{deviceStateLabel(focusDevice.state)}</Badge>
            : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Phiên:</span>
          <Badge
            severity={activeSessionStatus === "running" ? "normal" : "offline"}
            dot
            pulse={activeSessionStatus === "running"}
          >
            {activeSessionStatus === "running"
              ? "Đang chạy"
              : activeSessionStatus ?? "Chưa khởi động"}
          </Badge>
        </div>
      </div>
    </Card>
  );
}

function deviceStateLabel(state: string): string {
  switch (state) {
    case "streaming": return "Streaming";
    case "fall_countdown": return "Đang đếm ngược";
    case "sos_active": return "SOS active";
    case "warning": return "Cảnh báo";
    case "critical": return "Critical";
    case "offline": return "Offline";
    default: return state;
  }
}

function deviceStateSeverity(state: string): "normal" | "warning" | "critical" | "offline" | "info" {
  if (state === "sos_active" || state === "critical") return "critical";
  if (state === "fall_countdown" || state === "warning") return "warning";
  if (state === "offline" || state === "retired") return "offline";
  return "normal";
}

const selectStyle: CSSProperties = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "6px 10px",
  minWidth: "200px",
};
