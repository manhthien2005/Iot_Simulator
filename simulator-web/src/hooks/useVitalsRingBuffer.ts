import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchLatestVitals } from "../services/vitalsApi";
import { POLL_INTERVALS } from "../config/defaults";
import type { VitalsSample } from "../types/vitals";

// ---------------------------------------------------------------------------
// useVitalsRingBuffer — Module FA Phase 1.
//
// The Fall Lab needs HR / SpO2 / BP / RR samples in a +/-60s window around
// `lastFallEventAt` so it can render the post-fall vitals delta chart.
//
// The simulator BE only exposes `/api/v1/sim/vitals/latest` (one sample,
// no range query), so we ring-buffer samples client-side.  Each polling
// tick (`POLL_INTERVALS.vitalsLatest`) appends the latest sample, evicting
// anything older than `windowSec` seconds.
//
// Key design points:
//   * Buffer is keyed by `deviceId` so switching focus device on the Fall
//     Lab page resets cleanly without leaking samples.
//   * Samples are de-duped by `timestamp` (BE may return the same sample
//     multiple times if no new tick happened between polls).
//   * Disabled when `deviceId` is null — caller renders empty state.
//
// Returns the buffered samples plus the latest sample (so callers don't
// need to re-derive the "now" value from the array tail).
// ---------------------------------------------------------------------------

export interface VitalsBufferEntry extends VitalsSample {
  /** Numeric ms since epoch — convenience for chart math. */
  timestampMs: number;
}

interface Options {
  /** How many seconds of history to keep.  Defaults to 120s (covers +/-60s). */
  windowSec?: number;
  /** Override the polling interval. */
  refetchInterval?: number;
}

const DEFAULT_WINDOW_SEC = 120;

export function useVitalsRingBuffer(deviceId: string | null, options: Options = {}) {
  const windowSec = options.windowSec ?? DEFAULT_WINDOW_SEC;
  const refetchInterval = options.refetchInterval ?? POLL_INTERVALS.vitalsLatest ?? 2_000;

  const [buffer, setBuffer] = useState<VitalsBufferEntry[]>([]);
  const lastDeviceIdRef = useRef<string | null>(null);

  // Reset buffer when device changes.
  useEffect(() => {
    if (lastDeviceIdRef.current !== deviceId) {
      lastDeviceIdRef.current = deviceId;
      setBuffer([]);
    }
  }, [deviceId]);

  const query = useQuery({
    queryKey: ["vitals", "latest", deviceId],
    queryFn: () => fetchLatestVitals(deviceId!),
    enabled: Boolean(deviceId),
    refetchInterval,
    staleTime: refetchInterval,
  });

  // Append latest sample to the buffer when it changes.
  useEffect(() => {
    const sample = query.data;
    if (!sample) return;
    const ts = Date.parse(sample.timestamp);
    if (Number.isNaN(ts)) return;
    setBuffer((prev) => {
      // Skip if we already have this exact timestamp (BE returned the
      // same tick — no new info).
      if (prev.length > 0 && prev[prev.length - 1].timestampMs === ts) {
        return prev;
      }
      const next: VitalsBufferEntry = { ...sample, timestampMs: ts };
      const cutoff = ts - windowSec * 1000;
      const merged = [...prev, next].filter((entry) => entry.timestampMs >= cutoff);
      // Re-sort defensively in case of clock skew between polls.
      merged.sort((a, b) => a.timestampMs - b.timestampMs);
      return merged;
    });
  }, [query.data, windowSec]);

  return {
    buffer,
    latest: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error as Error | null,
  };
}
