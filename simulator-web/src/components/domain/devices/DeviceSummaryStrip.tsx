import type { CSSProperties, ReactNode } from "react";
import { AlertTriangle, Radio, UserX, Watch } from "lucide-react";
import type { DbDevice } from "../../../types/device";

// ---------------------------------------------------------------------------
// DeviceSummaryStrip — at-a-glance counts above the devices table.
//
// 4 stat tiles in a row so an operator can read the fleet's health without
// scanning the table:
//   • Tổng       — every device in the fleet
//   • Active     — device is the user's active mobile device
//   • SIM chạy   — simulator runtime is publishing vitals for this device
//   • Chưa gán   — device exists but has no linked user account
//
// Severity colors mirror the dashboard so the dashboard ↔ devices page feel
// like one product.
// ---------------------------------------------------------------------------

type TileSeverity = "neutral" | "ok" | "warning" | "critical";

interface DeviceSummaryStripProps {
  devices: DbDevice[];
}

export function DeviceSummaryStrip({ devices }: DeviceSummaryStripProps) {
  const total = devices.length;
  const active = devices.filter((d) => d.is_active).length;
  const simRunning = devices.filter((d) => d.is_sim_running).length;
  const unassigned = devices.filter((d) => d.user_id == null).length;

  return (
    <div className="devices-summary-grid" role="status" aria-label="Tổng quan thiết bị">
      <StatTile
        icon={<Watch size={18} />}
        label="Tổng"
        value={total}
        detail="thiết bị trong DB"
        severity="neutral"
      />
      <StatTile
        icon={<Radio size={18} />}
        label="Active"
        value={active}
        detail="kết nối mobile"
        severity={active > 0 ? "ok" : "neutral"}
      />
      <StatTile
        icon={<Radio size={18} />}
        label="SIM chạy"
        value={simRunning}
        detail="truyền dữ liệu"
        severity={simRunning > 0 ? "ok" : "neutral"}
      />
      <StatTile
        icon={unassigned > 0 ? <AlertTriangle size={18} /> : <UserX size={18} />}
        label="Chưa gán"
        value={unassigned}
        detail={unassigned > 0 ? "cần gán user" : "tất cả đã gán"}
        severity={unassigned > 0 ? "warning" : "ok"}
      />
    </div>
  );
}

// ── Subview ─────────────────────────────────────────────────────────────

interface StatTileProps {
  icon: ReactNode;
  label: string;
  value: number;
  detail: string;
  severity: TileSeverity;
}

function StatTile({ icon, label, value, detail, severity }: StatTileProps) {
  const palette = severityPalette[severity];
  return (
    <article style={tileStyle}>
      <header style={headerStyle}>
        <span style={{ display: "inline-flex", color: palette.fg, flexShrink: 0 }}>{icon}</span>
        <span style={labelStyle}>{label}</span>
      </header>
      <div style={{ ...valueStyle, color: palette.fg }}>{value}</div>
      <div style={detailStyle}>{detail}</div>
    </article>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────

const severityPalette: Record<TileSeverity, { fg: string }> = {
  neutral: { fg: "var(--text-primary)" },
  ok: { fg: "var(--severity-normal)" },
  warning: { fg: "var(--severity-warning)" },
  critical: { fg: "var(--severity-critical)" },
};

const tileStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "16px 18px",
  borderRadius: "var(--radius-lg)",
  background: "var(--bg-elevated)",
  border: "1px solid rgba(255, 255, 255, 0.06)",
  boxShadow: "var(--shadow-card)",
  minHeight: "112px",
};

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
};

const labelStyle: CSSProperties = {
  fontSize: "11px",
  fontWeight: 600,
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.09em",
  whiteSpace: "nowrap",
};

const valueStyle: CSSProperties = {
  marginTop: "12px",
  fontSize: "28px",
  fontWeight: 700,
  fontFamily: "var(--font-mono)",
  letterSpacing: "-0.02em",
  lineHeight: 1.1,
};

const detailStyle: CSSProperties = {
  marginTop: "auto",
  paddingTop: "10px",
  fontSize: "12px",
  color: "var(--text-muted)",
  lineHeight: 1.4,
};
