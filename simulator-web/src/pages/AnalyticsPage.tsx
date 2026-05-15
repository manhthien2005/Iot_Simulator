import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Moon, ShieldAlert, Watch, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { DismissibleBanner } from "../components/ui/DismissibleBanner";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
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
      <section className="page-section">
        <PageHeader title="Phân tích" />
        <Skeleton style={{ height: "220px" }} />
      </section>
    );
  }

  if (!devices.length) {
    return (
      <section className="page-section">
        <PageHeader title="Phân tích" />
        <EmptyState icon={Watch} title="Chưa có thiết bị" description="Tạo thiết bị để kích hoạt phân tích giấc ngủ và rủi ro." />
      </section>
    );
  }

  return (
    <section className="page-section">
      <PageHeader
        title="Phân tích"
        subtitle="Chế độ chỉ đọc cho người xem lâm sàng — phát lại giấc ngủ và phân tích rủi ro với fallback cho Sleep-EDF."
        action={
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
        }
      />

      <DismissibleBanner storageKey={DIAGNOSTICS_NOTICE_KEY} icon={<Wrench size={16} />}>
        <strong style={{ color: "var(--text-primary)" }}>Operator tools đã chuyển sang Diagnostics.</strong>{" "}
        Chạy tính toán theo yêu cầu, tiêm rủi ro nhân tạo và trình kiểm tra ngưỡng đều nằm trong{" "}
        <Link to="/diagnostics#risk-tools" style={{ color: "var(--accent-cyan)", textDecoration: "underline" }}>
          Diagnostics
        </Link>
        . Trang Phân tích giữ nguyên dữ liệu chỉ đọc cho clinical viewers.
      </DismissibleBanner>

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

