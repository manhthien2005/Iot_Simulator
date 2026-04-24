import { useMemo } from "react";
import { VerificationTable } from "../components/domain/VerificationTable";
import { LogViewer } from "../components/domain/LogViewer";
import { HealthStatusPanel } from "../components/domain/HealthStatusPanel";
import { useSessions } from "../hooks/useSessions";
import { useVerification } from "../hooks/useVerification";
import { useLogStream } from "../hooks/useLogStream";
import { useSessionStore } from "../stores/sessionStore";

export function VerificationPage() {
  const { activeSessionId } = useSessionStore();
  const { data: sessions = [], refetch: refetchSessions } = useSessions();
  const active = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? sessions.find((session) => session.status === "running") ?? null,
    [activeSessionId, sessions]
  );
  const { data: verification, refetch } = useVerification(active?.id ?? null);
  const { logs } = useLogStream(active?.id ?? null);

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div>
        <h1 className="page-title">Xác minh</h1>
        <p className="page-subtitle">Theo dõi xác minh theo thiết bị, kiểm tra log và xuất bằng chứng phiên chạy.</p>
      </div>

      <VerificationTable
        rows={verification ? [verification] : []}
        onRefresh={() => {
          refetch();
          refetchSessions();
        }}
      />

      <LogViewer logs={logs} />
      <HealthStatusPanel />
    </section>
  );
}
