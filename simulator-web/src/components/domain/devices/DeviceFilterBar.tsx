import type { CSSProperties } from "react";
import { Search } from "lucide-react";
import type { DbDevice } from "../../../types/device";

// ---------------------------------------------------------------------------
// DeviceFilterBar — filter chips + search input on a single row.
//
// Pro-operators rarely need full-text search; they need fast filters like
// "show me devices with no user yet" or "show me what's actually streaming".
// Chips render that question one-click away, with live counts so the
// operator can plan triage without scanning the table.
// ---------------------------------------------------------------------------

export type DeviceFilter = "all" | "active" | "idle" | "unassigned" | "sim";

interface DeviceFilterBarProps {
  devices: DbDevice[];
  filter: DeviceFilter;
  onFilterChange: (next: DeviceFilter) => void;
  search: string;
  onSearchChange: (value: string) => void;
}

interface ChipDef {
  key: DeviceFilter;
  label: string;
  count: number;
}

export function DeviceFilterBar({
  devices,
  filter,
  onFilterChange,
  search,
  onSearchChange,
}: DeviceFilterBarProps) {
  const chips: ChipDef[] = [
    { key: "all", label: "Tất cả", count: devices.length },
    { key: "active", label: "Active", count: devices.filter((d) => d.is_active).length },
    { key: "idle", label: "Idle", count: devices.filter((d) => !d.is_active).length },
    { key: "unassigned", label: "Chưa gán", count: devices.filter((d) => d.user_id == null).length },
    { key: "sim", label: "SIM chạy", count: devices.filter((d) => d.is_sim_running).length },
  ];

  return (
    <div style={barStyle}>
      <div style={chipsRowStyle} role="tablist" aria-label="Bộ lọc thiết bị">
        {chips.map((chip) => {
          const selected = filter === chip.key;
          return (
            <button
              key={chip.key}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onFilterChange(chip.key)}
              style={chipStyle(selected)}
            >
              <span style={{ fontSize: "12px", fontWeight: 600 }}>{chip.label}</span>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "11px",
                  color: selected ? "var(--text-primary)" : "var(--text-muted)",
                  background: selected ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.04)",
                  padding: "1px 7px",
                  borderRadius: "var(--radius-full)",
                  minWidth: "22px",
                  textAlign: "center",
                }}
              >
                {chip.count}
              </span>
            </button>
          );
        })}
      </div>

      <label style={searchWrapStyle}>
        <Search size={14} aria-hidden="true" style={{ color: "var(--text-muted)" }} />
        <input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Tìm theo tên, email, serial..."
          style={searchInputStyle}
          aria-label="Tìm kiếm thiết bị"
        />
      </label>
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────

const barStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap",
};

const chipsRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
  flexWrap: "wrap",
};

function chipStyle(selected: boolean): CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 12px",
    borderRadius: "var(--radius-full)",
    border: `1px solid ${selected ? "var(--accent-cyan)" : "rgba(255,255,255,0.08)"}`,
    background: selected ? "rgba(6,182,212,0.12)" : "var(--bg-elevated)",
    color: selected ? "var(--accent-cyan)" : "var(--text-secondary)",
    cursor: "pointer",
    transition: "background 120ms ease, color 120ms ease, border-color 120ms ease",
  };
}

const searchWrapStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  padding: "8px 12px",
  borderRadius: "var(--radius-md)",
  background: "var(--bg-elevated)",
  border: "1px solid rgba(255,255,255,0.08)",
  minWidth: "260px",
  flex: "0 1 320px",
};

const searchInputStyle: CSSProperties = {
  background: "transparent",
  border: "none",
  outline: "none",
  color: "var(--text-primary)",
  fontSize: "13px",
  width: "100%",
};
