import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Watch } from "lucide-react";
import { DevicePicker } from "../components/domain/session/DevicePicker";
import { UserProfileCard } from "../components/domain/session/UserProfileCard";
import { BackfillCard } from "../components/domain/BackfillCard";
import { SleepScenarioCard } from "../components/domain/sleep/SleepScenarioCard";
import { SleepPreviewPanel } from "../components/domain/sleep/SleepPreviewPanel";
import { SleepPushPanel } from "../components/domain/sleep/SleepPushPanel";
import { SleepHistoryPanel } from "../components/domain/sleep/SleepHistoryPanel";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { useDbDevices, useDevices } from "../hooks/useDevices";
import { useUserProfile } from "../hooks/useUserProfile";
import { getDbSleepHistory, getSleepSession } from "../services/analyticsApi";
import { POLL_INTERVALS } from "../config/defaults";
import { DEFAULT_SLEEP_SCENARIO_ID } from "../config/sleepScenarios";

// ---------------------------------------------------------------------------
// SleepLabPage — dedicated workspace for sleep simulation, mirrors the
// device-first layout of SessionRunnerPage.
//
//   1. Chọn thiết bị     -> DevicePicker (DB devices, no SIM-running filter
//                           because sleep can be pushed for past dates even
//                           when SIM is off).
//   2. Hồ sơ người dùng  -> UserProfileCard fetched on demand once a device
//                           is selected.
//   3. Kịch bản + preview -> SleepScenarioCard + SleepPreviewPanel.
//   4. Push / Backfill   -> SleepPushPanel + BackfillCard.
//   5. Lịch sử DB        -> SleepHistoryPanel.
//
// Data wiring lives here so each section component stays presentational
// and reuses session-page primitives where it makes sense.
// ---------------------------------------------------------------------------

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function SleepLabPage() {
  const { data: dbDevices = [], isLoading: dbDevicesLoading } = useDbDevices();
  const { data: simDevices = [] } = useDevices(2000);

  const [selectedDbDeviceId, setSelectedDbDeviceId] = useState<number | null>(null);
  const [scenarioId, setScenarioId] = useState<string>(DEFAULT_SLEEP_SCENARIO_ID);
  const [targetDate, setTargetDate] = useState(() => {
    const value = new Date();
    value.setDate(value.getDate() - 1);
    return toDateInputValue(value);
  });

  // Auto-select first DB device (any state, not just SIM-running) so the
  // page is usable even when no simulator session is active — the push /
  // backfill flow only needs a bound device + user.
  useEffect(() => {
    if (dbDevices.length === 0) {
      setSelectedDbDeviceId(null);
      return;
    }
    if (selectedDbDeviceId == null || !dbDevices.some((device) => device.id === selectedDbDeviceId)) {
      setSelectedDbDeviceId(dbDevices[0].id);
    }
  }, [dbDevices, selectedDbDeviceId]);

  const selectedDbDevice = useMemo(
    () => dbDevices.find((device) => device.id === selectedDbDeviceId) ?? null,
    [dbDevices, selectedDbDeviceId]
  );

  // Map DB device id -> simulator string id, the BE format expected by
  // /analytics/sleep & /scenarios/sleep/push-date.
  const selectedSimDevice = useMemo(
    () =>
      selectedDbDeviceId == null
        ? null
        : simDevices.find((device) => device.boundDbDeviceId === selectedDbDeviceId) ?? null,
    [selectedDbDeviceId, simDevices]
  );
  const simDeviceId = selectedSimDevice?.id ?? "";

  const {
    data: userProfile,
    isFetching: isProfileFetching,
    error: profileError,
  } = useUserProfile(selectedDbDevice?.user_id ?? null);

  const yesterdayLabel = useMemo(() => {
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
    queryKey: ["analytics", "sleep", simDeviceId],
    queryFn: () => getSleepSession(simDeviceId),
    enabled: Boolean(simDeviceId),
    refetchInterval: POLL_INTERVALS.analytics,
  });

  const dbHistoryQuery = useQuery({
    queryKey: ["analytics", "sleep", "db-history", simDeviceId],
    queryFn: () => getDbSleepHistory(simDeviceId, 30),
    enabled: Boolean(simDeviceId),
    refetchInterval: POLL_INTERVALS.analytics,
  });

  if (dbDevicesLoading) {
    return (
      <section className="page-section">
        <PageHeader title="Mô phỏng giấc ngủ" />
        <Skeleton style={{ height: "220px" }} />
      </section>
    );
  }

  if (dbDevices.length === 0) {
    return (
      <section className="page-section">
        <PageHeader title="Mô phỏng giấc ngủ" />
        <EmptyState
          icon={Watch}
          title="Chưa có thiết bị"
          description="Tạo thiết bị và gán cho người dùng để bắt đầu mô phỏng dữ liệu giấc ngủ."
        />
      </section>
    );
  }

  return (
    <section className="page-section">
      <PageHeader
        title="Mô phỏng giấc ngủ"
        subtitle="Chọn thiết bị, xem hồ sơ người dùng, sau đó áp dụng kịch bản giấc ngủ và đẩy / ghi đè vào DB."
      />

      <div style={{ display: "grid", gap: "8px" }}>
        <SectionHeading label="1. Chọn thiết bị" />
        <DevicePicker
          devices={dbDevices}
          selectedDeviceId={selectedDbDeviceId}
          onSelect={setSelectedDbDeviceId}
        />
      </div>

      {selectedDbDeviceId != null ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <SectionHeading label="2. Hồ sơ người dùng" />
          {selectedDbDevice?.user_id != null ? (
            <UserProfileCard
              profile={userProfile}
              isLoading={isProfileFetching && !userProfile}
              error={profileError as Error | null}
            />
          ) : (
            <UserProfileCard profile={undefined} isLoading={false} error={null} />
          )}
        </div>
      ) : null}

      {selectedDbDeviceId != null ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <SectionHeading label="3. Kịch bản & xem trước" />
          <SleepScenarioCard value={scenarioId} onChange={setScenarioId} disabled={!simDeviceId} />
          {simDeviceId ? (
            <SleepPreviewPanel sleepQuery={sleepQuery} />
          ) : (
            <EmptyState
              icon={Watch}
              title="Thiết bị chưa được liên kết với simulator"
              description="Bật SIM cho thiết bị này ở tab Thiết bị để có hypnogram và preview thời gian thực."
            />
          )}
        </div>
      ) : null}

      {selectedDbDeviceId != null && simDeviceId ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <SectionHeading label="4. Đẩy & backfill dữ liệu" />
          <SleepPushPanel
            deviceId={simDeviceId}
            scenarioId={scenarioId}
            onScenarioChange={setScenarioId}
            targetDate={targetDate}
            onTargetDateChange={setTargetDate}
            yesterdayLabel={yesterdayLabel}
            yesterdayInputMax={yesterdayInputMax}
            oldestInputMin={oldestInputMin}
            dbHistoryQuery={dbHistoryQuery}
          />
          <BackfillCard
            deviceId={simDeviceId}
            onCompleted={() => {
              void dbHistoryQuery.refetch();
            }}
          />
        </div>
      ) : null}

      {selectedDbDeviceId != null && simDeviceId ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <SectionHeading label="5. Lịch sử giấc ngủ trong DB" />
          <SleepHistoryPanel dbHistoryQuery={dbHistoryQuery} onUseDate={setTargetDate} />
        </div>
      ) : null}
    </section>
  );
}

function SectionHeading({ label }: { label: string }) {
  return (
    <div
      style={{
        fontSize: "11px",
        fontWeight: 700,
        color: "var(--text-muted)",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
      }}
    >
      {label}
    </div>
  );
}
