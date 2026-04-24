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
