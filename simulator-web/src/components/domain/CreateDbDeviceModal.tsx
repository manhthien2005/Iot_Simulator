import { useCallback, useEffect, useRef, useState } from "react";
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

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function CreateDbDeviceModal({ open, onClose, onCreate }: CreateDbDeviceModalProps) {
  const [deviceName, setDeviceName] = useState("");
  const [deviceType, setDeviceType] = useState<DeviceType>("smartwatch");
  const [userEmail, setUserEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const modalRef = useRef<HTMLDivElement>(null);

  // Auto-focus first input when modal opens
  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => {
      const firstInput = modalRef.current?.querySelector<HTMLElement>("input, select, textarea");
      firstInput?.focus();
    }, 0);
    return () => clearTimeout(timer);
  }, [open]);

  // ESC close + focus trap
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }

      if (event.key === "Tab" && modalRef.current) {
        const focusable = Array.from(
          modalRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey) {
          if (document.activeElement === first) {
            event.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, handleKeyDown]);

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
      onClick={(event) => {
        // Close on backdrop click (only when clicking the overlay itself)
        if (event.target === event.currentTarget) onClose();
      }}
      role="presentation"
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="surface-card"
        style={{ width: "520px", padding: "18px" }}
      >
        <h3 id="modal-title" style={{ marginTop: 0 }}>Tạo thiết bị</h3>
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
