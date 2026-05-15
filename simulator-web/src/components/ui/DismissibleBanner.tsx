import { useState, type ReactNode } from "react";
import { X } from "lucide-react";

interface DismissibleBannerProps {
  storageKey: string;
  icon?: ReactNode;
  children: ReactNode;
}

function readDismissed(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

export function DismissibleBanner({ storageKey, icon, children }: DismissibleBannerProps) {
  const [dismissed, setDismissed] = useState<boolean>(() => readDismissed(storageKey));

  if (dismissed) return null;

  function handleDismiss() {
    setDismissed(true);
    try {
      sessionStorage.setItem(storageKey, "1");
    } catch {
      // sessionStorage unavailable (private mode etc.) — non-fatal.
    }
  }

  return (
    <aside
      role="status"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
        padding: "12px 14px",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--accent-cyan-border)",
        background: "var(--accent-cyan-bg)",
      }}
    >
      {icon && (
        <span style={{ marginTop: "2px", color: "var(--accent-cyan)", flexShrink: 0 }}>
          {icon}
        </span>
      )}
      <div style={{ flex: 1, fontSize: "13px", lineHeight: 1.5, color: "var(--text-secondary)" }}>
        {children}
      </div>
      <button
        onClick={handleDismiss}
        aria-label="Đóng thông báo"
        style={{
          background: "transparent",
          border: "none",
          color: "var(--text-secondary)",
          cursor: "pointer",
          padding: "2px",
          flexShrink: 0,
        }}
      >
        <X size={14} />
      </button>
    </aside>
  );
}
