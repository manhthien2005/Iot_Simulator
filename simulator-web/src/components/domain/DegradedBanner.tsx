import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// DegradedBanner — renders only when `degradedReasons.length > 0`.  Each
// known reason maps to a single, operator-readable line; unknown reasons
// fall back to the raw token so we never silently drop signal.
// ---------------------------------------------------------------------------

interface DegradedBannerProps {
  reasons: readonly string[];
}

interface ReasonCopy {
  title: string;
  hint: string;
}

const REASON_COPY: Record<string, ReasonCopy> = {
  database_down: {
    title: "Database cục bộ không phản hồi",
    hint: "Tick publish và heartbeat sẽ thất bại cho đến khi DB lên lại.",
  },
  backend_unreachable: {
    title: "Health backend không truy cập được",
    hint: "Telemetry và alert không đẩy lên được — kiểm tra `health_system` trên cổng 8000.",
  },
  backend_slow: {
    title: "Health backend phản hồi chậm",
    hint: "Vượt ngưỡng cho phép; cảnh báo có thể bị trễ. Kiểm tra tải hệ thống.",
  },
  model_api_unavailable: {
    title: "Sleep AI tạm thời không khả dụng",
    hint: "Mô phỏng đang dùng heuristic dự phòng cho điểm giấc ngủ. Khởi động lại `healthguard-model-api` để khôi phục AI scoring.",
  },
  pre_trigger_misconfigured: {
    title: "Pre-trigger được bật nhưng không khởi tạo được",
    hint: "Mô phỏng sẽ không chạy rule pre-model. Kiểm tra log khởi động để biết tại sao orchestrator dừng.",
  },
};

export function DegradedBanner({ reasons }: DegradedBannerProps) {
  if (reasons.length === 0) return null;

  const items = reasons.map((reason) => REASON_COPY[reason] ?? { title: reason, hint: "Lý do không nằm trong từ điển — kiểm tra log mô phỏng." });

  return (
    <section role="status" aria-live="polite" style={bannerStyle}>
      <div style={headerStyle}>
        <span style={iconStyle} aria-hidden="true">!</span>
        <div>
          <strong style={{ fontSize: "14px", color: "var(--severity-warning)" }}>Mô phỏng đang ở chế độ suy giảm</strong>
          <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5 }}>
            Một hoặc nhiều dịch vụ phụ thuộc đang gặp sự cố. Mô phỏng vẫn phục vụ vitals nhưng các tính năng dưới đây đang ở chế độ dự phòng:
          </p>
        </div>
      </div>
      <ul style={listStyle}>
        {items.map((item, i) => (
          <li key={`${item.title}-${i}`} style={listItemStyle}>
            <strong style={{ color: "var(--text-primary)" }}>{item.title}</strong>
            <span style={{ color: "var(--text-secondary)", marginLeft: "6px" }}>— {item.hint}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────

const bannerStyle: CSSProperties = {
  border: "1px solid rgba(245, 158, 11, 0.35)",
  background: "rgba(245, 158, 11, 0.08)",
  borderRadius: "var(--radius-lg, 12px)",
  padding: "14px 16px",
  display: "grid",
  gap: "10px",
};

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: "12px",
};

const iconStyle: CSSProperties = {
  width: "24px",
  height: "24px",
  flexShrink: 0,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "50%",
  background: "rgba(245, 158, 11, 0.18)",
  color: "var(--severity-warning)",
  fontWeight: 700,
  fontSize: "13px",
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: "20px",
  display: "grid",
  gap: "4px",
  fontSize: "13px",
  lineHeight: 1.5,
};

const listItemStyle: CSSProperties = {
  color: "var(--text-secondary)",
};
