import { Play, Square, Trash2, UserPlus } from "lucide-react";
import { Tooltip } from "../ui/Tooltip";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { DbDevice } from "../../types/device";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

// ---------------------------------------------------------------------------
// DbDeviceTable — compact device list with merged status, demographics
// tooltip, SIM-running row highlight, and a 3-action bulk bar.
//
// Layout: 5 columns
//   ☐ │ # ID │ Thiết bị (name + type + status sub-line) │ Người dùng │ Action
//
// Status combines `is_active` (mobile sees the device) and `is_sim_running`
// (simulator runtime publishing vitals) into a single sub-line so the
// dedicated "Mobile" column is no longer needed.
// ---------------------------------------------------------------------------

interface DbDeviceTableProps {
  devices: DbDevice[];
  selectedIds: number[];
  onSelectionChange: (selectedIds: number[]) => void;
  onAssign: (deviceId: number, email: string) => Promise<void>;
  onActivateSim: (device: DbDevice) => Promise<void>;
  onDeactivateSim: (device: DbDevice) => Promise<void>;
  onDelete: (deviceId: number) => Promise<void>;
  onBatchActivate: (deviceIds: number[]) => Promise<void>;
  onBatchDeactivate?: (deviceIds: number[]) => Promise<void>;
  onBatchDelete?: (deviceIds: number[]) => Promise<void>;
  batchActivating?: boolean;
  batchBusy?: boolean;
}

