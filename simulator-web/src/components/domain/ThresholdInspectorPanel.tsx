import type { CSSProperties } from "react";
import { Card } from "../ui/Card";
import type { SimulatorSettingsResponse } from "../../types/settings";

// ---------------------------------------------------------------------------
// ThresholdInspectorPanel — Module D.8 + F.9.
//
// Read-only side-by-side view of the vitals thresholds the simulator uses
// at runtime: the *fallback* table baked into ``vitals_service.py`` and the
// *DB* table read by `SystemSettingsProvider` whenever the trigger
// orchestrator is wired (Phase 0.3).
//
// Lives on `/diagnostics` because:
//   1. It mutates nothing — but it *exposes* state that lets operators
//      decide whether to flip `USE_DB_THRESHOLDS`.
//   2. Settings is meant for mutable runtime config; "this is what the
//      simulator currently believes" belongs next to the rule + fall JSON
//      viewers.
//
// Cells where DB ≠ fallback are highlighted in cyan so anomalies pop.
// ---------------------------------------------------------------------------

const THRESHOLD_LABELS: Record<string, string> = {
  hr_critical_low: "Nhịp tim — Nguy hiểm thấp",
  hr_critical_high: "Nhịp tim — Nguy hiểm cao",
  hr_warning_low: "Nhịp tim — Cảnh báo thấp",
  hr_warning_high: "Nhịp tim — Cảnh báo cao",
  spo2_critical: "SpO2 — Nguy hiểm",
  spo2_warning: "SpO2 — Cảnh báo",
  rr_critical_low: "Nhịp thở — Nguy hiểm thấp",
  rr_critical_high: "Nhịp thở — Nguy hiểm cao",
  bp_sys_critical: "Huyết áp tâm thu — Nguy hiểm",
  bp_dia_critical: "Huyết áp tâm trương — Nguy hiểm",
  bp_sys_warning: "Huyết áp tâm thu — Cảnh báo",
  bp_dia_warning: "Huyết áp tâm trương — Cảnh báo",
  osa_alert_spo2_threshold: "OSA SpO2 ngưỡng",
  nocturnal_tachy_hr: "Nhịp tim nhanh ban đêm",
  apnea_rr_threshold: "Ngưng thở — nhịp thở",
};

function labelFor(key: string): string {
  return THRESHOLD_LABELS[key] ?? key;
}

interface ThresholdInspectorPanelProps {
  data: SimulatorSettingsResponse;
}

export function ThresholdInspectorPanel({ data }: ThresholdInspectorPanelProps) {
  const hasDb =
    data.db_daytime_thresholds !== null || data.db_sleep_thresholds !== null;
  const allKeys = Array.from(
    new Set([
      ...Object.keys(data.daytime_thresholds),
      ...Object.keys(data.sleep_thresholds),
      ...Object.keys(data.db_daytime_thresholds ?? {}),
      ...Object.keys(data.db_sleep_thresholds ?? {}),
    ]),
  );

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <strong>Threshold Inspector</strong>
          <ThresholdSourceBadge source={data.threshold_source} />
        </div>
      }
    >
      <p style={{ margin: "0 0 12px 0", fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
        Bảng chỉ đọc các ngưỡng vitals mà mô phỏng đang dùng — cột{" "}
        <strong style={{ color: "var(--text-primary)" }}>Fallback</strong> đến từ <code>vitals_service.py</code>,
        cột <strong style={{ color: "var(--text-primary)" }}>DB</strong> đến từ{" "}
        <code>SystemSettingsProvider</code>. Ô được tô khác màu khi giá trị DB khác fallback.
      </p>

      <div style={{ overflowX: "auto" }}>
        <table style={tableStyle}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-default)" }}>
              <th style={thStyle}>Chỉ số</th>
              <th style={thStyle}>{hasDb ? "Fallback (Ngày)" : "Ban ngày"}</th>
              {hasDb && <th style={thStyle}>DB (Ngày)</th>}
              <th style={thStyle}>{hasDb ? "Fallback (Đêm)" : "Ban đêm"}</th>
              {hasDb && <th style={thStyle}>DB (Đêm)</th>}
            </tr>
          </thead>
          <tbody>
            {allKeys.map((key) => {
              const fbDay = data.daytime_thresholds[key];
              const fbNight = data.sleep_thresholds[key];
              const dbDay = data.db_daytime_thresholds?.[key];
              const dbNight = data.db_sleep_thresholds?.[key];
              const dayDiff =
                hasDb && dbDay !== undefined && fbDay !== undefined && dbDay !== fbDay;
              const nightDiff =
                hasDb && dbNight !== undefined && fbNight !== undefined && dbNight !== fbNight;

              return (
                <tr key={key} style={{ borderBottom: "1px solid var(--border-default)" }}>
                  <td style={tdStyle}>{labelFor(key)}</td>
                  <td style={tdValueStyle}>{fbDay ?? "—"}</td>
                  {hasDb && (
                    <td
                      style={{
                        ...tdValueStyle,
                        color: dayDiff ? "var(--accent-cyan)" : undefined,
                      }}
                      title={dayDiff ? "Giá trị DB khác fallback" : undefined}
                    >
                      {dbDay ?? "—"}
                    </td>
                  )}
                  <td style={tdValueStyle}>{fbNight ?? "—"}</td>
                  {hasDb && (
                    <td
                      style={{
                        ...tdValueStyle,
                        color: nightDiff ? "var(--accent-cyan)" : undefined,
                      }}
                      title={nightDiff ? "Giá trị DB khác fallback" : undefined}
                    >
                      {dbNight ?? "—"}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ThresholdSourceBadge({ source }: { source: string }) {
  const map: Record<string, { label: string; tone: { fg: string; bg: string; border: string } }> = {
    db: {
      label: "Đọc từ DB",
      tone: {
        fg: "var(--severity-normal)",
        bg: "rgba(34,197,94,0.10)",
        border: "rgba(34,197,94,0.30)",
      },
    },
    fallback: {
      label: "Fallback (vitals_service)",
      tone: {
        fg: "var(--severity-warning)",
        bg: "rgba(245,158,11,0.10)",
        border: "rgba(245,158,11,0.30)",
      },
    },
  };
  const meta = map[source] ?? {
    label: source,
    tone: {
      fg: "var(--text-secondary)",
      bg: "transparent",
      border: "var(--border-default)",
    },
  };
  return (
    <span
      style={{
        fontSize: "11px",
        fontWeight: 700,
        padding: "2px 8px",
        borderRadius: "var(--radius-full)",
        color: meta.tone.fg,
        background: meta.tone.bg,
        border: `1px solid ${meta.tone.border}`,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    >
      {meta.label}
    </span>
  );
}

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "13px",
};

const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  color: "var(--text-secondary)",
  fontWeight: 600,
};

const tdStyle: CSSProperties = {
  padding: "6px 8px",
  color: "var(--text-primary)",
};

const tdValueStyle: CSSProperties = {
  padding: "6px 8px",
  color: "var(--text-primary)",
  fontFamily: "var(--font-mono)",
  textAlign: "right",
};
