import type { ReactNode } from "react";
import { CheckCircle2, Clock, ShieldAlert, Zap } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import { fallSeverityPalette, fallSeverityShortLabel } from "../../../utils/severity";
import {
  FALL_VARIANT_CATALOGUE,
  type FallVariantId,
  type FallVariantSpec,
} from "../../../types/fall";

interface Props {
  disabled: boolean;
  pendingVariant: FallVariantId | null;
  onPick: (variant: FallVariantSpec) => void;
  onHover: (id: FallVariantId | null) => void;
  focalVariantSpec: FallVariantSpec | null;
}

export function VariantPickerCard({ disabled, pendingVariant, onPick, onHover, focalVariantSpec }: Props) {
  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <strong>Kịch bản té ngã ({FALL_VARIANT_CATALOGUE.length})</strong>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Hover/click để xem chi tiết</span>
        </div>
      }
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "8px" }}>
        {FALL_VARIANT_CATALOGUE.map((variant) => (
          <VariantButton
            key={variant.id}
            variant={variant}
            disabled={disabled}
            pending={pendingVariant === variant.id}
            onPick={onPick}
            onHover={onHover}
          />
        ))}
      </div>
      <div style={{ marginTop: "12px" }}>
        <VariantDetailCard variant={focalVariantSpec} />
      </div>
    </Card>
  );
}

function VariantButton({
  variant,
  disabled,
  pending,
  onPick,
  onHover,
}: {
  variant: FallVariantSpec;
  disabled: boolean;
  pending: boolean;
  onPick: (v: FallVariantSpec) => void;
  onHover: (id: FallVariantId | null) => void;
}) {
  const palette = fallSeverityPalette(variant.severity);
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onPick(variant)}
      onMouseEnter={() => onHover(variant.id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(variant.id)}
      onBlur={() => onHover(null)}
      style={{
        display: "grid",
        gap: "4px",
        textAlign: "left",
        padding: "12px",
        borderRadius: "var(--radius-md)",
        border: `1px solid ${palette.border}`,
        background: pending ? palette.bg : "var(--bg-elevated)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        transition: "background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
        color: "var(--text-primary)",
      }}
      aria-label={`${variant.label} — ${variant.subtitle}`}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <strong style={{ fontSize: "13px" }}>{pending ? "Đang gửi…" : variant.label}</strong>
        <Badge severity={variant.severity}>{fallSeverityShortLabel(variant.severity)}</Badge>
      </div>
      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{variant.subtitle}</span>
    </button>
  );
}

function VariantDetailCard({ variant }: { variant: FallVariantSpec | null }) {
  if (!variant) {
    return (
      <div
        style={{
          padding: "10px 12px",
          fontSize: "12px",
          color: "var(--text-muted)",
          background: "var(--bg-base)",
          border: "1px dashed var(--border-default)",
          borderRadius: "var(--radius-md)",
        }}
      >
        Hover hoặc click một kịch bản để xem chi tiết policy + countdown.
      </div>
    );
  }
  return (
    <div
      style={{
        display: "grid",
        gap: "8px",
        padding: "10px 12px",
        background: "var(--bg-base)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <strong style={{ fontSize: "13px" }}>{variant.label}</strong>
      <p style={{ margin: 0, fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
        {variant.description}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
        <PolicyChip
          icon={<Clock size={12} />}
          label={variant.countdownSec === 0 ? "Không countdown" : `Countdown ${variant.countdownSec}s`}
        />
        <PolicyChip
          icon={<Zap size={12} />}
          label={variant.pushesAlert ? "Đẩy alert webhook" : "Không đẩy alert"}
          tone={variant.pushesAlert ? "warning" : "normal"}
        />
        {variant.autoResolve && (
          <PolicyChip icon={<CheckCircle2 size={12} />} label="Tự huỷ countdown" tone="normal" />
        )}
        <PolicyChip
          icon={<ShieldAlert size={12} />}
          label={variant.allowsCancel ? "Cho phép 'Tôi ổn'" : "Không cho huỷ"}
          tone={variant.allowsCancel ? "normal" : "critical"}
        />
      </div>
    </div>
  );
}

function PolicyChip({
  icon,
  label,
  tone = "normal",
}: {
  icon: ReactNode;
  label: string;
  tone?: "normal" | "warning" | "critical" | "offline";
}) {
  const palette = fallSeverityPalette(tone);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "3px 8px",
        fontSize: "11px",
        borderRadius: "var(--radius-full)",
        border: `1px solid ${palette.border}`,
        background: "var(--bg-elevated)",
        color: palette.text,
      }}
    >
      {icon}
      {label}
    </span>
  );
}
