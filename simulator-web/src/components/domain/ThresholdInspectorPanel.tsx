import { useMemo, useState, type CSSProperties } from "react";
import { Card } from "../ui/Card";
import type { SimulatorSettingsResponse } from "../../types/settings";
import {
  THRESHOLD_GROUPS,
  getThresholdInfo,
  type ThresholdGroup,
  type ThresholdGroupMeta,
  type ThresholdInfo,
  type ThresholdSeverity,
} from "./thresholdMeta";

// ---------------------------------------------------------------------------
// ThresholdInspectorPanel — Module D.8 + F.9 (refactor 2026-05).
//
// Read-only side-by-side view of vitals thresholds: gom theo nhóm chỉ số
// (HR, SpO₂, RR, BP, Sleep events) thay vì 1 bảng phẳng. Mỗi nhóm có 1 card
// với mô tả ngắn + bảng Day/Night kèm đơn vị, severity badge, status pill
// "Match"/"DB ghi đè".
//
// Lives on `/diagnostics`: chỉ hiển thị, không sửa. Logic so sánh DB vs
// fallback giữ nguyên — đổi bố cục thôi.
// ---------------------------------------------------------------------------

interface ThresholdInspectorPanelProps {
  data: SimulatorSettingsResponse;
}

interface GroupedRow {
  key: string;
  info: ThresholdInfo;
  fbDay?: number;
  fbNight?: number;
  dbDay?: number;
  dbNight?: number;
  dayDiff: boolean;
  nightDiff: boolean;
}

export function ThresholdInspectorPanel({ data }: ThresholdInspectorPanelProps) {
  const hasDb =
    data.db_daytime_thresholds !== null || data.db_sleep_thresholds !== null;
  const [diffOnly, setDiffOnly] = useState(false);

  const allKeys = Array.from(
    new Set([
      ...Object.keys(data.daytime_thresholds),
      ...Object.keys(data.sleep_thresholds),
      ...Object.keys(data.db_daytime_thresholds ?? {}),
      ...Object.keys(data.db_sleep_thresholds ?? {}),
    ]),
  );

  const grouped: Record<ThresholdGroup, GroupedRow[]> = {
    hr: [],
    spo2: [],
    rr: [],
    bp: [],
    sleep_event: [],
  };
  const orphans: GroupedRow[] = [];

  for (const key of allKeys) {
    const info = getThresholdInfo(key);
    const fbDay = data.daytime_thresholds[key];
    const fbNight = data.sleep_thresholds[key];
    const dbDay = data.db_daytime_thresholds?.[key];
    const dbNight = data.db_sleep_thresholds?.[key];
    const dayDiff =
      hasDb && dbDay !== undefined && fbDay !== undefined && dbDay !== fbDay;
    const nightDiff =
      hasDb && dbNight !== undefined && fbNight !== undefined && dbNight !== fbNight;
    const row: GroupedRow = {
      key,
      info: info ?? {
        group: "sleep_event",
        severity: "info",
        bound: "single",
        label: key,
        hint: "Chưa có metadata — cần cập nhật thresholdMeta.ts.",
      },
      fbDay,
      fbNight,
      dbDay,
      dbNight,
      dayDiff,
      nightDiff,
    };
    if (info) {
      grouped[info.group].push(row);
    } else {
      orphans.push(row);
    }
  }

  const totalDiff = useMemo(() => {
    if (!hasDb) return 0;
    let count = 0;
    for (const rows of Object.values(grouped)) {
      for (const r of rows) if (r.dayDiff || r.nightDiff) count++;
    }
    for (const r of orphans) if (r.dayDiff || r.nightDiff) count++;
    return count;
  }, [grouped, orphans, hasDb]);

  const filterRows = (rows: GroupedRow[]) =>
    diffOnly ? rows.filter((r) => r.dayDiff || r.nightDiff) : rows;

  return (
    <div style={{ display: "grid", gap: "12px" }}>
      <Card
        header={
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <strong>Threshold Inspector</strong>
            <ThresholdSourceBadge source={data.threshold_source} />
            {hasDb && totalDiff > 0 && (
              <Pill tone="cyan">{totalDiff} ngưỡng đang bị ghi đè</Pill>
            )}
          </div>
        }
      >
        <p style={legendTextStyle}>
          Trang này hiển thị các <strong>ngưỡng vitals</strong> mà mô phỏng đang dùng để gắn cờ cảnh báo.
          Cột <Pill tone="neutral">Fallback</Pill> đọc từ <code>vitals_service.py</code> (giá trị hard-code
          mặc định). Cột <Pill tone="cyan">DB</Pill> đọc từ <code>SystemSettingsProvider</code> (operator có
          thể chỉnh trong Health backend). Khi DB khác Fallback, dòng được đánh dấu để dễ phát hiện cấu hình
          ghi đè.
        </p>
        {hasDb && (
          <label style={diffToggleStyle}>
            <input
              type="checkbox"
              checked={diffOnly}
              onChange={(e) => setDiffOnly(e.target.checked)}
            />
            <span>Chỉ hiện ngưỡng DB khác Fallback</span>
          </label>
        )}
      </Card>

      {THRESHOLD_GROUPS.map((meta) => {
        const rows = filterRows(grouped[meta.key]);
        if (!rows.length) return null;
        return (
          <ThresholdGroupCard key={meta.key} meta={meta} rows={rows} hasDb={hasDb} />
        );
      })}

      {orphans.length > 0 && filterRows(orphans).length > 0 && (
        <ThresholdGroupCard
          meta={{
            key: "sleep_event",
            label: "Khác (chưa phân loại)",
            description: "Key chưa khai báo trong thresholdMeta.ts — cập nhật metadata để gom nhóm.",
            unit: "—",
          }}
          rows={filterRows(orphans)}
          hasDb={hasDb}
        />
      )}

      {hasDb && diffOnly && totalDiff === 0 && (
        <Card>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)" }}>
            Mọi ngưỡng đều khớp với fallback — DB không ghi đè giá trị nào.
          </p>
        </Card>
      )}
    </div>
  );
}

