import { useEffect, useRef, useState } from "react";
import type { HealthTelemetryBlock } from "../types/health";

// ---------------------------------------------------------------------------
// useKpiHistory — client-side ring buffer for the 4 telemetry KPIs.
//
// The backend's /api/v1/sim/health response only carries point-in-time values
// for `telemetry`.  The dashboard wants a 20-point trend sparkline per KPI
// so an operator can visually distinguish "spiked once" from "steadily
// climbing".  Persisting trend history server-side would be over-kill for
// what is a viewer convenience — instead we keep a small in-memory buffer
// that grows by one sample every time React Query hands us a fresh
// telemetry payload (≈every 15 s, matching POLL_INTERVALS.health).
//
// The buffer is intentionally NOT persisted: it should reset on full page
// reload so the operator never reads stale trends after a long idle.
// ---------------------------------------------------------------------------

const BUFFER_SIZE = 20;

export interface KpiHistory {
  devicesSimulated: number[];
  sessionsRunning: number[];
  alertsLastHour: number[];
  avgPublishLatencyMs: number[];
}

const EMPTY_HISTORY: KpiHistory = {
  devicesSimulated: [],
  sessionsRunning: [],
  alertsLastHour: [],
  avgPublishLatencyMs: [],
};

export function useKpiHistory(telemetry: HealthTelemetryBlock | undefined): KpiHistory {
  const [history, setHistory] = useState<KpiHistory>(EMPTY_HISTORY);
  // Stable snapshot key so we only push when the payload actually changes,
  // not on every render or React Query placeholder refresh.
  const lastSnapshot = useRef<string>("");

  useEffect(() => {
    if (!telemetry) return;
    const snapshot = `${telemetry.devicesSimulated}:${telemetry.sessionsRunning}:${telemetry.alertsLastHour}:${telemetry.avgPublishLatencyMs}`;
    if (snapshot === lastSnapshot.current) return;
    lastSnapshot.current = snapshot;

    setHistory((prev) => ({
      devicesSimulated: pushBounded(prev.devicesSimulated, telemetry.devicesSimulated),
      sessionsRunning: pushBounded(prev.sessionsRunning, telemetry.sessionsRunning),
      alertsLastHour: pushBounded(prev.alertsLastHour, telemetry.alertsLastHour),
      avgPublishLatencyMs: pushBounded(prev.avgPublishLatencyMs, telemetry.avgPublishLatencyMs),
    }));
  }, [telemetry]);

  return history;
}

function pushBounded(buffer: number[], value: number): number[] {
  const next = buffer.length >= BUFFER_SIZE ? buffer.slice(1) : buffer.slice();
  next.push(value);
  return next;
}
