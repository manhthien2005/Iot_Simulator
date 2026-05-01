// ---------------------------------------------------------------------------
// Module H Block 2 — Vietnamese labels for MotionLatest enums.
//
// `activityState` and `fallVariant` come straight from the BE persona
// engine as English snake_case tokens (`idle`, `walking`, `fall`,
// `recovery`, `fall_brief`, `fall_no_response`, …).  Operators don't
// read those.  These maps Vietnamize them for the motion preview pill
// and the technical-detail strip; unknown tokens fall back to the raw
// string so we never silently drop signal.
// ---------------------------------------------------------------------------

import type { ScenarioSeverity } from "../types/scenario";

export interface ActivityLabel {
  /** Display copy shown to the operator. */
  display: string;
  /** Tone applied to the badge (matches `<Badge severity>`). */
  severity: "normal" | "warning" | "critical" | "offline" | "info";
}

const ACTIVITY_LABELS: Record<string, ActivityLabel> = {
  idle: { display: "Nghỉ ngơi", severity: "normal" },
  resting: { display: "Nghỉ ngơi", severity: "normal" },
  walking: { display: "Đi bộ", severity: "normal" },
  running: { display: "Chạy", severity: "info" },
  exercising: { display: "Vận động", severity: "info" },
  sleeping: { display: "Đang ngủ", severity: "info" },
  recovery: { display: "Đang hồi phục", severity: "warning" },
  fall: { display: "TÉ NGÃ", severity: "critical" },
  unknown: { display: "Không rõ", severity: "offline" },
};

const FALL_VARIANT_LABELS: Record<string, string> = {
  fall_brief: "Té ngã nhẹ",
  fall_no_response: "Không phản hồi",
  confirmed: "Té ngã xác nhận",
  false_fall: "Té ngã giả",
  // Module FA additions
  slip_recovery: "Trượt — tự đứng dậy",
  fall_from_bed: "Té khỏi giường",
  // Persona-engine internal variants (rarely shown directly but mapped
  // here so the FE doesn't render the raw token if BE leaks them).
  fall_1: "Té ngã (chuẩn)",
  fall_generic: "Té ngã (chung)",
};

const TRACE_LABELS: Record<string, string> = {
  accelMag: "Gia tốc tổng |a|",
  accelX: "Gia tốc trục X",
  accelY: "Gia tốc trục Y",
  accelZ: "Gia tốc trục Z",
  gyroX: "Vận tốc góc trục X",
  gyroY: "Vận tốc góc trục Y",
  gyroZ: "Vận tốc góc trục Z",
};

/** Return a Vietnamese label + severity for an `activityState` token. */
export function describeActivity(activityState: string | null | undefined): ActivityLabel {
  if (!activityState) return ACTIVITY_LABELS.unknown;
  const key = activityState.trim().toLowerCase();
  return ACTIVITY_LABELS[key] ?? { display: activityState, severity: "info" };
}

/** Return a Vietnamese label for a fall variant, or null if unknown. */
export function describeFallVariant(variant: string | null | undefined): string | null {
  if (!variant) return null;
  const key = variant.trim().toLowerCase();
  return FALL_VARIANT_LABELS[key] ?? variant;
}

/** Return the Vietnamese trace label or the raw token if unmapped. */
export function describeTrace(traceKey: string): string {
  return TRACE_LABELS[traceKey] ?? traceKey;
}

/**
 * Threshold (m/s²) above which the peak gets a warning icon.  Picked to
 * roughly match the BE's `fall_detected` floor — operator-facing only,
 * the BE still owns the actual detection logic.
 */
export const PEAK_ACCEL_WARN_THRESHOLD = 20;

/**
 * Convenience for callers that want to colour the peak metric.  Returns
 * a severity level matching `<Badge severity>`.
 */
export function describePeakSeverity(peak: number): ScenarioSeverity {
  if (peak >= PEAK_ACCEL_WARN_THRESHOLD) return "critical";
  if (peak >= PEAK_ACCEL_WARN_THRESHOLD * 0.6) return "warning";
  return "normal";
}
