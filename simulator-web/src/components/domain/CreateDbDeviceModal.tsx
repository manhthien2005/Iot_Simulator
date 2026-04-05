import { useState } from "react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Select } from "../ui/Select";
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
    <Modal
      open={open}
      onClose={onClose}
      title="Tạo thiết bị"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Hủy
          </Button>
          <Button variant="primary" onClick={submit} loading={loading}>
            Tạo
          </Button>
        </>
      }
    >
      <div style={{ display: "grid", gap: "14px" }}>
        <Input
          id="db-device-name"
          label="Tên thiết bị"
          value={deviceName}
          onChange={(event) => setDeviceName(event.target.value)}
          placeholder="VSmart A1"
          error={error && !deviceName.trim() ? "Tên thiết bị là bắt buộc" : undefined}
        />

        <Select
          id="db-device-type"
          label="Loại thiết bị"
          value={deviceType}
          onChange={(event) => setDeviceType(event.target.value as DeviceType)}
          fullWidth
        >
          <option value="smartwatch">Đồng hồ thông minh</option>
          <option value="fitness_band">Vòng đeo thể thao</option>
          <option value="medical_device">Thiết bị y tế</option>
        </Select>

        <Input
          id="db-device-email"
          label="User email (tùy chọn)"
          value={userEmail}
          onChange={(event) => setUserEmail(event.target.value)}
          placeholder="user@demo.local"
          helperText="Email của người sử dụng thiết bị"
        />

        {error && deviceName.trim() ? (
          <p style={{ color: "var(--severity-critical)", margin: 0, fontSize: "13px" }}>{error}</p>
        ) : null}
      </div>
    </Modal>
  );
}
