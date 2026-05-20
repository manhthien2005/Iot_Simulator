import { type ChangeEvent, type ReactNode } from "react";
import { HelpCircle } from "lucide-react";
import { Tooltip } from "../../ui/Tooltip";

// ---------------------------------------------------------------------------
// RuntimeKnobField — Module H.1
//
// One editable knob row on the Settings page.  Wraps a labelled number input
// with:
//   * tooltip explaining the parameter (uses the existing portal `<Tooltip/>`)
//   * inline unit suffix (`giây`, `lần`)
//   * dynamic helper text computed from the current value
//   * soft warning state when the value falls outside `recommended`
//   * hard error state when an external cross-field validator rejects
//
// Bounds policy: `min`/`max` are the *absolute* limits enforced by the BE
// schema.  `recommended.min`/`recommended.max` are the soft guard rails — the
// FE flags values outside them but still allows save.  See plan §Phase 2.
// ---------------------------------------------------------------------------

export interface RuntimeKnobBounds {
  /** Absolute minimum accepted by the BE Pydantic schema. */
  min: number;
  /** Absolute maximum accepted by the BE Pydantic schema. */
  max: number;
  /** Step for the `<input type="number">`. */
  step: number;
  /** Soft range — values outside trigger the warning state but still save. */
  recommended: { min: number; max: number };
}

interface RuntimeKnobFieldProps {
  /** Vietnamese label shown next to the input. */
  label: string;
  /** Tooltip body (string or rich node). */
  tooltip: ReactNode;
  /** Unit suffix overlaid on the input ("giây", "lần"). */
  unit: string;
  /** Current input value (kept as string so users can type freely). */
  value: string;
  onChange: (next: string) => void;
  /** Bounds + recommended range. */
  bounds: RuntimeKnobBounds;
  /** Helper text computed from the value (e.g. "12 mẫu / phút"). */
  helper: ReactNode;
  /** Hard cross-field error — overrides the soft warning state. */
  error?: string | null;
  /** Disable input (e.g. while save is in flight). */
  disabled?: boolean;
  /** HTML id, generated from `label` if omitted. */
  id?: string;
}

function isInsideRecommended(raw: string, bounds: RuntimeKnobBounds): boolean {
  const n = Number(raw);
  if (!Number.isFinite(n)) return true; // empty/typing — don't shout warnings yet
  return n >= bounds.recommended.min && n <= bounds.recommended.max;
}

export function RuntimeKnobField({
  label,
  tooltip,
  unit,
  value,
  onChange,
  bounds,
  helper,
  error,
  disabled,
  id,
}: RuntimeKnobFieldProps) {
  const inputId = id ?? `knob-${label.replace(/\s+/g, "-").toLowerCase()}`;
  const hasError = Boolean(error);
  const isWarning = !hasError && !isInsideRecommended(value, bounds);

  const tone = hasError
    ? {
        border: "var(--severity-critical-border)",
        bg: "var(--severity-critical-bg)",
        accent: "var(--severity-critical)",
        helperColor: "var(--severity-critical)",
        inputBorder: "var(--severity-critical)",
      }
    : isWarning
      ? {
          border: "var(--severity-warning-border)",
          bg: "var(--severity-warning-bg)",
          accent: "var(--severity-warning)",
          helperColor: "var(--severity-warning)",
          inputBorder: "var(--severity-warning)",
        }
      : {
          border: "var(--border-default)",
          bg: "var(--bg-base)",
          accent: "var(--text-secondary)",
          helperColor: "var(--text-secondary)",
          inputBorder: "var(--border-default)",
        };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange(event.target.value);
  };

  return (
    <div
      style={{
        display: "grid",
        gap: "6px",
        padding: "12px 14px",
        border: `1px solid ${tone.border}`,
        borderRadius: "var(--radius-md)",
        background: tone.bg,
        transition:
          "border-color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <label
          htmlFor={inputId}
          style={{ fontSize: "12.5px", fontWeight: 600, color: "var(--text-primary)" }}
        >
          {label}
        </label>
        <Tooltip content={tooltip} placement="top">
          <button
            type="button"
            aria-label={`Giải thích ${label}`}
            style={{
              width: "18px",
              height: "18px",
              borderRadius: "50%",
              border: "none",
              background: "var(--bg-active)",
              color: "var(--text-secondary)",
              display: "inline-grid",
              placeItems: "center",
              padding: 0,
              cursor: "help",
            }}
          >
            <HelpCircle size={12} strokeWidth={2} />
          </button>
        </Tooltip>
        <span
          style={{
            marginLeft: "auto",
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: "var(--text-muted)",
          }}
        >
          khuyến nghị {bounds.recommended.min}–{bounds.recommended.max}
        </span>
      </div>

      <div style={{ position: "relative" }}>
        <input
          id={inputId}
          type="number"
          step={bounds.step}
          min={bounds.min}
          max={bounds.max}
          value={value}
          onChange={handleChange}
          disabled={disabled}
          aria-invalid={hasError}
          style={{
            width: "100%",
            background: "var(--bg-elevated)",
            border: `1px solid ${tone.inputBorder}`,
            borderRadius: "var(--radius-md)",
            color: "var(--text-primary)",
            padding: "8px 56px 8px 12px",
            fontSize: "13px",
            fontFamily: "var(--font-mono)",
            outline: "none",
            transition: "border-color var(--duration-fast) var(--ease-default)",
          }}
        />
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            right: "12px",
            top: "50%",
            transform: "translateY(-50%)",
            fontSize: "12px",
            color: "var(--text-muted)",
            fontFamily: "var(--font-mono)",
            pointerEvents: "none",
          }}
        >
          {unit}
        </span>
      </div>

      <div style={{ fontSize: "12px", color: tone.helperColor, lineHeight: 1.5 }}>
        {hasError ? error : helper}
      </div>
    </div>
  );
}
