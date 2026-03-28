import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "../../services/healthApi";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

function statusToSeverity(value: string) {
  if (value === "running" || value === "connected" || value === "local-ok") return "normal" as const;
  if (value === "idle") return "warning" as const;
  return "critical" as const;
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
          <Row label="API" value={data.api} />
          <Row label="MQTT" value={data.mqtt} />
          <Row label="DB" value={data.db} />
          <Row label="Phiên bản" value={data.version} />
        </div>
      ) : (
        <span style={{ color: "var(--text-secondary)" }}>Đang kiểm tra trạng thái...</span>
      )}
    </Card>
  );
}

function Row(props: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <span style={{ color: "var(--text-secondary)" }}>{props.label}</span>
      <Badge severity={statusToSeverity(props.value)}>{healthLabel(props.value)}</Badge>
    </div>
  );
}

function healthLabel(value: string) {
  if (value === "running") return "đang chạy";
  if (value === "connected") return "đã kết nối";
  if (value === "local-ok") return "ổn định";
  if (value === "idle") return "rảnh";
  return value;
}