export const DbDeviceTable = memo(function DbDeviceTable({
  devices,
  selectedIds,
  onSelectionChange,
  onAssign,
  onActivateSim,
  onDeactivateSim,
  onDelete,
  onBatchActivate,
  onBatchDeactivate,
  onBatchDelete,
  batchActivating = false,
  batchBusy = false,
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

  // Bulk-action eligibility: which selected devices can be activated /
  // deactivated.  We compute these once so the bottom action bar can show
  // the precise count next to each button label.
  const eligibleActivateIds = useMemo(
    () =>
      devices
        .filter((d) => selectedVisibleIds.includes(d.id) && d.user_id != null && !d.is_sim_running)
        .map((d) => d.id),
    [devices, selectedVisibleIds]
  );
  const eligibleDeactivateIds = useMemo(
    () =>
      devices
        .filter((d) => selectedVisibleIds.includes(d.id) && d.is_sim_running)
        .map((d) => d.id),
    [devices, selectedVisibleIds]
  );
  const blockedActivateCount = selectedCount - eligibleActivateIds.length;

  const allVisibleSelected = devices.length > 0 && selectedCount === devices.length;
  const someVisibleSelected = selectedCount > 0 && selectedCount < devices.length;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someVisibleSelected;
    }
  }, [someVisibleSelected]);

  const anyBusy = batchActivating || batchBusy || busyKey !== null;

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
    if (!eligibleActivateIds.length) return;
    await onBatchActivate(eligibleActivateIds);
  };

  const handleBatchDeactivate = async () => {
    if (!eligibleDeactivateIds.length || !onBatchDeactivate) return;
    await onBatchDeactivate(eligibleDeactivateIds);
  };

  const handleBatchDelete = async () => {
    if (!selectedCount || !onBatchDelete) return;
    await onBatchDelete(selectedVisibleIds);
  };

  return (
    <div className="surface-card" style={{ overflow: "hidden" }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "1020px" }}>
          <thead>
            <tr style={headerRowStyle}>
              <th style={{ ...thStyle, width: "44px" }}>
                <input
                  ref={selectAllRef}
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleAll}
                  disabled={anyBusy}
                  aria-label="Chọn tất cả thiết bị đang hiển thị"
                  style={checkboxStyle}
                />
              </th>
              <th style={{ ...thStyle, width: "56px" }}>ID</th>
              <th style={thStyle}>Thiết bị</th>
              <th style={{ ...thStyle, width: "140px" }}>Loại</th>
              <th style={{ ...thStyle, minWidth: "260px" }}>Người dùng</th>
              <th style={{ ...thStyle, textAlign: "right" }}>Hành động</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => {
              const canActivate = !device.is_sim_running && device.user_id !== null;
              const activateTitle = !device.user_id
                ? "Thiết bị chưa được gán user"
                : device.is_sim_running
                  ? "Đang SIM rồi"
                  : "Bật chế độ SIM";
              const canDeactivate = device.is_sim_running;
              const deactivateTitle = device.is_sim_running ? "Tắt chế độ SIM" : "Thiết bị chưa chạy simulator";
              const userName = device.user_full_name?.trim();
              const assignOpen = showAssign[device.id] ?? false;
              const isSelected = selectedIds.includes(device.id);

              const age = device.date_of_birth
                ? new Date(Date.now() - new Date(device.date_of_birth).getTime()).getUTCFullYear() - 1970
                : null;
              const demographics = [
                age ? `${Math.max(0, age)} tuổi` : null,
                device.gender === "male" ? "Nam" : device.gender === "female" ? "Nữ" : device.gender,
                device.weight_kg ? `${device.weight_kg} kg` : null,
                device.height_cm ? `${device.height_cm} cm` : null,
              ]
                .filter(Boolean)
                .join(" · ");

              return (
                <tr key={device.id} style={rowStyle(device.is_sim_running)}>
                  {/* Checkbox */}
                  <td style={tdStyle}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleDevice(device.id)}
                      disabled={anyBusy}
                      aria-label={`Chọn thiết bị ${device.device_name}`}
                      style={checkboxStyle}
                    />
                  </td>
                  {/* ID */}
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {device.id}
                  </td>
                  {/* Device name + merged status */}
                  <td style={tdStyle}>
                    <div style={{ display: "grid", gap: "4px" }}>
                      <strong style={{ color: "var(--text-primary)", fontSize: "14px" }}>
                        {device.device_name}
                      </strong>
                      <DeviceStatusLine device={device} />
                    </div>
                  </td>
                  {/* Device type — dedicated column for visual scan */}
                  <td style={tdStyle}>
                    <span style={typeBadgeStyle}>{device.device_type}</span>
                  </td>
                  {/* User cell */}
                  <td style={tdStyle}>
                    <div style={{ display: "grid", gap: "8px" }}>
                      {device.user_email ? (
                        <Tooltip
                          content={demographics || "Chưa có thông tin sinh trắc"}
                          placement="top"
                        >
                          <div style={{ display: "grid", gap: "2px", cursor: "help" }}>
                            <strong style={{ color: "var(--text-primary)", fontSize: "13px" }}>{device.user_email}</strong>
                            {userName ? (
                              <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>{userName}</span>
                            ) : null}
                          </div>
                        </Tooltip>
                      ) : (
                        <div style={unassignedHintStyle}>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--severity-warning)" }} aria-hidden="true" />
                            <strong style={{ color: "var(--severity-warning)", fontSize: "12px", letterSpacing: "0.04em", textTransform: "uppercase" }}>
                              Chưa gán user
                            </strong>
                          </span>
                          <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>
                            Bị bỏ qua khi bật SIM hàng loạt.
                          </span>
                        </div>
                      )}
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
                            disabled={anyBusy || !(assignInputs[device.id] ?? "").trim()}
                            onClick={() => void handleAssign(device)}
                          >
                            Gán
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  </td>
                  {/* Action icons */}
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <div style={{ display: "inline-flex", gap: "2px", alignItems: "center", justifyContent: "flex-end" }}>
                      <IconAction
                        icon={<UserPlus size={14} />}
                        tooltip={assignOpen ? "Ẩn gán user" : device.user_email ? "Gán lại user" : "Gán user"}
                        active={assignOpen}
                        disabled={anyBusy}
                        onClick={() => setShowAssign((prev) => ({ ...prev, [device.id]: !(prev[device.id] ?? false) }))}
                      />
                      <IconAction
                        icon={<Play size={14} />}
                        tooltip={activateTitle}
                        accent="cyan"
                        disabled={!canActivate || anyBusy}
                        busy={busyKey === `activate:${device.id}`}
                        onClick={() => void runAction(`activate:${device.id}`, () => onActivateSim(device))}
                      />
                      <IconAction
                        icon={<Square size={14} />}
                        tooltip={deactivateTitle}
                        disabled={!canDeactivate || anyBusy}
                        busy={busyKey === `deactivate:${device.id}`}
                        onClick={() => void runAction(`deactivate:${device.id}`, () => onDeactivateSim(device))}
                      />
                      <IconAction
                        icon={<Trash2 size={14} />}
                        tooltip="Xoá thiết bị"
                        accent="danger"
                        disabled={anyBusy}
                        busy={busyKey === `delete:${device.id}`}
                        onClick={() => void runAction(`delete:${device.id}`, () => onDelete(device.id))}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedCount > 0 ? (
        <div style={selectionBarStyle}>
          <div style={{ display: "grid", gap: "4px" }}>
            <strong style={{ color: "var(--text-primary)" }}>
              Đã chọn {selectedCount} thiết bị
            </strong>
            <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
              {blockedActivateCount > 0
                ? `${blockedActivateCount} không bật SIM được (chưa gán user hoặc đã SIM).`
                : "Tất cả đủ điều kiện kích hoạt SIM."}
            </span>
          </div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <Button variant="ghost" size="sm" disabled={batchActivating || batchBusy} onClick={clearSelection}>
              Bỏ chọn
            </Button>
            {onBatchDeactivate ? (
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Square size={13} />}
                disabled={!eligibleDeactivateIds.length || batchActivating || batchBusy}
                onClick={() => void handleBatchDeactivate()}
              >
                {`Tắt SIM (${eligibleDeactivateIds.length})`}
              </Button>
            ) : null}
            {onBatchDelete ? (
              <Button
                variant="danger"
                size="sm"
                leftIcon={<Trash2 size={13} />}
                disabled={!selectedCount || batchActivating || batchBusy}
                onClick={() => void handleBatchDelete()}
              >
                {`Xoá (${selectedCount})`}
              </Button>
            ) : null}
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Play size={13} />}
              loading={batchActivating}
              disabled={!eligibleActivateIds.length || batchActivating || batchBusy}
              onClick={() => void handleBatchActivate()}
            >
              {`Bật SIM (${eligibleActivateIds.length})`}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
});

