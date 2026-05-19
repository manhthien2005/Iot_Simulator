import { useMutation, type UseQueryResult } from "@tanstack/react-query";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { fieldStyle } from "../../../config/defaults";
import { sleepScenarioOptions } from "../../../config/sleepScenarios";
import { pushSleepForDate } from "../../../services/analyticsApi";
import type { DbSleepHistoryRow, PushSleepDateResponse } from "../../../types/analytics";
import { notify } from "../../../utils/toast";

// ---------------------------------------------------------------------------
// SleepPushPanel — date-targeted push form for the sleep table.
//
// Operator picks a scenario + a past date, hits "Đẩy / Ghi đè", and the
// BE either creates a new `sleep_sessions` row or overwrites an existing
// one for that user/device/date.  Result banner mirrors the BE response
// shape so the operator can verify what landed without opening the DB.
//
// Owns its own mutation; takes a `dbHistoryQuery` reference so it can
// trigger a refetch after a successful push without forcing the parent
// to thread an `onSuccess` callback through props.
// ---------------------------------------------------------------------------

interface SleepPushPanelProps {
  deviceId: string;
  scenarioId: string;
  onScenarioChange: (id: string) => void;
  targetDate: string;
  onTargetDateChange: (date: string) => void;
  yesterdayLabel: string;
  yesterdayInputMax: string;
  oldestInputMin: string;
  dbHistoryQuery: UseQueryResult<DbSleepHistoryRow[]>;
  disabled?: boolean;
}

export function SleepPushPanel({
  deviceId,
  scenarioId,
  onScenarioChange,
  targetDate,
  onTargetDateChange,
  yesterdayLabel,
  yesterdayInputMax,
  oldestInputMin,
  dbHistoryQuery,
  disabled = false,
}: SleepPushPanelProps) {
  const pushMutation = useMutation({
    mutationFn: () =>
      pushSleepForDate({
        device_id: deviceId,
        target_date: targetDate,
        scenario_id: scenarioId,
      }),
    onSuccess: async (result) => {
      await dbHistoryQuery.refetch();
      const statusLabel = result.was_overwritten ? "Đã ghi đè" : "Đã tạo mới";
      notify.success(
        `${statusLabel} phiên ngày ${result.target_date}. Điểm ${result.sleep_score}/100, thời lượng ${formatDuration(
          result.duration_minutes
        )}.`
      );
    },
    onError: (error) => {
      notify.error(extractApiError(error, "Không thể push dữ liệu giấc ngủ cho ngày đã chọn."));
    },
  });

  const onPushClick = async () => {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi đẩy dữ liệu.");
      return;
    }
    if (!targetDate) {
      notify.error("Chọn ngày cần push trước khi tiếp tục.");
      return;
    }
    if (targetDate > yesterdayInputMax) {
      notify.error("Chỉ được chọn ngày quá khứ, tối đa là hôm qua.");
      return;
    }
    await pushMutation.mutateAsync();
  };

  return (
    <Card header={<strong>Đẩy / Ghi đè 1 đêm vào DB</strong>}>
      <div style={{ display: "grid", gap: "10px" }}>
        <small style={{ color: "var(--text-secondary)" }}>
          Chọn kịch bản và một ngày quá khứ để tạo mới hoặc ghi đè phiên đã lưu. Date picker khoá từ{" "}
          <span style={{ color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>{yesterdayLabel}</span> trở về trước.
        </small>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(220px, 1.2fr) minmax(180px, 0.8fr) auto",
            gap: "8px",
            alignItems: "end",
          }}
        >
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Kịch bản
            <select
              value={scenarioId}
              onChange={(event) => onScenarioChange(event.target.value)}
              style={fieldStyle}
              disabled={disabled}
            >
              {sleepScenarioOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Ngày cần push
            <input
              type="date"
              min={oldestInputMin}
              max={yesterdayInputMax}
              value={targetDate}
              onChange={(event) => onTargetDateChange(event.target.value)}
              style={fieldStyle}
              disabled={disabled}
            />
          </label>
          <Button
            variant="primary"
            onClick={onPushClick}
            loading={pushMutation.isPending}
            disabled={disabled || !deviceId}
          >
            Đẩy / Ghi đè
          </Button>
        </div>

        {pushMutation.data ? <PushResultBanner data={pushMutation.data} /> : null}
      </div>
    </Card>
  );
}

function PushResultBanner({ data }: { data: PushSleepDateResponse }) {
  const accent = data.was_overwritten ? "rgba(245,158,11,0.4)" : "rgba(34,197,94,0.4)";
  const accentBg = data.was_overwritten ? "rgba(245,158,11,0.08)" : "rgba(34,197,94,0.08)";
  const accentText = data.was_overwritten ? "var(--severity-warning, #f59e0b)" : "var(--severity-normal, #22c55e)";

  return (
    <div
      role="status"
      style={{
        borderRadius: "var(--radius-md)",
        padding: "10px 12px",
        background: accentBg,
        border: `1px solid ${accent}`,
        fontSize: "13px",
        display: "grid",
        gap: "6px",
      }}
    >
      <strong style={{ color: accentText }}>
        {data.was_overwritten ? "Đã ghi đè" : "Đã tạo mới"} phiên ngày {data.target_date}
      </strong>
      <span style={{ color: "var(--text-secondary)" }}>
        Kịch bản <strong>{data.scenario_id}</strong> · Điểm {data.sleep_score}/100 · Thời lượng {formatDuration(data.duration_minutes)}
      </span>
      {data.disorder_tags.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
          {data.disorder_tags.map((tag) => (
            <span
              key={tag}
              style={{
                padding: "2px 8px",
                borderRadius: "var(--radius-full)",
                background: "rgba(255,255,255,0.06)",
                color: "var(--text-primary)",
                fontSize: "11.5px",
                fontWeight: 600,
                fontFamily: "var(--font-mono)",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function formatDuration(totalMinutes: number) {
  const safe = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(safe / 60);
  const minutes = safe % 60;
  return `${hours} giờ ${minutes} phút`;
}

function extractApiError(error: unknown, fallback: string) {
  if (typeof error === "object" && error && "response" in error) {
    const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }
  }
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return fallback;
}
