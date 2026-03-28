import { Plus, Watch } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CreateDeviceModal } from "../components/domain/CreateDeviceModal";
import { DeviceDetailDrawer } from "../components/domain/DeviceDetailDrawer";
import { DeviceTable } from "../components/domain/DeviceTable";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { Skeleton } from "../components/ui/Skeleton";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { useDevices } from "../hooks/useDevices";
import { bindDevice, createDevice, deleteDevice, unbindDevice } from "../services/deviceApi";
import type { SimulatedDevice } from "../types/device";
import { notify } from "../utils/toast";

export function DevicesPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useDevices();
  const [search, setSearch] = useState("");
  const [openCreate, setOpenCreate] = useState(false);
  const [selected, setSelected] = useState<SimulatedDevice | null>(null);

  const devices = useMemo(
    () =>
      (data ?? []).filter(
        (device) =>
          device.name.toLowerCase().includes(search.toLowerCase()) ||
          device.serialNumber.toLowerCase().includes(search.toLowerCase())
      ),
    [data, search]
  );

  useEffect(() => {
    if (!selected || !data) return;
    const nextSelected = data.find((device) => device.id === selected.id) ?? null;
    setSelected(nextSelected);
  }, [data, selected]);

  const create = async (payload: { name: string; type: "smartwatch" | "fitness_band" | "medical_device" }) => {
    await createDevice(payload);
    notify.success("Đã tạo thiết bị");
    await queryClient.invalidateQueries({ queryKey: ["devices"] });
  };

  const remove = async (deviceId: string) => {
    await deleteDevice(deviceId);
    notify.success("Đã xóa thiết bị");
    await queryClient.invalidateQueries({ queryKey: ["devices"] });
  };

  const bind = async (deviceId: string, rawDbDeviceId: string) => {
    const dbDeviceId = Number.parseInt(rawDbDeviceId, 10);
    if (!Number.isInteger(dbDeviceId) || dbDeviceId <= 0) {
      notify.error("Nhập DB Device ID hợp lệ.");
      return;
    }
    try {
      await bindDevice(deviceId, dbDeviceId);
      notify.success(`Đã bind với DB #${dbDeviceId}`);
      await queryClient.invalidateQueries({ queryKey: ["devices"] });
    } catch {
      notify.error("Không bind được thiết bị.");
    }
  };

  const unbind = async (deviceId: string) => {
    try {
      await unbindDevice(deviceId);
      notify.success("Đã hủy bind thiết bị");
      await queryClient.invalidateQueries({ queryKey: ["devices"] });
    } catch {
      notify.error("Không hủy bind được thiết bị.");
    }
  };

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: "12px" }}>
        <div>
          <h1 className="page-title">Thiết bị</h1>
          <p className="page-subtitle">Quản lý thiết bị mô phỏng, trạng thái ghép nối và thao tác tiêm sự kiện nhanh.</p>
        </div>
        <Button variant="primary" leftIcon={<Plus size={14} />} onClick={() => setOpenCreate(true)}>
          Tạo thiết bị
        </Button>
      </div>
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Tìm theo tên hoặc serial..."
      />

      {isLoading ? (
        <Skeleton style={{ height: "220px" }} />
      ) : error ? (
        <ErrorCard message="Không tải được danh sách thiết bị." onRetry={() => refetch()} />
      ) : devices.length === 0 ? (
        <EmptyState
          icon={Watch}
          title="Không tìm thấy thiết bị"
          description="Tạo thiết bị mô phỏng đầu tiên để bắt đầu truyền dữ liệu."
          action={{ label: "Tạo thiết bị", onClick: () => setOpenCreate(true) }}
        />
      ) : (
        <DeviceTable devices={devices} onSelect={setSelected} onDelete={remove} onBind={bind} onUnbind={unbind} />
      )}

      <CreateDeviceModal open={openCreate} onClose={() => setOpenCreate(false)} onCreate={create} />
      <DeviceDetailDrawer device={selected} onClose={() => setSelected(null)} />
    </section>
  );
}
