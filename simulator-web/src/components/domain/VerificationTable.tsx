import type { VerificationResult } from "../../types/verification";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

interface VerificationTableProps {
  rows: VerificationResult[];
  onRefresh: () => void;
}

function statusSeverity(status: VerificationResult["status"]) {
  if (status === "PASS") return "normal" as const;
  if (status === "DELAYED") return "warning" as const;
  if (status === "FAILED") return "critical" as const;
  return "offline" as const;
}

export function VerificationTable({ rows, onRefresh }: VerificationTableProps) {
  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <strong>Bảng xác minh</strong>
          <Button variant="secondary" size="sm" onClick={onRefresh}>
            Kiểm tra lại
          </Button>
        </div>
      }
    >
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ color: "var(--text-secondary)", fontSize: "12px", textTransform: "uppercase" }}>
            <th style={{ textAlign: "left", padding: "8px 0" }}>Thiết bị</th>
            <th style={{ textAlign: "left", padding: "8px 0" }}>Sinh hiệu</th>
            <th style={{ textAlign: "left", padding: "8px 0" }}>Cảnh báo</th>
            <th style={{ textAlign: "left", padding: "8px 0" }}>Rủi ro</th>
            <th style={{ textAlign: "left", padding: "8px 0" }}>Độ trễ</th>
            <th style={{ textAlign: "left", padding: "8px 0" }}>Kết quả</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.deviceId} style={{ borderTop: "1px solid var(--border-default)" }}>
              <td style={{ padding: "10px 0" }}>{row.deviceId}</td>
              <td style={{ padding: "10px 0" }}>{row.vitalsReceived ? "Có" : "Không"}</td>
              <td style={{ padding: "10px 0" }}>{row.alertReceived ? "Đã nhận" : "N/A"}</td>
              <td style={{ padding: "10px 0" }}>{row.riskScoreReceived ? "Sẵn sàng" : "Đang chờ"}</td>
              <td style={{ padding: "10px 0" }}>{row.latencyMs}ms</td>
              <td style={{ padding: "10px 0" }}>
                <Badge severity={statusSeverity(row.status)}>{statusLabel(row.status)}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function statusLabel(status: VerificationResult["status"]) {
  if (status === "PASS") return "Đạt";
  if (status === "DELAYED") return "Trễ";
  if (status === "FAILED") return "Thất bại";
  return "Đang chờ";
}
