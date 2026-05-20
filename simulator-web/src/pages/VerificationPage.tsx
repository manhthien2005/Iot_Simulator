import { useCallback, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { EvidenceGrid } from "../components/domain/EvidenceGrid";
import { LogViewer } from "../components/domain/LogViewer";
import { PageHeader } from "../components/ui/PageHeader";
import { useSessions } from "../hooks/useSessions";
import { useAllVerifications } from "../hooks/useVerification";
import { useLogStream } from "../hooks/useLogStream";
import { useDevices } from "../hooks/useDevices";
import { useRelativeTime } from "../hooks/useRelativeTime";

// ---------------------------------------------------------------------------
// VerificationPage — "Trung tâm Bằng chứng" rebuild.
//
// Layout:
//   1. PageHeader + LivenessSummary (replaces session-id headerLine).
//   2. <EvidenceGrid/> — one card per device with liveness, pipeline, log strip.
//   3. <LogViewer/>   — full-stream log viewer; auto-filters by deviceId when
//                       a card focuses logs.
// ---------------------------------------------------------------------------

const LIVENESS_OK_MS = 10_000;
const LIVENESS_WARN_MS = 60_000;

export function VerificationPage() {
  const { data: sessions = [], refetch: refetchSessions, dataUpdatedAt } = useSessions();

  const runningIds = useMemo(
    () => sessions.filter((s) => s.status === "running").map((s) => s.id),
    [sessions],
  );

  const { data: rows = [], refetch } = useAllVerifications(runningIds);
  const { data: devices = [] } = useDevices();
  const { logs } = useLogStream(runningIds);

  const [focusedDeviceId, setFocusedDeviceId] = useState<string | null>(null);

  const deviceNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of devices) map[d.id] = d.name;
    return map;
  }, [devices]);

  const handleRefresh = useCallback(() => {
    refetch();
    refetchSessions();
  }, [refetch, refetchSessions]);

  const handleClearFocus = useCallback(() => setFocusedDeviceId(null), []);

  const liveCount = useMemo(
    () =>
      rows.filter((r) => isLive(r.lastGoodPublishAt ?? r.lastCheckedAt, r.status)).length,
    [rows],
  );

  return (
    <section className="page-section">
      <div>
        <PageHeader
          title="Trung tâm Bằng chứng"
          subtitle="Mỗi thẻ là một bằng chứng đang sống của một thiết bị: liveness, pipeline xác minh, và 3 dòng log gần nhất. Trạng thái hệ thống tổng quan đã chuyển sang trang Bảng điều khiển."
        />
        <LivenessSummary
          liveCount={liveCount}
          totalCount={rows.length}
          updatedAt={dataUpdatedAt}
        />
      </div>

      <EvidenceGrid
        rows={rows}
        logs={logs}
        deviceNameMap={deviceNameMap}
        onRefresh={handleRefresh}
        onFocusLogs={setFocusedDeviceId}
      />

      <LogViewer
        logs={logs}
        deviceNameMap={deviceNameMap}
        focusedDeviceId={focusedDeviceId}
        onClearFocus={handleClearFocus}
      />
    </section>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function isLive(iso: string | null | undefined, status: string): boolean {
  if (status === "FAILED") return false;
  if (!iso) return false;
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return false;
  return Date.now() - ts < LIVENESS_WARN_MS;
}

function LivenessSummary({
  liveCount,
  totalCount,
  updatedAt,
}: {
  liveCount: number;
  totalCount: number;
  updatedAt: number;
}) {
  const updatedIso = updatedAt ? new Date(updatedAt).toISOString() : null;
  const { label } = useRelativeTime(updatedIso, 1000);

  if (totalCount === 0) {
    return (
      <p style={summaryStyle}>
        Chưa có phiên đang chạy — bắt đầu một phiên để xem bằng chứng.
      </p>
    );
  }

  const dotClass = liveCount > 0 ? "live-dot" : undefined;
  const dotStyle: CSSProperties = {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background:
      liveCount === totalCount
        ? "var(--severity-normal)"
        : liveCount > 0
          ? "var(--severity-warning)"
          : "var(--severity-critical)",
  };

  return (
    <p style={summaryStyle}>
      <span className={dotClass} style={dotStyle} aria-hidden />
      <span>
        <strong style={{ color: "var(--text-primary)" }}>
          {liveCount}/{totalCount}
        </strong>
        &nbsp;thiết bị đang phát dữ liệu
      </span>
      <span style={{ color: "var(--text-muted)" }}>·</span>
      <span>
        cập nhật <code style={codeStyle}>{label}</code> trước
      </span>
    </p>
  );
}

const summaryStyle: CSSProperties = {
  margin: "8px 0 0 0",
  display: "flex",
  alignItems: "center",
  gap: "8px",
  fontSize: "13px",
  color: "var(--text-secondary)",
};

const codeStyle: CSSProperties = {
  fontFamily: "var(--font-mono)",
  color: "var(--text-primary)",
};
