import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// RuntimePresetSelect — Module H.2
//
// Quick-pick presets for the three runtime knobs.  Selecting a preset only
// fills the form fields; user still has to press "Lưu thay đổi" to persist.
// The "Tuỳ chỉnh" pseudo-preset matches when none of the canonical presets
// equals the current values — purely a label, clicking it is a no-op.
// ---------------------------------------------------------------------------

export interface RuntimePresetValues {
  tick_interval_seconds: number;
  push_interval_seconds: number;
  sleep_speed_factor: number;
}

export interface RuntimePreset {
  id: "demo" | "realistic" | "stress";
  name: string;
  hint: string;
  values: RuntimePresetValues;
}

export const RUNTIME_PRESETS: RuntimePreset[] = [
  {
    id: "demo",
    name: "Demo nhanh",
    hint: "tick 1s · push 5s · sleep 60×",
    values: { tick_interval_seconds: 1.0, push_interval_seconds: 5, sleep_speed_factor: 60 },
  },
  {
    id: "realistic",
    name: "Realistic",
    hint: "tick 5s · push 30s · sleep 60×",
    values: { tick_interval_seconds: 5.0, push_interval_seconds: 30, sleep_speed_factor: 60 },
  },
  {
    id: "stress",
    name: "Stress test",
    hint: "tick 0.5s · push 1s · sleep 1×",
    values: { tick_interval_seconds: 0.5, push_interval_seconds: 1, sleep_speed_factor: 1 },
  },
];

interface RuntimePresetSelectProps {
  current: RuntimePresetValues;
  onPick: (values: RuntimePresetValues) => void;
  disabled?: boolean;
}

function matchesPreset(current: RuntimePresetValues, preset: RuntimePreset): boolean {
  return (
    current.tick_interval_seconds === preset.values.tick_interval_seconds &&
    current.push_interval_seconds === preset.values.push_interval_seconds &&
    current.sleep_speed_factor === preset.values.sleep_speed_factor
  );
}

export function RuntimePresetSelect({ current, onPick, disabled }: RuntimePresetSelectProps) {
  const activePresetId = RUNTIME_PRESETS.find((p) => matchesPreset(current, p))?.id ?? "custom";

  return (
    <div>
      <div
        style={{
          fontSize: "11.5px",
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: "6px",
        }}
      >
        Preset
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px" }}>
        {RUNTIME_PRESETS.map((preset) => (
          <PresetCard
            key={preset.id}
            name={preset.name}
            hint={preset.hint}
            isActive={activePresetId === preset.id}
            disabled={disabled}
            onClick={() => onPick(preset.values)}
          />
        ))}
        <PresetCard
          name="Tuỳ chỉnh"
          hint={activePresetId === "custom" ? "đang chỉnh tay…" : "khớp 1 preset bên trên"}
          isActive={activePresetId === "custom"}
          disabled
          onClick={() => undefined}
        />
      </div>
    </div>
  );
}

interface PresetCardProps {
  name: string;
  hint: string;
  isActive: boolean;
  disabled?: boolean;
  onClick: () => void;
}

function PresetCard({ name, hint, isActive, disabled, onClick }: PresetCardProps) {
  const style: CSSProperties = {
    textAlign: "left",
    padding: "10px 12px",
    border: `1px solid ${isActive ? "var(--accent-cyan)" : "var(--border-default)"}`,
    borderRadius: "var(--radius-md)",
    background: isActive ? "var(--accent-cyan-bg)" : "var(--bg-base)",
    color: "var(--text-primary)",
    cursor: disabled ? "default" : "pointer",
    opacity: disabled && !isActive ? 0.55 : 1,
    display: "grid",
    gap: "4px",
    transition:
      "border-color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default)",
  };
  return (
    <button type="button" onClick={onClick} disabled={disabled} style={style}>
      <span style={{ fontSize: "12.5px", fontWeight: 700 }}>{name}</span>
      <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{hint}</span>
    </button>
  );
}
