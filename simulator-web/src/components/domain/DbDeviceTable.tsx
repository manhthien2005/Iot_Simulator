import { Copy, Play, Square, Trash2, UserPlus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DbDevice } from "../../types/device";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

interface DbDeviceTableProps {
  devices: DbDevice[];
  selectedIds: number[];
  onSelectionChange: (selectedIds: number[]) => void;
  onAssign: (deviceId: number, email: string) => Promise<void>;
  onActivateSim: (device: DbDevice) => Promise<void>;
  onDeactivateSim: (device: DbDevice) => Promise<void>;
  onDelete: (deviceId: number) => Promise<void>;
  onBatchActivate: (deviceIds: number[]) => Promise<void>;
  batchActivating?: boolean;
}

export function DbDeviceTable({
  devices,
  selectedIds,
  onSelectionChange,
  onAssign,
  onActivateSim,
  onDeactivateSim,
  onDelete,
  onBatchActivate,
  batchActivating = false,
}: DbDeviceTableProps) {
  const [assignInputs, setAssignInputs] = useState<Record<number, string>>({});
  const [showAssign, setShowAssign] = useState<Record<number, boolean>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const selectAllRef = useRef<HTMLInputElement | null>(null);

  const selectedVisibleIds = useMemo(
    () => devices.filter((device) => selectedIds.includes(device.id)).map((device) => device.id),
    [devices, selectedIds]
  );
  const selectedCount = selectedVisibleIds.length;
  const eligibleSelectedIds = useMemo(
    () => devices.filter((device) => selectedVisibleIds.includes(device.id) && device.user_id !== null).map((device) => device.id),
    [devices, selectedVisibleIds]
  );
  const blockedSelectedCount = selectedCount - eligibleSelectedIds.length;
  const allVisibleSelected = devices.length > 0 && selectedCount === devices.length;
  const someVisibleSelected = selectedCount > 0 && selectedCount < devices.length;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someVisibleSelected;
    }
  }, [someVisibleSelected]);

  const updateSelection = (updater: (current: number[]) => number[]) => {
    const next = updater(selectedIds);
    onSelectionChange(Array.from(new Set(next)));
  };

  const toggleDevice = (deviceId: number) => {
    updateSelection((current) =>
      current.includes(deviceId) ? current.filter((id) => id !== deviceId) : [...current, deviceId]
    );
  };

  const toggleAll = () => {
    if (allVisibleSelected) {
      updateSelection((current) => current.filter((id) => !devices.some((device) => device.id === id)));
      return;
    }
    updateSelection((current) => {
      const visibleIds = devices.map((device) => device.id);
      const merged = new Set(current);
      visibleIds.forEach((id) => merged.add(id));
      return Array.from(merged);
    });
  };

  const clearSelection = () => onSelectionChange([]);

  const handleAssign = async (device: DbDevice) => {
    const email = (assignInputs[device.id] ?? "").trim();
    if (!email) return;
    setBusyKey(`assign:${device.id}`);
    try {
      await onAssign(device.id, email);
      setShowAssign((prev) => ({ ...prev, [device.id]: false }));
      setAssignInputs((prev) => ({ ...prev, [device.id]: "" }));
    } finally {
      setBusyKey(null);
    }
  };

  const runAction = async (key: string, action: () => Promise<void>) => {
    setBusyKey(key);
    try {
      await action();
    } finally {
      setBusyKey(null);
    }
  };

  const handleBatchActivate = async () => {
    if (!eligibleSelectedIds.length) {
      return;
    }
    await onBatchActivate(eligibleSelectedIds);
  };

  return (
    <div className="surface-card" style={{ overflow: "hidden" }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "1100px" }}>
          <thead>
            <tr style={{ color: "var(--text-secondary)", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              <th style={{ textAlign: "left", padding: "10px 12px", width: "44px" }}>
                <input
                  ref={selectAllRef}
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleAll}
                  disabled={batchActivating}
                  aria-label="Chọn tất cả thiết bị đang hiển thị"
                  style={{ accentColor: "var(--accent-cyan)", width: "16px", height: "16px", cursor: "pointer" }}
                />
              </th>
              <th style={{ textAlign: "left", padding: "10px 12px", width: "96px" }}>ID</th>
              <th style={{ textAlign: "left", padding: "10px 12px" }}>Trạng thái</th>
              <th style={{ textAlign: "left", padding: "10px 12px" }}>Tên / Loại</th>
              <th style={{ textAlign: "left", padding: "10px 12px", minWidth: "290px" }}>Người dùng</th>
              <th style={{ textAlign: "left", padding: "10px 12px" }}>Serial</th>
              <th style={{ textAlign: "right", padding: "10px 12px" }}>Hành động</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => {
              const canActivate = !device.is_sim_running && device.user_id !== null;
              const activateTitle = !device.user_id
                ? "Thiết bị chưa được gán user"
                : device.is_sim_running
                  ? "Đang sim rồi"
                  : "Bật chế độ sim";
              const canDeactivate = device.is_sim_running;
              const deactivateTitle = device.is_sim_running ? "Tắt chế độ sim" : "Thiết bị chưa chạy simulator";
              const userName = device.user_full_name?.trim();
              const serial = device.serial_number?.trim() || "Chưa có";
              const assignOpen = showAssign[device.id] ?? false;
              const isSelected = selectedIds.includes(device.id);

              const age = device.date_of_birth
                ? new Date(Date.now() - new Date(device.date_of_birth).getTime()).getUTCFullYear() - 1970
                : null;
              const demographics = [
                age ? `${Math.max(0, age)}t` : null,
                device.gender === "male" ? "Nam" : device.gender === "female" ? "Nữ" : device.gender,
                device.weight_kg ? `${device.weight_kg}kg` : null,
                device.height_cm ? `${device.height_cm}cm` : null,
              ]
                .filter(Boolean)
                .join(" • ");

              return (
                <tr key={device.id} style={{ borderTop: "1px solid var(--border-default)" }}>
                  <td style={{ padding: "12px 12px", verticalAlign: "top" }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleDevice(device.id)}
                      disabled={batchActivating}
                      aria-label={`Chọn thiết bị ${device.device_name}`}
                      style={{ accentColor: "var(--accent-cyan)", width: "16px", height: "16px", cursor: "pointer" }}
                    />
                  </td>
                  <td style={{ padding: "12px 12px", verticalAlign: "top", fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-primary)" }}>
                    {device.id}
                  </td>
                  <td style={{ padding: "12px 12px", verticalAlign: "top" }}>
                    <div style={{ display: "grid", gap: "8px" }}>
                      <Badge severity={device.is_active ? "normal" : "offline"} dot pulse={device.is_active}>
                        {device.is_active ? "Mobile Active" : "Inactive"}
                      </Badge>
                      <Badge severity={device.is_sim_running ? "info" : "offline"} dot pulse={device.is_sim_running}>
                        {device.is_sim_running ? "Đang Sim" : "Chờ"}
                      </Badge>
                    </div>
                  </td>
                  <td style={{ padding: "12px 12px", verticalAlign: "top" }}>
                    <div style={{ display: "grid", gap: "6px" }}>
                      <strong style={{ color: "var(--text-primary)", fontSize: "14px" }}>{device.device_name}</strong>
                      <span
                        style={{
                          display: "inline-flex",
                          width: "fit-content",
                          padding: "2px 8px",
                          borderRadius: "var(--radius-full)",
                          border: "1px solid var(--border-default)",
                          background: "var(--bg-elevated)",
                          color: "var(--text-secondary)",
                          fontSize: "11px",
                          letterSpacing: "0.04em",
                          textTransform: "uppercase",
                        }}
                      >
                        {device.device_type}
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: "12px 12px", verticalAlign: "top" }}>
                    <div style={{ display: "grid", gap: "8px" }}>
                      {device.user_email ? (
                        <div style={{ display: "grid", gap: "2px" }}>
                          <strong style={{ color: "var(--text-primary)", fontSize: "13px" }}>{device.user_email}</strong>
                          {userName ? <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>{userName}</span> : null}
                          {demographics ? (
                            <span style={{ color: "var(--text-secondary)", fontSize: "11px", marginTop: "2px" }}>
                              {demographics}
                            </span>
                          ) : null}
                        </div>
                      ) : (
                        <div style={{ display: "grid", gap: "4px" }}>
                          <Badge severity="warning">Chưa gán user</Badge>
                          <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
                            Thiết bị này sẽ bị bỏ qua khi batch activate.
                          </span>
                        </div>
                      )}
                      <div style={{ display: "grid", gap: "8px" }}>
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<UserPlus size={13} />}
                          disabled={batchActivating || busyKey !== null}
                          onClick={() =>
                            setShowAssign((prev) => ({
                              ...prev,
                              [device.id]: !(prev[device.id] ?? false),
                            }))
                          }
                        >
                          {assignOpen ? "Ẩn gán user" : device.user_email ? "Gán lại user" : "Gán user"}
                        </Button>
                        {assignOpen ? (
                          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "8px" }}>
                            <Input
                              value={assignInputs[device.id] ?? ""}
                              onChange={(event) =>
                                setAssignInputs((prev) => ({
                                  ...prev,
                                  [device.id]: event.target.value,
                                }))
                              }
                              placeholder="email@domain.com"
                            />
                            <Button
                              variant="outline"
                              size="sm"
                              loading={busyKey === `assign:${device.id}`}
                              disabled={batchActivating || busyKey !== null || !(assignInputs[device.id] ?? "").trim()}
                              onClick={() => void handleAssign(device)}
                            >
                              Gán
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: "12px 12px", verticalAlign: "top" }}>
                    <div style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-primary)" }}>{serial}</span>
                      <button
                        type="button"
                        title="Copy serial"
                        onClick={() => {
                          if (device.serial_number) {
                            void navigator.clipboard?.writeText(device.serial_number);
                          }
                        }}
                        style={{
                          margin: 0,
                          padding: 0,
                          background: "transparent",
                          border: "none",
                          color: "var(--text-secondary)",
                          cursor: device.serial_number ? "pointer" : "default",
                        }}
                      >
                        <Copy size={13} />
                      </button>
                    </div>
                  </td>
                  <td style={{ padding: "12px 12px", textAlign: "right", verticalAlign: "top" }}>
                    <div style={{ display: "inline-flex", gap: "8px", flexWrap: "wrap", justifyContent: "flex-end" }}>
                      <span title={activateTitle} style={{ display: "inline-flex" }}>
                        <Button
                          variant="outline"
                          size="sm"
                          leftIcon={<Play size={13} />}
                          loading={busyKey === `activate:${device.id}`}
                          disabled={!canActivate || batchActivating || busyKey !== null}
                          onClick={() => void runAction(`activate:${device.id}`, () => onActivateSim(device))}
                        >
                          Bật Sim
                        </Button>
                      </span>
                      <span title={deactivateTitle} style={{ display: "inline-flex" }}>
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<Square size={13} />}
                          loading={busyKey === `deactivate:${device.id}`}
                          disabled={!canDeactivate || batchActivating || busyKey !== null}
                          onClick={() => void runAction(`deactivate:${device.id}`, () => onDeactivateSim(device))}
                        >
                          Tắt Sim
                        </Button>
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={<Trash2 size={13} />}
                        loading={busyKey === `delete:${device.id}`}
                        disabled={batchActivating || busyKey !== null}
                        onClick={() => void runAction(`delete:${device.id}`, () => onDelete(device.id))}
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

      {selectedCount > 0 ? (
        <div
          style={{
            position: "sticky",
            bottom: 0,
            zIndex: 1,
            marginTop: "12px",
            borderTop: "1px solid var(--border-default)",
            background: "linear-gradient(180deg, rgba(11,18,32,0.72) 0%, rgba(11,18,32,0.96) 100%)",
            backdropFilter: "blur(12px)",
            padding: "12px 14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "grid", gap: "4px" }}>
            <strong style={{ color: "var(--text-primary)" }}>✓ Đã chọn {selectedCount} thiết bị</strong>
            <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
              {blockedSelectedCount > 0
                ? `${blockedSelectedCount} thiết bị chưa gán user sẽ bị bỏ qua khi kích hoạt hàng loạt.`
                : "Tất cả thiết bị đã chọn đều đủ điều kiện kích hoạt."}
            </span>
          </div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <Button variant="ghost" size="sm" disabled={batchActivating} onClick={clearSelection}>
              Bỏ chọn
            </Button>
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Play size={13} />}
              loading={batchActivating}
              disabled={!eligibleSelectedIds.length || batchActivating}
              onClick={() => void handleBatchActivate()}
            >
              {`Bật Sim (${eligibleSelectedIds.length})`}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
