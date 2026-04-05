import { useState } from "react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { notify } from "../../utils/toast";
import type { DeviceType } from "../../types/device";

export interface CreateDbDeviceModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (payload: {
    device_name: string;
    device_type: DeviceType;
    user_email?: string;
  }) => Promise<void>;
}

export function CreateDbDeviceModal({ open, onClose, onCreate }: CreateDbDeviceModalProps) {
  const [deviceName, setDeviceName] = useState("");
  const [deviceType, setDeviceType] = useState<DeviceType>("smartwatch");
  const [userEmail, setUserEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const submit = async () => {
    if (!deviceName.trim()) {
      setError("Tên thiết bị là bắt buộc.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      await onCreate({
        device_name: deviceName.trim(),
        device_type: deviceType,
        user_email: userEmail.trim() || undefined,
      });
      setDeviceName("");
      setDeviceType("smartwatch");
      setUserEmail("");
      onClose();
    } catch {
      setError("Không tạo được thiết bị. Kiểm tra lại dữ liệu nhập.");
      notify.error("Không tạo được thiết bị.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--bg-overlay)",
        zIndex: 50,
        display: "grid",
        placeItems: "center",
      }}
    >
      <div className="surface-card" style={{ width: "520px", padding: "18px" }}>
        <h3 style={{ marginTop: 0 }}>Tạo thiết bị</h3>
        <label htmlFor="db-device-name" style={{ display: "block", marginBottom: "6px", color: "var(--text-secondary)" }}>
          Tên thiết bị
        </label>
        <Input
          id="db-device-name"
          value={deviceName}
          onChange={(event) => setDeviceName(event.target.value)}
          placeholder="VSmart A1"
        />

        <label htmlFor="db-device-type" style={{ display: "block", marginTop: "12px", marginBottom: "6px", color: "var(--text-secondary)" }}>
          Loại thiết bị
        </label>
        <select
          id="db-device-type"
          value={deviceType}
          onChange={(event) => setDeviceType(event.target.value as DeviceType)}
          style={{
            width: "100%",
            background: "var(--bg-base)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            color: "var(--text-primary)",
            padding: "9px 12px",
          }}
        >
          <option value="smartwatch">Đồng hồ thông minh</option>
          <option value="fitness_band">Vòng đeo thể thao</option>
          <option value="medical_device">Thiết bị y tế</option>
        </select>

        <label htmlFor="db-device-email" style={{ display: "block", marginTop: "12px", marginBottom: "6px", color: "var(--text-secondary)" }}>
          User email (optional)
        </label>
        <Input
          id="db-device-email"
          value={userEmail}
          onChange={(event) => setUserEmail(event.target.value)}
          placeholder="user@demo.local"
        />

        {error ? <p style={{ color: "var(--severity-critical)" }}>{error}</p> : null}
        <div style={{ marginTop: "16px", display: "flex", justifyContent: "flex-end", gap: "8px" }}>
          <Button variant="ghost" onClick={onClose}>
            Hủy
          </Button>
          <Button variant="primary" onClick={submit} loading={loading}>
            Tạo
          </Button>
        </div>
      </div>
    </div>
  );
}
