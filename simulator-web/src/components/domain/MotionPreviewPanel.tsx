import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { VitalsSample } from "../../types/vitals";
import type { SimulatedDevice } from "../../types/device";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { POLL_INTERVALS } from "../../config/defaults";

interface MotionPreviewPanelProps {
  selectedDevice: SimulatedDevice | null;
  currentVitals?: VitalsSample | null;
}

interface MotionRow {
  key: string;
  value: number;
  emphasis?: boolean;
}

function pseudoMetric(seed: string, offset: number, timeSlice: number, amplitude = 1): number {
  const hash = [...seed].reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const base = Math.abs(Math.sin((hash + offset + timeSlice * 0.7) * 0.11) * 8.2 * amplitude);
  const micro = Math.abs(Math.cos((hash * 0.13 + offset + timeSlice * 1.9) * 0.09) * 1.8 * amplitude);
  return base + micro;
}

export const MotionPreviewPanel = memo(function MotionPreviewPanel({ selectedDevice, currentVitals }: MotionPreviewPanelProps) {
  const [timeSlice, setTimeSlice] = useState(0);
  const isFalling = currentVitals?.activityLabel === "falling";
  const fillColor = isFalling ? "var(--severity-critical)" : "var(--accent-cyan)";

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startInterval = useCallback(() => {
    if (intervalRef.current) return;
    intervalRef.current = window.setInterval(() => {
      setTimeSlice((prev) => prev + 1);
    }, POLL_INTERVALS.motionPreview);
  }, []);

  const stopInterval = useCallback(() => {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!selectedDevice) return;
    if (!document.hidden) startInterval();

    const handler = () => {
      if (document.hidden) stopInterval();
      else startInterval();
    };
    document.addEventListener("visibilitychange", handler);
    return () => {
      stopInterval();
      document.removeEventListener("visibilitychange", handler);
    };
  }, [selectedDevice?.id, startInterval, stopInterval]);

  const rows = useMemo<MotionRow[]>(() => {
    const seed = selectedDevice?.id ?? "none";
    const amplitude = selectedDevice?.state === "fall_countdown" || selectedDevice?.state === "critical" ? 1.35 : 1;
    const accelRows = [
      { key: "Gia tốc X", value: pseudoMetric(seed, 1, timeSlice, amplitude) },
      { key: "Gia tốc Y", value: pseudoMetric(seed, 2, timeSlice, amplitude) },
      { key: "Gia tốc Z", value: pseudoMetric(seed, 3, timeSlice, amplitude) },
    ];
    const accelMagnitude = Math.sqrt(accelRows.reduce((sum, row) => sum + row.value ** 2, 0));
    return [
      ...accelRows,
      { key: "Biên độ gia tốc", value: accelMagnitude, emphasis: true },
      { key: "Con quay X", value: pseudoMetric(seed, 4, timeSlice, amplitude) },
      { key: "Con quay Y", value: pseudoMetric(seed, 5, timeSlice, amplitude) },
      { key: "Con quay Z", value: pseudoMetric(seed, 6, timeSlice, amplitude) },
    ];
  }, [selectedDevice?.id, selectedDevice?.state, timeSlice]);

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
          <strong>Xem trước chuyển động</strong>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <Badge severity="info">Synthetic fallback</Badge>
            {currentVitals?.activityLabel ? (
              <Badge severity={isFalling ? "critical" : "normal"}>{currentVitals.activityLabel}</Badge>
            ) : null}
          </div>
        </div>
      }
    >
      {selectedDevice ? (
        <div style={{ display: "grid", gap: "8px" }}>
          <small style={{ color: "var(--text-muted)" }}>
            Nguồn hiển thị: dữ liệu chuyển động giả lập, dùng để xem trước khi backend motion/latest chưa có sẵn.
          </small>
          {rows.map((row) => (
            <div
              key={row.key}
              style={{
                display: "grid",
                gridTemplateColumns: "120px 1fr 70px",
                gap: "8px",
                alignItems: "center",
              }}
            >
              <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{row.key}</span>
              <div style={{ height: row.emphasis ? "10px" : "8px", borderRadius: "999px", background: "var(--bg-base)", overflow: "hidden" }}>
                <div
                  className={isFalling ? "motion-bar-fill motion-bar-fill--falling" : "motion-bar-fill"}
                  style={{
                    width: `${Math.min(row.value * (row.emphasis ? 7 : 10), 100)}%`,
                    height: "100%",
                    background: fillColor,
                    opacity: row.emphasis ? 0.95 : 0.85,
                  }}
                />
              </div>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", textAlign: "right" }}>{row.value.toFixed(2)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: "var(--text-secondary)" }}>Chọn thiết bị để xem trước chuyển động.</p>
      )}
    </Card>
  );
});
