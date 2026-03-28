import { BatteryLow, Copy, Link2, MoreHorizontal, Trash2, Unplug } from "lucide-react";
import { useState } from "react";
import type { SimulatedDevice } from "../../types/device";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

interface DeviceTableProps {
  devices: SimulatedDevice[];
  onSelect: (device: SimulatedDevice) => void;
  onDelete: (deviceId: string) => void;
  onBind: (deviceId: string, dbDeviceId: string) => Promise<void>;
  onUnbind: (deviceId: string) => Promise<void>;
}

function statusSeverity(state: SimulatedDevice["state"]) {
  if (state === "critical" || state === "fall_countdown" || state === "sos_active") return "critical" as const;
  if (state === "warning") return "warning" as const;
  if (state === "offline") return "offline" as const;
  return "normal" as const;
}

export function DeviceTable({ devices, onSelect, onDelete, onBind, onUnbind }: DeviceTableProps) {
  const [bindInputs, setBindInputs] = useState<Record<string, string>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const inputValue = (device: SimulatedDevice) => bindInputs[device.id] ?? (device.boundDbDeviceId?.toString() ?? "");

  const handleBind = async (device: SimulatedDevice) => {
    const value = inputValue(device).trim();
    if (!value) {
      return;
    }
    setBusyKey(`bind:${device.id}`);
    try {
      await onBind(device.id, value);
    } finally {
      setBusyKey(null);
    }
  };

  const handleUnbind = async (deviceId: string) => {
    setBusyKey(`unbind:${deviceId}`);
    try {
      await onUnbind(deviceId);
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className="surface-card" style={{ overflow: "hidden" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ color: "var(--text-secondary)", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            <th style={{ textAlign: "left", padding: "10px 14px" }}>Trạng thái</th>
            <th style={{ textAlign: "left", padding: "10px 14px" }}>Tên</th>
            <th style={{ textAlign: "left", padding: "10px 14px" }}>Serial</th>
            <th style={{ textAlign: "left", padding: "10px 14px" }}>Ghép nối</th>
            <th style={{ textAlign: "left", padding: "10px 14px" }}>Pin</th>
            <th style={{ textAlign: "right", padding: "10px 14px" }}>Hành động</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => {
            const batteryColor = device.batteryLevel < 20 ? "var(--severity-critical)" : device.batteryLevel < 50 ? "var(--severity-warning)" : "var(--severity-normal)";
            return (
              <tr
                key={device.id}
                style={{ borderTop: "1px solid var(--border-default)", cursor: "pointer" }}
                onClick={() => onSelect(device)}
              >
                <td style={{ padding: "12px 14px" }}>
                  <Badge severity={statusSeverity(device.state)} dot pulse={device.isOnline}>
                    {device.isOnline ? "trực tuyến" : "ngoại tuyến"}
                  </Badge>
                </td>
                <td style={{ padding: "12px 14px", color: "var(--text-primary)" }}>{device.name}</td>
                <td style={{ padding: "12px 14px", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                  <span>{device.serialNumber}</span>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      navigator.clipboard?.writeText(device.serialNumber);
                    }}
                    style={{ marginLeft: "8px", background: "transparent", border: "none", color: "var(--text-secondary)", cursor: "pointer" }}
                  >
                    <Copy size={13} />
                  </button>
                </td>
                <td style={{ padding: "12px 14px" }}>
                  <div
                    onClick={(event) => event.stopPropagation()}
                    style={{ display: "grid", gap: "8px", minWidth: "240px" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      <Badge severity={device.boundDbDeviceId ? "normal" : "offline"}>
                        {device.boundDbDeviceId ? `DB #${device.boundDbDeviceId}` : "UNBOUND"}
                      </Badge>
                      <span style={{ fontSize: "11px", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                        {bindStatusLabel(device.bindStatus)}
                      </span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto auto", gap: "8px", alignItems: "center" }}>
                      <Input
                        type="number"
                        min={1}
                        placeholder="DB Device ID"
                        value={inputValue(device)}
                        onChange={(event) =>
                          setBindInputs((current) => ({
                            ...current,
                            [device.id]: event.target.value,
                          }))
                        }
                        style={{ minWidth: "110px" }}
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={<Link2 size={13} />}
                        loading={busyKey === `bind:${device.id}`}
                        disabled={!inputValue(device).trim() || busyKey !== null}
                        onClick={() => void handleBind(device)}
                      >
                        Bind
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={<Unplug size={13} />}
                        loading={busyKey === `unbind:${device.id}`}
                        disabled={device.boundDbDeviceId == null || busyKey !== null}
                        onClick={() => void handleUnbind(device.id)}
                      >
                        Unbind
                      </Button>
                    </div>
                  </div>
                </td>
                <td style={{ padding: "12px 14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div style={{ width: "92px", height: "8px", borderRadius: "999px", background: "var(--bg-elevated)", overflow: "hidden" }}>
                      <div style={{ width: `${device.batteryLevel}%`, height: "100%", background: batteryColor }} />
                    </div>
                    <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{device.batteryLevel}%</span>
                    {device.batteryLevel < 20 ? <BatteryLow size={13} color="var(--severity-critical)" /> : null}
                  </div>
                </td>
                <td style={{ padding: "12px 14px", textAlign: "right" }}>
                  <div onClick={(event) => event.stopPropagation()} style={{ display: "inline-flex", gap: "8px" }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      rightIcon={<MoreHorizontal size={14} />}
                      onClick={() => onSelect(device)}
                    >
                      Chi tiết
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      rightIcon={<Trash2 size={14} />}
                      onClick={() => onDelete(device.id)}
                    >
                      Xóa
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function bindStatusLabel(status: SimulatedDevice["bindStatus"]) {
  if (status === "bound") return "đã ghép";
  if (status === "bindable") return "có thể ghép";
  return "chưa ghép";
}
