import { Square, Zap } from "lucide-react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSessions, stopSession } from "../../services/sessionApi";
import { useSessionStore } from "../../stores/sessionStore";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";

export function Topbar() {
  const { activeSessionId, setActiveSession } = useSessionStore();
  const { data: sessions } = useQuery({
    queryKey: ["sessions", "topbar"],
    queryFn: fetchSessions,
    refetchInterval: 2000,
  });

  const active = useMemo(() => {
    if (!sessions) return null;
    if (activeSessionId) {
      return sessions.find((session) => session.id === activeSessionId) ?? null;
    }
    return sessions.find((session) => session.status === "running") ?? null;
  }, [activeSessionId, sessions]);

  const stop = async () => {
    if (!active) return;
    await stopSession(active.id);
    setActiveSession(null);
  };

  return (
    <header
      style={{
        height: "56px",
        borderBottom: "1px solid var(--border-default)",
        background: "var(--bg-surface)",
        position: "sticky",
        top: 0,
        zIndex: 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 16px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <Zap size={18} color="var(--accent-cyan)" />
        <span style={{ fontWeight: 600, letterSpacing: "0.02em" }}>Trung tâm điều khiển IoT Simulator</span>
      </div>
      {active ? (
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Badge severity="normal" dot pulse>
            Đang chạy {active.deviceIds.length} thiết bị
          </Badge>
          <span style={{ color: "var(--text-secondary)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
            {active.id}
          </span>
          <Button variant="danger" size="sm" leftIcon={<Square size={14} />} onClick={stop}>
            Dừng
          </Button>
        </div>
      ) : (
        <Badge severity="offline" dot>
          Chưa có phiên chạy
        </Badge>
      )}
    </header>
  );
}
