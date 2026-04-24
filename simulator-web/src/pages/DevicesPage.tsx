import { Plus, Watch } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { DbDeviceTable } from "../components/domain/DbDeviceTable";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { Skeleton } from "../components/ui/Skeleton";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { useDbDevices } from "../hooks/useDevices";
import {
  batchActivateDbDevices,
  activateDbDevice,
  assignDbDevice,
  createDbDevice,
  deactivateDbDevice,
  deleteDbDevice,
} from "../services/deviceApi";
import { notify } from "../utils/toast";
import type { DbDevice, DeviceType } from "../types/device";

export function DevicesPage() {
  const queryClient = useQueryClient();
  const { data: dbDevices = [], isLoading, error, refetch } = useDbDevices();
  const [search, setSearch] = useState("");
  const [openCreate, setOpenCreate] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [batchActivating, setBatchActivating] = useState(false);

  const filtered = useMemo(
    () =>
      dbDevices.filter(
        (device) =>
          device.device_name.toLowerCase().includes(search.toLowerCase()) ||
          (device.serial_number ?? "").toLowerCase().includes(search.toLowerCase()) ||
          (device.user_email ?? "").toLowerCase().includes(search.toLowerCase())
      ),
    [dbDevices, search]
  );

  useEffect(() => {
    const visibleIds = new Set(filtered.map((device) => device.id));
    setSelectedIds((current) => current.filter((id) => visibleIds.has(id)));
  }, [filtered]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["db-devices"] });

  const handleCreate = async (payload: {
    device_name: string;
    device_type: DeviceType;
    user_email?: string;
  }) => {
    await createDbDevice(payload);
    notify.success("Đã tạo thiết bị trong DB");
    await invalidate();
  };

  const handleAssign = async (deviceId: number, email: string) => {
    await assignDbDevice(deviceId, email);
    notify.success(`Đã gán thiết bị cho ${email}`);
    await invalidate();
  };

  const handleActivateSim = async (device: DbDevice) => {
    await activateDbDevice(device.id);
    notify.success(`Đã bật SIM cho ${device.device_name}. Chờ xác minh telemetry.`);
    await invalidate();
  };

  const handleDeactivateSim = async (device: DbDevice) => {
    await deactivateDbDevice(device.id);
    notify.warning(`Đã tắt SIM cho ${device.device_name}. Phiên sẽ dừng gửi dữ liệu.`);
    await invalidate();
  };

  const handleDelete = async (deviceId: number) => {
    await deleteDbDevice(deviceId);
    notify.success("Đã xóa thiết bị");
    await invalidate();
  };

  const handleBatchActivate = async (deviceIds: number[]) => {
    const eligibleDevices = filtered.filter((device) => deviceIds.includes(device.id) && device.user_id !== null);

    // Single-Active Rule Validation: Block activating multiple devices for the same user
    const userMap = new Map<number, number[]>();
    eligibleDevices.forEach((device) => {
      const u = device.user_id!;
      if (!userMap.has(u)) userMap.set(u, []);
      userMap.get(u)!.push(device.id);
    });

    const hasDuplicateUsers = Array.from(userMap.values()).some((arr) => arr.length > 1);
    if (hasDuplicateUsers) {
      notify.error("Không thể bật đồng thời nhiều thiết bị của cùng một người dùng. Hệ thống chỉ cho phép 1 thiết bị kích hoạt mỗi người dùng (Single-Active Rule).");
      return;
    }

    const blockedCount = deviceIds.length - eligibleDevices.length;

    if (!eligibleDevices.length) {
      notify.warning("Không có thiết bị hợp lệ để kích hoạt hàng loạt.");
      return;
    }

    setBatchActivating(true);
    try {
      const results = await batchActivateDbDevices(eligibleDevices.map((device) => device.id));
      const activatedCount = results.filter((item) => item.status === "activated").length;
      const failedCount = results.filter((item) => item.status === "error").length;
      const missingCount = results.filter((item) => item.status === "not_found").length;

      if (activatedCount > 0) {
        notify.success(`Đã bật sim thành công cho ${activatedCount} thiết bị`);
      }

      const warningParts = [
        blockedCount > 0 ? `${blockedCount} chưa gán user` : null,
        failedCount > 0 ? `${failedCount} lỗi` : null,
        missingCount > 0 ? `${missingCount} không tìm thấy` : null,
      ].filter((part): part is string => part !== null);

      if (warningParts.length > 0) {
        notify.warning(warningParts.join(" • "));
      }

      setSelectedIds([]);
      await invalidate();
    } catch {
      notify.error("Không kích hoạt được các thiết bị đã chọn.");
    } finally {
      setBatchActivating(false);
    }
  };

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: "12px" }}>
        <div>
          <h1 className="page-title">Thiết bị</h1>
          <p className="page-subtitle">
            Quản lý toàn bộ thiết bị trong hệ thống, trạng thái kết nối mobile và chế độ mô phỏng.
          </p>
        </div>
        <Button variant="primary" leftIcon={<Plus size={14} />} onClick={() => setOpenCreate(true)}>
          Tạo thiết bị
        </Button>
      </div>
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Tìm theo tên, serial hoặc email..."
      />

      {isLoading ? (
        <Skeleton style={{ height: "220px" }} />
      ) : error ? (
        <ErrorCard message="Không tải được danh sách thiết bị." onRetry={() => refetch()} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Watch}
          title="Không tìm thấy thiết bị"
          description="Tạo thiết bị mới hoặc thay đổi từ khóa tìm kiếm."
          action={{ label: "Tạo thiết bị", onClick: () => setOpenCreate(true) }}
        />
      ) : (
        <DbDeviceTable
          devices={filtered}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          onAssign={handleAssign}
          onActivateSim={handleActivateSim}
          onDeactivateSim={handleDeactivateSim}
          onDelete={handleDelete}
          onBatchActivate={handleBatchActivate}
          batchActivating={batchActivating}
        />
      )}

      <CreateDbDeviceModal open={openCreate} onClose={() => setOpenCreate(false)} onCreate={handleCreate} />
    </section>
  );
}

interface CreateDbDeviceModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (payload: {
    device_name: string;
    device_type: DeviceType;
    user_email?: string;
  }) => Promise<void>;
}

function CreateDbDeviceModal({ open, onClose, onCreate }: CreateDbDeviceModalProps) {
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
