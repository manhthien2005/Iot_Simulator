import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Moon, ShieldAlert, Watch, X, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui/EmptyState";
import { Select } from "../components/ui/Select";
import { Skeleton } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { SleepAnalyticsTab } from "../components/domain/SleepAnalyticsTab";
import { RiskAnalyticsTab } from "../components/domain/RiskAnalyticsTab";
import { useDevices } from "../hooks/useDevices";
import { getDbSleepHistory, getRiskScore, getSleepSession } from "../services/analyticsApi";
import { POLL_INTERVALS } from "../config/defaults";

// ---------------------------------------------------------------------------
// Module D.7 — dismissible "moved to Diagnostics" notice.
//
// Survives reload via sessionStorage so a user who has acknowledged the
// move does not see the banner on every navigation back.  Stored under a
// versioned key so we can re-arm later if the notice content changes.
// ---------------------------------------------------------------------------

const DIAGNOSTICS_NOTICE_KEY = "ux-refactor:analytics-notice-v1";

type AnalyticsTab = "sleep" | "risk";

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function AnalyticsPage() {
  const [tab, setTab] = useState<AnalyticsTab>("sleep");
  const { data: devices = [], isLoading: devicesLoading } = useDevices();
  const [deviceId, setDeviceId] = useState<string>("");
  const [sleepScenarioId, setSleepScenarioId] = useState("good_sleep_night");
  const [targetDate, setTargetDate] = useState(() => {
    const value = new Date();
    value.setDate(value.getDate() - 1);
    return toDateInputValue(value);
  });

  useEffect(() => {
    if (!devices.length) {
      setDeviceId("");
      return;
    }
    if (!deviceId || !devices.some((device) => device.id === deviceId)) {
      setDeviceId(devices[0].id);
    }
  }, [deviceId, devices]);

  const yesterdayStr = useMemo(() => {
    const value = new Date();
    value.setHours(0, 0, 0, 0);
    value.setDate(value.getDate() - 1);
    return value.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }, []);

  const yesterdayInputMax = useMemo(() => {
    const value = new Date();
    value.setHours(0, 0, 0, 0);
    value.setDate(value.getDate() - 1);
    return toDateInputValue(value);
  }, []);

  const oldestInputMin = useMemo(() => {
    const value = new Date();
    value.setHours(0, 0, 0, 0);
    value.setDate(value.getDate() - 365);
    return toDateInputValue(value);
  }, []);

  const sleepQuery = useQuery({
    queryKey: ["analytics", "sleep", deviceId],
    queryFn: () => getSleepSession(deviceId),
    enabled: Boolean(deviceId) && tab === "sleep",
    refetchInterval: POLL_INTERVALS.analytics,
  });

  const dbHistoryQuery = useQuery({
    queryKey: ["analytics", "sleep", "db-history", deviceId],
    queryFn: () => getDbSleepHistory(deviceId, 30),
    enabled: Boolean(deviceId) && tab === "sleep",
    refetchInterval: POLL_INTERVALS.analytics,
  });

  const riskQuery = useQuery({
    queryKey: ["analytics", "risk", deviceId],
    queryFn: () => getRiskScore(deviceId),
    enabled: Boolean(deviceId) && tab === "risk",
    refetchInterval: POLL_INTERVALS.analyticsRisk,
  });

  if (devicesLoading) {
    return (
      <section style={{ display: "grid", gap: "12px" }}>
        <h1 className="page-title">Phân tích</h1>
        <Skeleton style={{ height: "220px" }} />
      </section>
    );
  }

  if (!devices.length) {
    return (
      <section style={{ display: "grid", gap: "12px" }}>
        <h1 className="page-title">Phân tích</h1>
        <EmptyState icon={Watch} title="Chưa có thiết bị" description="Tạo thiết bị để kích hoạt phân tích giấc ngủ và rủi ro." />
      </section>
    );
  }

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <h1 className="page-title">Phân tích</h1>
          <p className="page-subtitle">
            Chế độ chỉ đọc cho người xem lâm sàng — phát lại giấc ngủ và phân tích rủi ro với fallback cho Sleep-EDF.
          </p>
        </div>
        <Select
          value={deviceId}
          onChange={(event) => setDeviceId(event.target.value)}
          aria-label="Chọn thiết bị để phân tích"
        >
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name}
            </option>
          ))}
        </Select>
      </div>

      <DiagnosticsMovedNotice />

      <Tabs
        items={[
          { key: "sleep", label: "Giấc ngủ", icon: <Moon size={14} /> },
          { key: "risk", label: "Rủi ro", icon: <ShieldAlert size={14} /> },
        ]}
        activeKey={tab}
        onChange={(key) => setTab(key as AnalyticsTab)}
      />

      {tab === "sleep" ? (
        <SleepAnalyticsTab
          deviceId={deviceId}
          sleepQuery={sleepQuery}
          dbHistoryQuery={dbHistoryQuery}
          sleepScenarioId={sleepScenarioId}
          onSleepScenarioIdChange={setSleepScenarioId}
          targetDate={targetDate}
          onTargetDateChange={setTargetDate}
          yesterdayStr={yesterdayStr}
          yesterdayInputMax={yesterdayInputMax}
          oldestInputMin={oldestInputMin}
        />
      ) : (
        <RiskAnalyticsTab deviceId={deviceId} riskQuery={riskQuery} />
      )}
    </section>
  );
}

// ── Diagnostics moved notice ────────────────────────────────────────────

function DiagnosticsMovedNotice() {
  const [dismissed, setDismissed] = useState<boolean>(() => readDismissed());

  if (dismissed) return null;

  function handleDismiss() {
    setDismissed(true);
    try {
      sessionStorage.setItem(DIAGNOSTICS_NOTICE_KEY, "1");
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
        border: "1px solid rgba(6, 182, 212, 0.30)",
        background: "rgba(6, 182, 212, 0.08)",
      }}
    >
      <Wrench size={16} style={{ marginTop: "2px", color: "var(--accent-cyan)", flexShrink: 0 }} />
      <div style={{ flex: 1, fontSize: "13px", lineHeight: 1.5, color: "var(--text-secondary)" }}>
        <strong style={{ color: "var(--text-primary)" }}>Operator tools đã chuyển sang Diagnostics.</strong>{" "}
        Chạy tính toán theo yêu cầu, tiêm rủi ro nhân tạo và trình kiểm tra ngưỡng đều nằm trong{" "}
        <Link to="/diagnostics#risk-tools" style={{ color: "var(--accent-cyan)", textDecoration: "underline" }}>
          Diagnostics
        </Link>
        . Trang Phân tích giữ nguyên dữ liệu chỉ đọc cho clinical viewers.
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

function readDismissed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(DIAGNOSTICS_NOTICE_KEY) === "1";
  } catch {
    return false;
  }
}
