import { useState } from "react";
import type { DeviceType } from "../../types/device";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

interface CreateDeviceModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (payload: { name: string; type: DeviceType }) => Promise<void>;
}

export function CreateDeviceModal({ open, onClose, onCreate }: CreateDeviceModalProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<DeviceType>("smartwatch");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const submit = async () => {
    if (!name.trim()) {
      setError("Tên thiết bị là bắt buộc.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await onCreate({ name: name.trim(), type });
      setName("");
      setType("smartwatch");
      onClose();
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
      <div className="surface-card" style={{ width: "480px", padding: "18px" }}>
        <h3 style={{ marginTop: 0 }}>Tạo thiết bị</h3>
        <label htmlFor="device-name" style={{ display: "block", marginBottom: "6px", color: "var(--text-secondary)" }}>
          Tên thiết bị
        </label>
        <Input id="device-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="VSmart A1" />
        <label htmlFor="device-type" style={{ display: "block", marginTop: "12px", marginBottom: "6px", color: "var(--text-secondary)" }}>
          Loại thiết bị
        </label>
        <select
          id="device-type"
          value={type}
          onChange={(event) => setType(event.target.value as DeviceType)}
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