// ── Group card ──────────────────────────────────────────────────────────

function ThresholdGroupCard({
  meta,
  rows,
  hasDb,
}: {
  meta: ThresholdGroupMeta;
  rows: GroupedRow[];
  hasDb: boolean;
}) {
  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap" }}>
          <strong>{meta.label}</strong>
          <span style={unitBadgeStyle}>{meta.unit}</span>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{meta.description}</span>
        </div>
      }
    >
      <div style={{ overflowX: "auto" }}>
        <table style={tableStyle}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-default)" }}>
              <th style={thStyle}>Ngưỡng</th>
              <th style={thStyle}>Mô tả</th>
              <th style={{ ...thStyle, textAlign: "right" }}>{hasDb ? "Ngày · Fallback" : "Ngày"}</th>
              {hasDb && <th style={{ ...thStyle, textAlign: "right" }}>Ngày · DB</th>}
              <th style={{ ...thStyle, textAlign: "right" }}>{hasDb ? "Đêm · Fallback" : "Đêm"}</th>
              {hasDb && <th style={{ ...thStyle, textAlign: "right" }}>Đêm · DB</th>}
              {hasDb && <th style={thStyle}>Trạng thái</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <ThresholdRow key={row.key} row={row} unit={meta.unit} hasDb={hasDb} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ThresholdRow({
  row,
  unit,
  hasDb,
}: {
  row: GroupedRow;
  unit: string;
  hasDb: boolean;
}) {
  const status = !hasDb
    ? null
    : row.dayDiff || row.nightDiff
      ? "differ"
      : "match";

  return (
    <tr style={{ borderBottom: "1px solid var(--border-default)" }}>
      <td style={tdStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <SeverityDot severity={row.info.severity} />
          <span style={{ color: "var(--text-primary)" }}>{row.info.label}</span>
        </div>
        <div style={keyHintStyle}>{row.key}</div>
      </td>
      <td style={{ ...tdStyle, color: "var(--text-secondary)", fontSize: "12px", lineHeight: 1.5 }}>
        {row.info.hint}
      </td>
      <td style={tdValueStyle}>{formatValue(row.fbDay, unit)}</td>
      {hasDb && (
        <td
          style={{
            ...tdValueStyle,
            color: row.dayDiff ? "var(--accent-cyan)" : undefined,
            fontWeight: row.dayDiff ? 600 : undefined,
          }}
          title={row.dayDiff ? "Giá trị DB ghi đè fallback" : undefined}
        >
          {formatValue(row.dbDay, unit)}
        </td>
      )}
      <td style={tdValueStyle}>{formatValue(row.fbNight, unit)}</td>
      {hasDb && (
        <td
          style={{
            ...tdValueStyle,
            color: row.nightDiff ? "var(--accent-cyan)" : undefined,
            fontWeight: row.nightDiff ? 600 : undefined,
          }}
          title={row.nightDiff ? "Giá trị DB ghi đè fallback" : undefined}
        >
          {formatValue(row.dbNight, unit)}
        </td>
      )}
      {hasDb && (
        <td style={tdStyle}>
          {status === "differ" ? (
            <Pill tone="cyan">DB ghi đè</Pill>
          ) : status === "match" ? (
            <Pill tone="green">Khớp</Pill>
          ) : (
            <Pill tone="neutral">—</Pill>
          )}
        </td>
      )}
    </tr>
  );
}

function formatValue(value: number | undefined, unit: string): string {
  if (value === undefined || value === null) return "—";
  if (unit === "—" || !unit) return String(value);
  return `${value} ${unit}`;
}

// ── Atoms ───────────────────────────────────────────────────────────────

function SeverityDot({ severity }: { severity: ThresholdSeverity }) {
  const color =
    severity === "critical"
      ? "var(--severity-critical, #ef4444)"
      : severity === "warning"
        ? "var(--severity-warning, #f59e0b)"
        : "var(--text-muted)";
  const label =
    severity === "critical" ? "Nguy hiểm" : severity === "warning" ? "Cảnh báo" : "Thông tin";
  return (
    <span
      aria-label={label}
      title={label}
      style={{
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        background: color,
        display: "inline-block",
        flexShrink: 0,
      }}
    />
  );
}

type PillTone = "neutral" | "green" | "cyan" | "amber";

function Pill({ tone, children }: { tone: PillTone; children: React.ReactNode }) {
  const palette: Record<PillTone, { fg: string; bg: string; border: string }> = {
    neutral: {
      fg: "var(--text-secondary)",
      bg: "var(--bg-elevated)",
      border: "var(--border-default)",
    },
    green: {
      fg: "var(--severity-normal, #22c55e)",
      bg: "rgba(34,197,94,0.10)",
      border: "rgba(34,197,94,0.30)",
    },
    cyan: {
      fg: "var(--accent-cyan)",
      bg: "rgba(34,211,238,0.10)",
      border: "rgba(34,211,238,0.30)",
    },
    amber: {
      fg: "var(--severity-warning, #f59e0b)",
      bg: "rgba(245,158,11,0.10)",
      border: "rgba(245,158,11,0.30)",
    },
  };
  const c = palette[tone];
  return (
    <span
      style={{
        fontSize: "11px",
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: "var(--radius-full)",
        color: c.fg,
        background: c.bg,
        border: `1px solid ${c.border}`,
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

function ThresholdSourceBadge({ source }: { source: string }) {
  if (source === "db") return <Pill tone="green">Đọc từ DB</Pill>;
  if (source === "fallback") return <Pill tone="amber">Fallback (vitals_service)</Pill>;
  return <Pill tone="neutral">{source}</Pill>;
}

// ── Styles ──────────────────────────────────────────────────────────────

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "13px",
};

const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "8px",
  color: "var(--text-secondary)",
  fontWeight: 600,
  fontSize: "12px",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const tdStyle: CSSProperties = {
  padding: "8px",
  color: "var(--text-primary)",
  verticalAlign: "top",
};

const tdValueStyle: CSSProperties = {
  padding: "8px",
  color: "var(--text-primary)",
  fontFamily: "var(--font-mono)",
  textAlign: "right",
  whiteSpace: "nowrap",
  verticalAlign: "top",
};

const keyHintStyle: CSSProperties = {
  fontSize: "11px",
  color: "var(--text-muted)",
  fontFamily: "var(--font-mono)",
  marginTop: "2px",
};

const legendTextStyle: CSSProperties = {
  margin: 0,
  fontSize: "13px",
  color: "var(--text-secondary)",
  lineHeight: 1.6,
};

const diffToggleStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  marginTop: "10px",
  fontSize: "13px",
  color: "var(--text-secondary)",
  cursor: "pointer",
  userSelect: "none",
};

const unitBadgeStyle: CSSProperties = {
  fontSize: "11px",
  fontFamily: "var(--font-mono)",
  color: "var(--text-secondary)",
  padding: "1px 6px",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-sm)",
};
