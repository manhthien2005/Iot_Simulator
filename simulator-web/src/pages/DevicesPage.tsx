import { Plus, Watch } from "lucide-react";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CreateDbDeviceModal } from "../components/domain/CreateDbDeviceModal";
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
import { notify, runWithToast } from "../utils/toast";
import { useConfirm } from "../hooks/useConfirm";
import type { DbDevice, DeviceType } from "../types/device";

const EMPTY_DB_DEVICES: DbDevice[] = [];

export function DevicesPage() {
  const queryClient = useQueryClient();
  const { data: dbDevices = EMPTY_DB_DEVICES, isLoading, error, refetch } = useDbDevices();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [openCreate, setOpenCreate] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [batchActivating, setBatchActivating] = useState(false);
  // Module G.18 — confirm before destructive deletes + unified toasts
  // for the rest of the page's mutations.
  const [confirm, confirmDialog] = useConfirm();

  const filtered = useMemo(
    () => {
      const term = deferredSearch.toLowerCase();
      return dbDevices.filter(
        (device) =>
          device.device_name.toLowerCase().includes(term) ||
          (device.serial_number ?? "").toLowerCase().includes(term) ||
          (device.user_email ?? "").toLowerCase().includes(term)
      );
    },
    [dbDevices, deferredSearch]
  );

  useEffect(() => {
    const visibleIds = new Set(filtered.map((device) => device.id));
    setSelectedIds((current) => {
      const next = current.filter((id) => visibleIds.has(id));
      // Bail out: return same reference if nothing was removed → prevents re-render loop
      return next.length === current.length ? current : next;
    });
  }, [filtered]);

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["db-devices"] }),
    [queryClient]
  );

  const handleCreate = useCallback(
    async (payload: {
      device_name: string;
      device_type: DeviceType;
      user_email?: string;
    }) => {
      await runWithToast(createDbDevice(payload), {
        loading: `Đang tạo thiết bị "${payload.device_name}"…`,
        success: `Đã tạo thiết bị "${payload.device_name}" trong DB.`,
        error: "Không tạo được thiết bị. Kiểm tra kết nối.",
      });
      await invalidate();
    },
    [invalidate]
  );

  const handleAssign = useCallback(
    async (deviceId: number, email: string): Promise<void> => {
      try {
        await runWithToast(assignDbDevice(deviceId, email), {
          loading: `Đang gán thiết bị cho ${email}…`,
          success: `Đã gán thiết bị cho ${email}.`,
          error: "Không gán được thiết bị. Kiểm tra kết nối.",
        });
        await invalidate();
      } catch {
        // runWithToast surfaced the error toast.
      }
    },
    [invalidate]
  );

  // Module G.9 — optimistic SIM toggle.
  //
  // The row's "Bật/Tắt sim" buttons are the highest-frequency mutation
  // on the page.  Without optimism, the operator clicks → ~250 ms BE
  // round-trip → invalidate → refetch → row finally flips.  With
  // optimism we patch `is_sim_running` in the React Query cache
  // synchronously, runWithToast handles the loading/success/error
  // toast, and `onError` rolls the row back to the snapshot if the BE
  // rejects.  `onSettled` invalidates so the BE-truth eventually wins.
  //
  // Helper builds an optimistic mutation for a given target value of
  // `is_sim_running` so activate/deactivate share the patch logic.
  const buildSimToggleMutation = useCallback(
    (nextValue: boolean) => ({
      onMutate: async (device: DbDevice) => {
        await queryClient.cancelQueries({ queryKey: ["db-devices"] });
        const previous = queryClient.getQueryData<DbDevice[]>(["db-devices"]);
        queryClient.setQueryData<DbDevice[]>(["db-devices"], (old) =>
          old?.map((d) => (d.id === device.id ? { ...d, is_sim_running: nextValue } : d)) ?? old
        );
        return { previous };
      },
      onError: (_error: unknown, _device: DbDevice, ctx?: { previous?: DbDevice[] }) => {
        if (ctx?.previous) {
          queryClient.setQueryData(["db-devices"], ctx.previous);
        }
      },
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: ["db-devices"] });
      },
    }),
    [queryClient]
  );

  const activateSimMutation = useMutation({
    mutationFn: (device: DbDevice) => activateDbDevice(device.id),
    ...buildSimToggleMutation(true),
  });

  const deactivateSimMutation = useMutation({
    mutationFn: (device: DbDevice) => deactivateDbDevice(device.id),
    ...buildSimToggleMutation(false),
  });

  const handleActivateSim = useCallback(
    async (device: DbDevice): Promise<void> => {
      try {
        await runWithToast(activateSimMutation.mutateAsync(device), {
          loading: `Đang bật sim cho ${device.device_name}…`,
          success: `Đã bật sim cho ${device.device_name} — hệ thống đang truyền dữ liệu.`,
          error: `Không bật được sim cho ${device.device_name}. Kiểm tra kết nối.`,
        });
      } catch {
        // runWithToast already surfaced the error toast and onError
        // rolled back the optimistic patch.  Swallow so the click
        // handler doesn't leak an unhandled rejection.
      }
    },
    [activateSimMutation]
  );

  const handleDeactivateSim = useCallback(
    async (device: DbDevice): Promise<void> => {
      try {
        await runWithToast(deactivateSimMutation.mutateAsync(device), {
          loading: `Đang tắt sim cho ${device.device_name}…`,
          success: `Đã tắt sim cho ${device.device_name} — mobile app sẽ mất dữ liệu.`,
          error: `Không tắt được sim cho ${device.device_name}. Kiểm tra kết nối.`,
        });
      } catch {
        // see above
      }
    },
    [deactivateSimMutation]
  );

  const handleDelete = useCallback(
    async (deviceId: number): Promise<void> => {
      const target = dbDevices.find((d) => d.id === deviceId);
      const ok = await confirm({
        severity: "critical",
        title: "Xoá thiết bị?",
        description: target
          ? `Thao tác này xoá thiết bị "${target.device_name}" (id=${target.id}) khỏi production DB và không thể hoàn tác. Mọi sample/event đã ghi sẽ vẫn còn nhưng thiết bị sẽ biến mất khỏi danh sách.`
          : "Thao tác này xoá thiết bị khỏi production DB và không thể hoàn tác.",
        confirmLabel: "Xoá thiết bị",
      });
      if (!ok) return;

      try {
        await runWithToast(deleteDbDevice(deviceId), {
          loading: `Đang xoá ${target?.device_name ?? "thiết bị"}…`,
          success: `Đã xoá ${target?.device_name ?? "thiết bị"}.`,
          error: "Không xoá được thiết bị. Kiểm tra kết nối.",
        });
        await invalidate();
      } catch {
        // runWithToast surfaced the error toast.
      }
    },
    [confirm, dbDevices, invalidate]
  );

  const handleBatchActivate = useCallback(async (deviceIds: number[]) => {
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
  }, [filtered, invalidate]);

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
        placeholder="Tìm theo tên hoặc email..."
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
      {confirmDialog}
    </section>
  );
}
