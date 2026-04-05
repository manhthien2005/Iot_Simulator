import { Square, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { useSessions } from "../../hooks/useSessions";
import { stopSession } from "../../services/sessionApi";
import { useSessionStore } from "../../stores/sessionStore";
import { notify } from "../../utils/toast";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";

export function Topbar() {
  const { activeSessionId, setActiveSession } = useSessionStore();
  const { data: sessions } = useSessions();
  const [stopping, setStopping] = useState(false);

  const runningSessions = useMemo(() => {
    if (!sessions) return [];
    if (activeSessionId) {
      const active = sessions.find((session) => session.id === activeSessionId);
      return active ? [active] : [];
    }
    return sessions.filter((session) => session.status === "running");
  }, [activeSessionId, sessions]);

  const activeDeviceCount = useMemo(() => {
    return runningSessions.reduce((total, s) => total + s.deviceIds.length, 0);
  }, [runningSessions]);

  const stopAll = async () => {
    if (runningSessions.length === 0) return;
    setStopping(true);
    try {
      const results = await Promise.allSettled(
        runningSessions.map((session) => stopSession(session.id))
      );
      const failed = results.filter((r) => r.status === "rejected").length;
      if (failed === 0) {
        notify.success("Đã dừng tất cả phiên mô phỏng.");
      } else if (failed < results.length) {
        notify.warning(`Dừng được ${results.length - failed}/${results.length} phiên. ${failed} phiên lỗi.`);
      } else {
        notify.error("Không dừng được phiên nào. Kiểm tra kết nối.");
      }
      setActiveSession(null);
    } catch {
      notify.error("Lỗi khi dừng phiên mô phỏng.");
    } finally {
      setStopping(false);
    }
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
      {runningSessions.length > 0 ? (
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Badge severity="normal" dot pulse>
            Đang chạy {activeDeviceCount} thiết bị ({runningSessions.length} phiên)
          </Badge>
          <Button variant="danger" size="sm" leftIcon={<Square size={14} />} onClick={stopAll} disabled={stopping}>
            {stopping ? "Đang dừng…" : "Dừng tất cả"}
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
