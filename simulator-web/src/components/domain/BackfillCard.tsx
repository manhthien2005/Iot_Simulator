import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { backfillSleep } from "../../services/analyticsApi";
import type { BackfillSleepResponse } from "../../types/analytics";
import { notify } from "../../utils/toast";

const sleepScenarioOptions = [
  { id: "good_sleep_night", label: "Đêm ngủ tốt (AASM chuẩn)" },
  { id: "fragmented_sleep", label: "Ngủ phân mảnh" },
  { id: "sleep_apnea_mild", label: "Ngưng thở nhẹ (AHI ~10)" },
  { id: "sleep_apnea_severe", label: "Ngưng thở nặng (AHI >30)" },
  { id: "insomnia_pattern", label: "Mất ngủ kinh niên" },
  { id: "elderly_normal", label: "Ngủ người cao tuổi (bình thường)" },
] as const;

export interface BackfillCardProps {
  deviceId: string;
  onCompleted?: () => void | Promise<void>;
}

const fieldStyle: React.CSSProperties = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  minHeight: "36px",
  padding: "0 10px",
};

export function BackfillCard({ deviceId, onCompleted }: BackfillCardProps) {
  const [days, setDays] = useState(30);
  const [scenarioId, setScenarioId] = useState("good_sleep_night");
  const [result, setResult] = useState<BackfillSleepResponse | null>(null);

  const backfillMutation = useMutation({
    mutationFn: () =>
      backfillSleep({
        device_id: deviceId,
        days_behind: days,
        scenario_id: scenarioId,
      }),
    onSuccess: async (data) => {
      setResult(data);
      notify.success(`Backfill hoàn tất: ${data.pushed}/${data.total_days} ngày thành công.`);
      await onCompleted?.();
    },
    onError: () => {
      notify.error("Backfill thất bại. Kiểm tra kết nối Backend.");
    },
  });

  return (
    <Card header={<strong>Tiêm dữ liệu lịch sử giấc ngủ</strong>}>
      <div style={{ display: "grid", gap: "10px" }}>
        <small style={{ color: "var(--text-secondary)" }}>
          Bơm N ngày dữ liệu giấc ngủ vào DB để AI có đủ lịch sử phân tích. Mỗi ngày được gán timestamp ngẫu nhiên
          trong khung 21:00-01:00.
        </small>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr auto",
            gap: "8px",
            alignItems: "end",
          }}
        >
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Kịch bản
            <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)} style={fieldStyle}>
              {sleepScenarioOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "grid", gap: "4px", color: "var(--text-secondary)", fontSize: "12px" }}>
            Số ngày (1-90)
            <input
              type="number"
              min={1}
              max={90}
              value={days}
              onChange={(event) => {
                const nextValue = Number(event.target.value);
                if (!Number.isFinite(nextValue)) {
                  setDays(1);
                  return;
                }
                setDays(Math.max(1, Math.min(90, nextValue)));
              }}
              style={fieldStyle}
            />
          </label>
          <Button
            variant="outline"
            onClick={() => backfillMutation.mutate()}
            loading={backfillMutation.isPending}
            disabled={!deviceId}
          >
            Bắt đầu backfill
          </Button>
        </div>

        {result ? (
          <div
            style={{
              borderRadius: "var(--radius-md)",
              padding: "10px 12px",
              background: result.errors.length === 0 ? "rgba(34,197,94,0.08)" : "rgba(245,158,11,0.08)",
              border: `1px solid ${
                result.errors.length === 0 ? "rgba(34,197,94,0.3)" : "rgba(245,158,11,0.35)"
              }`,
              fontSize: "13px",
            }}
          >
            ✅ {result.pushed}/{result.total_days} ngày thành công
            {result.skipped > 0 ? ` | ⚠️ ${result.skipped} ngày bị bỏ qua` : null}
            {result.errors.length > 0 ? (
              <details style={{ marginTop: "6px" }}>
                <summary style={{ cursor: "pointer", color: "var(--text-secondary)" }}>{result.errors.length} lỗi chi tiết</summary>
                <ul style={{ margin: "6px 0 0", paddingLeft: "16px", color: "var(--text-secondary)" }}>
                  {result.errors.map((error, index) => (
                    <li key={`${index}-${error}`} style={{ fontSize: "12px" }}>
                      {error}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
