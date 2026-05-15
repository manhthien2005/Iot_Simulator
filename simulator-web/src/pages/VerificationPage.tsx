import { useMemo } from "react";
import { VerificationTable } from "../components/domain/VerificationTable";
import { LogViewer } from "../components/domain/LogViewer";
import { LastGoodPublishCard } from "../components/domain/LastGoodPublishCard";
import { PageHeader } from "../components/ui/PageHeader";
import { useSessions } from "../hooks/useSessions";
import { useAllVerifications } from "../hooks/useVerification";
import { useLogStream } from "../hooks/useLogStream";
import { useDevices } from "../hooks/useDevices";
import { useSessionStore } from "../stores/sessionStore";

// ---------------------------------------------------------------------------
// VerificationPage — Module E rebuild as the "Trung tâm Bằng chứng".
//
// Layout:
//   1. Page header (truthful copy + running-session count line)
//   2. <VerificationTable/>           — one card per running session/device
//   3. <LastGoodPublishCard/>         — evidence for the active/first session
//   4. <LogViewer/>                   — live log stream (active session WS)
// ---------------------------------------------------------------------------

export function VerificationPage() {
  const { activeSessionId } = useSessionStore();
  const { data: sessions = [], refetch: refetchSessions } = useSessions();

  const runningSessions = useMemo(
    () => sessions.filter((s) => s.status === "running"),
    [sessions],
  );
  const runningIds = useMemo(
    () => runningSessions.map((s) => s.id),
    [runningSessions],
  );

  const activeSession = useMemo(
    () =>
      sessions.find((s) => s.id === activeSessionId && s.status === "running") ??
      runningSessions[0] ??
      null,
    [activeSessionId, sessions, runningSessions],
  );

  const { data: allRows = [], refetch } = useAllVerifications(runningIds);
  const { data: devices = [] } = useDevices();
  const { logs } = useLogStream(runningIds);

  const deviceNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of devices) map[d.id] = d.name;
    return map;
  }, [devices]);

  const activeResult = useMemo(
    () => allRows.find((r) => r.sessionId === activeSession?.id) ?? allRows[0] ?? null,
    [allRows, activeSession],
  );

  function handleRefresh() {
    refetch();
    refetchSessions();
  }

  const headerLine = useMemo(() => {
    if (runningSessions.length === 0) {
      return "Chưa có phiên đang chạy — bắt đầu một phiên để xem bằng chứng.";
    }
    const names = runningSessions
      .map((s) => {
        const devList = s.deviceIds.slice(0, 2).join(", ");
        const extra = s.deviceIds.length > 2 ? ` +${s.deviceIds.length - 2}` : "";
        return `[${s.id.slice(0, 8)}…] ${devList}${extra}`;
      })
      .join(" · ");
    return `${runningSessions.length} phiên đang chạy — ${names}`;
  }, [runningSessions]);

  return (
    <section className="page-section">
      <div>
        <PageHeader
          title="Trung tâm Bằng chứng"
          subtitle="Tiến trình pipeline theo từng phiên, lý do lỗi, lần publish thành công gần nhất và log thời gian thực — đủ bằng chứng để báo cáo phiên mô phỏng. Trạng thái hệ thống tổng quan đã chuyển sang trang Bảng điều khiển."
        />
        <p style={activeSessionStyle}>{headerLine}</p>
      </div>

      <VerificationTable
        rows={allRows}
        onRefresh={handleRefresh}
        deviceNameMap={deviceNameMap}
      />

      <div style={gridStyle}>
        <LastGoodPublishCard result={activeResult} />
        <LogViewer logs={logs} deviceNameMap={deviceNameMap} />
      </div>
    </section>
  );
}

const activeSessionStyle = {
  margin: "4px 0 0 0",
  fontSize: "12px",
  color: "var(--text-muted)",
  fontFamily: "var(--font-mono)",
} as const;

const gridStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(280px, 1fr) minmax(0, 2fr)",
  gap: "12px",
} as const;
