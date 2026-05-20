import { useState, type CSSProperties } from "react";
import { ChevronDown, ChevronRight, Code, FileWarning } from "lucide-react";
import { Card } from "../ui/Card";
import { Tabs } from "../ui/Tabs";
import type { SimulatorSettingsResponse } from "../../types/settings";
import { JsonAutoView } from "./diagnostics/JsonAutoView";
import {
  RULES_SECTIONS,
  FALL_SECTIONS,
  buildOrderedSections,
  isMetaField,
  type ConfigSection,
} from "./diagnostics/triggerConfigSchema";

// ---------------------------------------------------------------------------
// TriggerConfigPanel — Module F.10 (refactor 2026-05).
//
// Render `rules_config.json` + `fall_pipeline_wrist_config.json` dưới dạng
// structured cards: header (version/name/description) + accordion theo từng
// section đã khai báo trong `triggerConfigSchema.ts`. Operator vẫn có thể
// mở "Xem JSON gốc" để xem nguyên file khi cần debug.
//
// Read-only: file là source of truth trên disk; sửa rồi restart simulator.
// ---------------------------------------------------------------------------

interface TriggerConfigPanelProps {
  data: SimulatorSettingsResponse;
}

type ConfigTab = "rules" | "fall";

const TAB_ITEMS = [
  { key: "rules" as const, label: "Health Rules" },
  { key: "fall" as const, label: "Fall Pipeline" },
];

export function TriggerConfigPanel({ data }: TriggerConfigPanelProps) {
  const [tab, setTab] = useState<ConfigTab>("rules");
  const json = tab === "rules" ? data.rules_config : data.fall_config;
  const schema = tab === "rules" ? RULES_SECTIONS : FALL_SECTIONS;
  const fileLabel =
    tab === "rules"
      ? "pre_model_trigger/health_rules/rules_config.json"
      : "pre_model_trigger/fall/fall_pipeline_wrist_config.json";

  return (
    <div style={{ display: "grid", gap: "12px" }}>
      <Card
        header={
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <strong>Pre-Model Trigger Config</strong>
            <span style={readonlyBadgeStyle}>
              <FileWarning size={11} /> Read-only
            </span>
          </div>
        }
      >
        <p style={legendTextStyle}>
          Mô phỏng nạp 2 file JSON khi khởi động: <strong>Health Rules</strong> điều phối escalation theo
          vitals, <strong>Fall Pipeline</strong> cấu hình mô-đun phát hiện té ngã. Trang này chia file thành
          từng phần theo nghĩa nghiệp vụ kèm mô tả ngắn — sửa file trên disk rồi <em>restart simulator</em>{" "}
          để áp dụng thay đổi.
        </p>
        <Tabs items={TAB_ITEMS} activeKey={tab} onChange={(key) => setTab(key as ConfigTab)} />
      </Card>

      {json === null ? (
        <Card>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)" }}>
            Không tìm thấy file <code>{fileLabel}</code> — kiểm tra <code>pre_model_trigger/</code> trong
            simulator.
          </p>
        </Card>
      ) : (
        <ConfigContent json={json} schema={schema} fileLabel={fileLabel} />
      )}
    </div>
  );
}

function ConfigContent({
  json,
  schema,
  fileLabel,
}: {
  json: Record<string, unknown>;
  schema: ConfigSection[];
  fileLabel: string;
}) {
  const ordered = buildOrderedSections(json, schema);
  const version = typeof json.version === "string" ? json.version : null;
  const name = typeof json.name === "string" ? json.name : null;
  const description = typeof json.description === "string" ? json.description : null;

  return (
    <>
      {(version || name || description) && (
        <Card>
          <div style={{ display: "grid", gap: "6px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              {name && <strong style={{ fontSize: "14px" }}>{name}</strong>}
              {version && (
                <span style={versionPillStyle}>v{version}</span>
              )}
              <span style={fileLabelStyle}>{fileLabel}</span>
            </div>
            {description && (
              <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {description}
              </p>
            )}
          </div>
        </Card>
      )}

      <div style={{ display: "grid", gap: "10px" }}>
        {ordered.map((section) => {
          if (isMetaField(section.key)) return null;
          const value = json[section.key];
          if (value === undefined) return null;
          return (
            <SectionAccordion key={section.key} section={section} value={value} />
          );
        })}
      </div>

      <RawJsonCard json={json} fileLabel={fileLabel} />
    </>
  );
}

function SectionAccordion({
  section,
  value,
}: {
  section: ConfigSection;
  value: unknown;
}) {
  const [open, setOpen] = useState(false);
  const Icon = section.icon;
  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={accordionHeaderStyle}
        aria-expanded={open}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          {Icon && <Icon size={16} />}
          <span style={{ fontWeight: 600, fontSize: "13px" }}>{section.label}</span>
          <span style={sectionKeyStyle}>{section.key}</span>
        </span>
      </button>
      {section.desc && (
        <p style={sectionDescStyle}>{section.desc}</p>
      )}
      {open && (
        <div style={{ marginTop: "10px" }}>
          <JsonAutoView value={value} />
        </div>
      )}
    </Card>
  );
}

function RawJsonCard({
  json,
  fileLabel,
}: {
  json: Record<string, unknown>;
  fileLabel: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={accordionHeaderStyle}
        aria-expanded={open}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <Code size={16} />
          <span style={{ fontWeight: 600, fontSize: "13px" }}>Xem JSON gốc</span>
          <span style={sectionKeyStyle}>{fileLabel}</span>
        </span>
      </button>
      {open && (
        <pre style={rawJsonStyle}>{JSON.stringify(json, null, 2)}</pre>
      )}
    </Card>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────

const legendTextStyle: CSSProperties = {
  margin: "0 0 12px 0",
  fontSize: "13px",
  color: "var(--text-secondary)",
  lineHeight: 1.6,
};

const readonlyBadgeStyle: CSSProperties = {
  fontSize: "11px",
  fontWeight: 600,
  padding: "2px 8px",
  borderRadius: "var(--radius-full)",
  color: "var(--severity-warning, #f59e0b)",
  background: "rgba(245,158,11,0.10)",
  border: "1px solid rgba(245,158,11,0.30)",
  display: "inline-flex",
  alignItems: "center",
  gap: "4px",
};

const versionPillStyle: CSSProperties = {
  fontSize: "11px",
  fontFamily: "var(--font-mono)",
  padding: "2px 8px",
  borderRadius: "var(--radius-full)",
  color: "var(--accent-cyan)",
  background: "rgba(34,211,238,0.10)",
  border: "1px solid rgba(34,211,238,0.30)",
};

const fileLabelStyle: CSSProperties = {
  fontSize: "11px",
  fontFamily: "var(--font-mono)",
  color: "var(--text-muted)",
};

const sectionKeyStyle: CSSProperties = {
  fontSize: "11px",
  fontFamily: "var(--font-mono)",
  color: "var(--text-muted)",
  marginLeft: "auto",
};

const sectionDescStyle: CSSProperties = {
  margin: "6px 0 0 24px",
  fontSize: "12px",
  color: "var(--text-secondary)",
  lineHeight: 1.5,
};

const accordionHeaderStyle: CSSProperties = {
  width: "100%",
  background: "none",
  border: "none",
  color: "var(--text-primary)",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  gap: "6px",
  padding: 0,
  textAlign: "left",
};

const rawJsonStyle: CSSProperties = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "12px",
  fontSize: "12px",
  fontFamily: "var(--font-mono)",
  margin: "10px 0 0 0",
  overflow: "auto",
  maxHeight: "500px",
};
