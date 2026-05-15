import { Clock } from "lucide-react";
import { useState, useEffect } from "react";

function useCurrentTime() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

export function Topbar() {
  const now = useCurrentTime();
  const timeStr = now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const dateStr = now.toLocaleDateString("vi-VN", { weekday: "short", day: "2-digit", month: "2-digit" });

  return (
    <header
      style={{
        height: "54px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        background: "var(--bg-surface)",
        position: "sticky",
        top: 0,
        zIndex: 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-end",
        padding: "0 20px",
        gap: "12px",
      }}
    >
      {/* Right: clock — only content remaining after sessions UI was removed */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          color: "var(--text-secondary)",
          fontSize: "13px",
          fontFamily: "var(--font-mono)",
          flexShrink: 0,
        }}
      >
        <Clock size={14} />
        <span>{timeStr}</span>
        <span style={{ color: "var(--text-muted)" }}>·</span>
        <span style={{ color: "var(--text-muted)" }}>{dateStr}</span>
      </div>
    </header>
  );
}
