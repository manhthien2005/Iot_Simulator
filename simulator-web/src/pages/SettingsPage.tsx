import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Save } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorCard } from "../components/ui/ErrorCard";
import { fetchSettings, updateRuntimeConfig } from "../services/settingsApi";
import type { RuntimeConfigUpdate, SimulatorSettingsResponse } from "../types/settings";
import { notify } from "../utils/toast";

/* ── Threshold label mapping ────────────────────────────────────────── */

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

/* ── Section: Runtime Config (editable) ─────────────────────────────── */

function RuntimeSection({
  data,
  onSaved,
}: {
  data: SimulatorSettingsResponse;
  onSaved: () => void;
}) {
  const [tickInterval, setTickInterval] = useState(String(data.runtime.tick_interval_seconds));
  const [pushInterval, setPushInterval] = useState(String(data.runtime.push_interval_seconds));
  const [sleepSpeed, setSleepSpeed] = useState(String(data.runtime.sleep_speed_factor));

  const mutation = useMutation({
    mutationFn: (body: RuntimeConfigUpdate) => updateRuntimeConfig(body),
    onSuccess: () => {
      notify.success("Cập nhật cấu hình runtime thành công.");
      onSaved();
    },
    onError: () => {
      notify.error("Lỗi khi cập nhật cấu hình runtime.");
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate({
      tick_interval_seconds: Number(tickInterval),
      push_interval_seconds: Number(pushInterval),
      sleep_speed_factor: Number(sleepSpeed),
    });
  }

  return (
    <Card header={<strong>Simulator Runtime</strong>}>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Tick Interval (giây)</span>
          <Input type="number" step="0.1" min="0.1" max="60" value={tickInterval} onChange={(e) => setTickInterval(e.target.value)} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Push Interval (giây)</span>
          <Input type="number" step="1" min="1" max="300" value={pushInterval} onChange={(e) => setPushInterval(e.target.value)} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Sleep Speed Factor</span>
          <Input type="number" step="1" min="1" max="3600" value={sleepSpeed} onChange={(e) => setSleepSpeed(e.target.value)} />
        </label>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Health Backend URL (read-only)</span>
          <Input value={data.runtime.health_backend_url} readOnly style={{ opacity: 0.6 }} />
        </div>
        <div style={{ alignSelf: "flex-start", marginTop: "4px" }}>
          <Button type="submit" disabled={mutation.isPending}>
            <Save size={14} style={{ marginRight: "6px" }} />
            {mutation.isPending ? "Đang lưu…" : "Lưu thay đổi"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

/* ── Section: Thresholds (read-only, daytime vs sleep side-by-side) ── */

function ThresholdsSection({ data }: { data: SimulatorSettingsResponse }) {
  const allKeys = Array.from(
    new Set([...Object.keys(data.daytime_thresholds), ...Object.keys(data.sleep_thresholds)])
  );

  return (
    <Card header={<strong>Ngưỡng Vitals (Read-Only)</strong>}>
      <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "8px" }}>
        Ngưỡng sẽ được quản lý qua DB khi MASTER_PLAN Phase 3 hoàn tất. Hiện tại chỉ hiển thị.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-default)" }}>
              <th style={thStyle}>Chỉ số</th>
              <th style={thStyle}>Ban ngày</th>
              <th style={thStyle}>Ban đêm</th>
            </tr>
          </thead>
          <tbody>
            {allKeys.map((key) => (
              <tr key={key} style={{ borderBottom: "1px solid var(--border-default)" }}>
                <td style={tdStyle}>{labelFor(key)}</td>
                <td style={tdValueStyle}>{data.daytime_thresholds[key] ?? "—"}</td>
                <td style={tdValueStyle}>{data.sleep_thresholds[key] ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const thStyle = { textAlign: "left" as const, padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 };
const tdStyle = { padding: "6px 8px", color: "var(--text-primary)" };
const tdValueStyle = { padding: "6px 8px", color: "var(--text-primary)", fontFamily: "var(--font-mono)", textAlign: "right" as const };

/* ── Section: Pre-Model Trigger Config (collapsible JSON viewer) ───── */

function TriggerConfigSection({ data }: { data: SimulatorSettingsResponse }) {
  const [rulesOpen, setRulesOpen] = useState(false);
  const [fallOpen, setFallOpen] = useState(false);

  return (
    <Card header={<strong>Pre-Model Trigger Config (Read-Only)</strong>}>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <CollapsibleJson label="Rules Config" json={data.rules_config} isOpen={rulesOpen} onToggle={() => setRulesOpen(!rulesOpen)} />
        <CollapsibleJson label="Fall Pipeline Config" json={data.fall_config} isOpen={fallOpen} onToggle={() => setFallOpen(!fallOpen)} />
      </div>
    </Card>
  );
}

function CollapsibleJson({
  label,
  json,
  isOpen,
  onToggle,
}: {
  label: string;
  json: Record<string, unknown> | null;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        style={{
          background: "none",
          border: "none",
          color: "var(--text-primary)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "4px 0",
          fontSize: "13px",
          fontWeight: 500,
        }}
      >
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {label}
        {json === null && <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(không tìm thấy file)</span>}
      </button>
      {isOpen && json !== null && (
        <pre
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            padding: "12px",
            fontSize: "12px",
            fontFamily: "var(--font-mono)",
            overflow: "auto",
            maxHeight: "400px",
            marginTop: "4px",
          }}
        >
          {JSON.stringify(json, null, 2)}
        </pre>
      )}
    </div>
  );
}

/* ── Section: Feature Flags ─────────────────────────────────────────── */

function FeatureFlagsSection({ data }: { data: SimulatorSettingsResponse }) {
  return (
    <Card header={<strong>Feature Flags</strong>}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "4px 0" }}>
        <ToggleSwitch checked={data.feature_flags.use_db_thresholds} disabled />
        <span style={{ fontSize: "13px", color: "var(--text-primary)" }}>USE_DB_THRESHOLDS</span>
        <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          (Sẽ bật được khi MASTER_PLAN Phase 3 hoàn tất)
        </span>
      </div>
    </Card>
  );
}

function ToggleSwitch({ checked, disabled }: { checked: boolean; disabled?: boolean }) {
  return (
    <div
      style={{
        width: "36px",
        height: "20px",
        borderRadius: "10px",
        background: checked ? "var(--accent-cyan)" : "var(--bg-elevated)",
        border: "1px solid var(--border-default)",
        position: "relative",
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "background var(--duration-fast) var(--ease-default)",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: "14px",
          height: "14px",
          borderRadius: "50%",
          background: "var(--text-primary)",
          position: "absolute",
          top: "2px",
          left: checked ? "18px" : "2px",
          transition: "left var(--duration-fast) var(--ease-default)",
        }}
      />
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────── */

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: 30_000,
  });

  function handleRuntimeSaved() {
    queryClient.invalidateQueries({ queryKey: ["settings"] });
  }

  if (isLoading) {
    return (
      <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "16px" }}>
        <h1 className="page-title">Cài đặt</h1>
        <Skeleton style={{ height: "200px" }} />
        <Skeleton style={{ height: "300px" }} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div style={{ padding: "1.5rem" }}>
        <h1 className="page-title">Cài đặt</h1>
        <ErrorCard message={error instanceof Error ? error.message : "Không thể tải cài đặt."} />
      </div>
    );
  }

  return (
    <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "16px", maxWidth: "900px" }}>
      <h1 className="page-title">Cài đặt</h1>
      <p className="page-subtitle">Xem và điều chỉnh cấu hình của IoT Simulator.</p>

      <RuntimeSection data={data} onSaved={handleRuntimeSaved} />
      <ThresholdsSection data={data} />
      <TriggerConfigSection data={data} />
      <FeatureFlagsSection data={data} />
    </div>
  );
}