// ── Subviews ────────────────────────────────────────────────────────────

function DeviceStatusLine({ device }: { device: DbDevice }) {
  const items: Array<{ label: string; color: string; pulse?: boolean }> = [];
  items.push(
    device.is_active
      ? { label: "Active", color: "var(--severity-normal)", pulse: true }
      : { label: "Idle", color: "var(--text-muted)" }
  );
  if (device.is_sim_running) {
    items.push({ label: "SIM running", color: "var(--accent-cyan)", pulse: true });
  }
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
      {items.map((item, idx) => (
        <span key={idx} style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <span
            className={item.pulse ? "live-dot" : undefined}
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: item.color,
              animation: item.pulse ? "live-pulse 2s infinite" : undefined,
            }}
            aria-hidden="true"
          />
          <span style={{ color: item.color, fontSize: "11.5px", fontWeight: 500, letterSpacing: "0.02em" }}>
            {item.label}
          </span>
        </span>
      ))}
    </div>
  );
}

interface IconActionProps {
  icon: React.ReactNode;
  tooltip: string;
  active?: boolean;
  accent?: "cyan" | "danger";
  disabled?: boolean;
  busy?: boolean;
  onClick: () => void;
}

function IconAction({ icon, tooltip, active, accent, disabled, busy, onClick }: IconActionProps) {
  const baseColor =
    accent === "danger" ? "#ef4444" : accent === "cyan" ? "var(--accent-cyan)" : "var(--text-secondary)";
  const bg = active ? "rgba(6,182,212,0.15)" : "transparent";
  const color = active ? "var(--accent-cyan)" : baseColor;

  return (
    <Tooltip content={tooltip}>
      <span style={{ display: "inline-flex" }}>
        <button
          type="button"
          aria-label={tooltip}
          disabled={disabled}
          onClick={onClick}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "28px",
            height: "28px",
            borderRadius: "var(--radius-sm)",
            border: "none",
            cursor: disabled ? "not-allowed" : "pointer",
            background: bg,
            color,
            opacity: disabled ? 0.4 : 1,
          }}
        >
          {busy ? <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>...</span> : icon}
        </button>
      </span>
    </Tooltip>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────

const headerRowStyle: React.CSSProperties = {
  color: "var(--text-muted)",
  fontSize: "11px",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  fontWeight: 600,
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
};

const tdStyle: React.CSSProperties = {
  padding: "12px",
  verticalAlign: "top",
};

const checkboxStyle: React.CSSProperties = {
  accentColor: "var(--accent-cyan)",
  width: "16px",
  height: "16px",
  cursor: "pointer",
};

function rowStyle(simRunning: boolean): React.CSSProperties {
  return {
    borderTop: "1px solid var(--border-default)",
    background: simRunning ? "rgba(34, 197, 94, 0.04)" : undefined,
    transition: "background 120ms ease",
  };
}

const typeBadgeStyle: React.CSSProperties = {
  display: "inline-flex",
  width: "fit-content",
  padding: "2px 8px",
  borderRadius: "var(--radius-full)",
  border: "1px solid var(--border-default)",
  background: "var(--bg-elevated)",
  color: "var(--text-secondary)",
  fontSize: "10px",
  fontWeight: 600,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
};

const unassignedHintStyle: React.CSSProperties = {
  display: "grid",
  gap: "4px",
};

const selectionBarStyle: React.CSSProperties = {
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
};
