import { Card } from "../../ui/Card";
import type { DbDevice } from "../../../types/device";

// ---------------------------------------------------------------------------
// DevicePicker — single-select dropdown for picking which simulated device
// to drive.  Replaces the earlier cards-grid layout with a compact native
// `<select>` so the page real estate goes to the profile + scenario
// sections below.  The parent has already filtered to devices with
// `is_sim_running === true`.
// ---------------------------------------------------------------------------

interface DevicePickerProps {
  devices: DbDevice[];
  selectedDeviceId: number | null;
  onSelect: (deviceId: number) => void;
}

export function DevicePicker({ devices, selectedDeviceId, onSelect }: DevicePickerProps) {
  if (devices.length === 0) {
    return (
      <Card>
        <div
          style={{
            padding: "12px 0",
            textAlign: "center",
            color: "var(--text-muted)",
            fontSize: "13px",
          }}
        >
          Chưa có thiết bị nào đang bật SIM. Hãy sang tab <strong>Thiết bị</strong> và bật SIM trước.
        </div>
      </Card>
    );
  }

  const selectedDevice = devices.find((device) => device.id === selectedDeviceId) ?? null;

  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        <label
          htmlFor="device-picker"
          style={{
            fontSize: "13px",
            fontWeight: 600,
            color: "var(--text-secondary)",
            whiteSpace: "nowrap",
          }}
        >
          Thiết bị mô phỏng:
        </label>
        <select
          id="device-picker"
          value={selectedDeviceId ?? ""}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (!Number.isNaN(next)) onSelect(next);
          }}
          aria-label="Chọn thiết bị mô phỏng"
          style={{
            flex: 1,
            minWidth: "260px",
            background: "var(--bg-base)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            padding: "9px 12px",
            fontSize: "14px",
            cursor: "pointer",
          }}
        >
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {formatOptionLabel(device)}
            </option>
          ))}
        </select>
        {selectedDevice ? <SimStatusBadge active={selectedDevice.is_sim_running} /> : null}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// formatOptionLabel — single-line "Device — User (Serial)" so the dropdown
// is scannable.  Vietnamese names can be long, so we trim the most
// important info to the front: device label, then user, then serial.
// ---------------------------------------------------------------------------

function formatOptionLabel(device: DbDevice): string {
  const user = device.user_full_name?.trim() || "Chưa gán người dùng";
  return `${device.device_name} — ${user}`;
}

function SimStatusBadge({ active }: { active: boolean }) {
  return (
    <span
      title={active ? "SIM đang chạy" : "SIM dừng"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "4px 10px",
        borderRadius: "var(--radius-full)",
        background: active ? "rgba(34,197,94,0.12)" : "rgba(255,255,255,0.05)",
        color: active ? "var(--severity-normal)" : "var(--text-muted)",
        fontSize: "11.5px",
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          background: active ? "var(--severity-normal)" : "var(--text-muted)",
        }}
      />
      {active ? "SIM đang chạy" : "SIM dừng"}
    </span>
  );
}
