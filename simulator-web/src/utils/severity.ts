// ---------------------------------------------------------------------------
// Fall Lab — severity palette + AI label helpers
// ---------------------------------------------------------------------------

export type FallSeverityTone = "normal" | "warning" | "critical" | "offline";

export interface SeverityPalette {
  bg: string;
  text: string;
  border: string;
}

export function fallSeverityPalette(severity: FallSeverityTone): SeverityPalette {
  switch (severity) {
    case "critical":
      return { bg: "var(--severity-critical-bg)", text: "var(--severity-critical)", border: "var(--severity-critical-border)" };
    case "warning":
      return { bg: "var(--severity-warning-bg)", text: "var(--severity-warning)", border: "var(--severity-warning-border)" };
    case "offline":
      return { bg: "var(--severity-offline-bg)", text: "var(--text-muted)", border: "var(--severity-offline-border)" };
    case "normal":
    default:
      return { bg: "var(--severity-normal-bg)", text: "var(--severity-normal)", border: "var(--severity-normal-border)" };
  }
}

export function aiLabelText(label: string): string {
  switch (label) {
    case "normal": return "Bình thường";
    case "possible_fall": return "Có thể té ngã";
    case "likely_fall": return "Khả năng té ngã cao";
    case "critical_fall": return "Té ngã nghiêm trọng";
    default: return String(label);
  }
}

export function aiStatusLabel(status: string): string {
  switch (status) {
    case "offline": return "AI offline";
    case "no_window": return "Không đủ mẫu";
    case "skipped": return "Bỏ qua AI";
    case "ok": return "AI sẵn sàng";
    default: return status;
  }
}

export function fallSeverityShortLabel(severity: "normal" | "warning" | "critical"): string {
  if (severity === "critical") return "critical";
  if (severity === "warning") return "warning";
  return "safe";
}

export function fallSeverityRowBg(sev: string): string {
  if (sev === "critical") return "color-mix(in srgb, var(--severity-critical) 6%, transparent)";
  if (sev === "warning") return "color-mix(in srgb, var(--severity-warning) 6%, transparent)";
  return "rgba(255,255,255,0.02)";
}

export function fallSeverityRowColor(sev: string): string {
  if (sev === "critical") return "var(--severity-critical)";
  if (sev === "warning") return "var(--severity-warning)";
  return "var(--border-default)";
}

// ---------------------------------------------------------------------------

export function getVitalSeverity(
  vital: "heartRate" | "spo2" | "temperature" | "bloodPressureSys",
  value: number | null | undefined
): "normal" | "warning" | "critical" {
  if (value == null) return "normal";
  if (vital === "heartRate") {
    if (value < 40 || value > 180) return "critical";
    if (value < 50 || value > 100) return "warning";
    return "normal";
  }
  if (vital === "spo2") {
    if (value < 85) return "critical";
    if (value < 90) return "warning";
    return "normal";
  }
  if (vital === "temperature") {
    if (value < 35 || value > 40) return "critical";
    if (value > 37.5) return "warning";
    return "normal";
  }
  if (value > 180 || value < 80) return "critical";
  if (value > 140 || value < 90) return "warning";
  return "normal";
}
