import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "../../services/healthApi";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

type HealthKind = "runtime" | "backend" | "database";

function statusToSeverity(value: string, kind: HealthKind) {
  const normalized = value.trim().toLowerCase();

  if (["running", "connected", "healthy", "ok", "ready"].includes(normalized)) {
    return "normal" as const;
  }

  if (["idle", "degraded", "stale", "delayed", "syncing", "local-ok"].includes(normalized)) {
    return kind === "database" && normalized === "local-ok" ? "warning" : "warning";
  }

  if (["down", "failed", "error", "offline", "disconnected", "stopped", "unreachable"].includes(normalized)) {
    return "critical" as const;
  }

  return "info" as const;
}

export function HealthStatusPanel() {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15000,
  });

  return (
    <Card header={<strong>Sức khỏe hệ thống mô phỏng</strong>}>
      {data ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <Row label="Runtime" value={data.status ?? data.api} kind="runtime" />
          <Row label="Backend" value={data.backend ?? data.mqtt ?? "unknown"} kind="backend" />
          <Row label="DB" value={data.db} kind="database" />
          <Row label="Phiên bản" value={data.version} />
        </div>
      ) : (
        <span style={{ color: "var(--text-secondary)" }}>Đang kiểm tra trạng thái...</span>
      )}
    </Card>
  );
}

function Row(props: { label: string; value: string; kind?: HealthKind }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <span style={{ color: "var(--text-secondary)" }}>{props.label}</span>
      <Badge severity={statusToSeverity(props.value, props.kind ?? "runtime")}>{healthLabel(props.value, props.kind ?? "runtime")}</Badge>
    </div>
  );
}

function healthLabel(value: string, kind: HealthKind) {
  const normalized = value.trim().toLowerCase();

  if (kind === "runtime") {
    if (normalized === "running") return "đang chạy";
    if (normalized === "idle") return "rảnh";
    if (normalized === "stopped") return "đã dừng";
    if (normalized === "degraded") return "suy giảm";
  }

  if (kind === "backend") {
    if (normalized === "connected") return "kết nối";
    if (normalized === "disconnected") return "mất kết nối";
    if (normalized === "down") return "ngắt";
    if (normalized === "local-ok") return "cục bộ";
  }

  if (kind === "database") {
    if (normalized === "local-ok") return "cục bộ";
    if (normalized === "healthy" || normalized === "ok") return "ổn định";
    if (normalized === "failed") return "lỗi";
  }

  if (normalized === "unknown") return "không rõ";
  return value;
}
