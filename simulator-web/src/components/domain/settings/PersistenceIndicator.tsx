import { formatSavedAt } from "../../../utils/format";
import type { RuntimePersistenceBlock } from "../../../types/settings";

interface PersistenceIndicatorProps {
  persistence: RuntimePersistenceBlock;
  pending: boolean;
}

export function PersistenceIndicator({ persistence, pending }: PersistenceIndicatorProps) {
  const isFile = persistence.source === "file";
  const tone = pending
    ? { fg: "var(--accent-cyan)", bg: "var(--accent-cyan-bg)", border: "var(--accent-cyan-border)" }
    : isFile
      ? { fg: "var(--severity-normal)", bg: "var(--severity-normal-bg)", border: "var(--severity-normal-border)" }
      : { fg: "var(--severity-warning)", bg: "var(--severity-warning-bg)", border: "var(--severity-warning-border)" };

  let title: string;
  let body: string;
  if (pending) {
    title = "Đang lưu vào runtime.json…";
    body = "Đang ghi cấu hình mới ra đĩa, sẽ áp dụng ngay sau khi xong.";
  } else if (isFile) {
    title = `Đã lưu lúc ${formatSavedAt(persistence.last_saved_at)}`;
    body = "Cấu hình hiện tại đến từ runtime.json — vẫn giữ nguyên sau khi khởi động lại.";
  } else {
    title = "Đang dùng cấu hình mặc định";
    body = "Cấu hình đến từ runtime_defaults.json. Bấm Lưu để tạo runtime.json riêng cho máy này.";
  }

  return (
    <div
      style={{
        display: "flex",
        gap: "10px",
        padding: "10px 12px",
        borderRadius: "var(--radius-md)",
        border: `1px solid ${tone.border}`,
        background: tone.bg,
        color: "var(--text-primary)",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: "8px",
          height: "8px",
          marginTop: "6px",
          borderRadius: "50%",
          background: tone.fg,
          flexShrink: 0,
        }}
      />
      <div style={{ display: "grid", gap: "2px" }}>
        <strong style={{ fontSize: "13px", color: tone.fg }}>{title}</strong>
        <small style={{ color: "var(--text-secondary)", fontSize: "12px" }}>{body}</small>
        {persistence.last_error ? (
          <small style={{ color: "var(--severity-warning)", fontSize: "12px" }}>
            Cảnh báo: {persistence.last_error}
          </small>
        ) : null}
      </div>
    </div>
  );
}
