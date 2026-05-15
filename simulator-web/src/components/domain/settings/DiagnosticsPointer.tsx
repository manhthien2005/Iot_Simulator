import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { Card } from "../../ui/Card";

export function DiagnosticsPointer() {
  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: "240px" }}>
          <strong style={{ fontSize: "13px" }}>Tìm ngưỡng vitals + cấu hình rule?</strong>
          <p style={{ margin: "2px 0 0 0", fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            Bảng so sánh DB vs fallback và viewer JSON cho rules/fall đã chuyển sang trang Diagnostics
            để Settings tập trung vào cấu hình mutable.
          </p>
        </div>
        <Link
          to="/diagnostics#thresholds"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 12px",
            fontSize: "13px",
            color: "var(--accent-cyan)",
            border: "1px solid var(--accent-cyan)",
            borderRadius: "var(--radius-md)",
            textDecoration: "none",
          }}
        >
          <ExternalLink size={14} />
          Mở Diagnostics
        </Link>
      </div>
    </Card>
  );
}
