import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// useRelativeTime — re-renders every `tickMs` so callers see "fresh" age
// strings without manual timers.  Returns the human-friendly label plus the
// raw `ageMs` so the caller can branch on liveness thresholds.
// ---------------------------------------------------------------------------

export interface RelativeTime {
  label: string;
  ageMs: number | null;
}

export function useRelativeTime(iso: string | null | undefined, tickMs = 1000): RelativeTime {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!iso) return;
    const id = window.setInterval(() => setNow(Date.now()), tickMs);
    return () => window.clearInterval(id);
  }, [iso, tickMs]);

  if (!iso) return { label: "—", ageMs: null };

  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return { label: "—", ageMs: null };

  const ageMs = Math.max(0, now - ts);
  return { label: formatAge(ageMs), ageMs };
}

export function formatAge(ageMs: number): string {
  const sec = Math.floor(ageMs / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  if (min < 60) return remSec === 0 ? `${min}m` : `${min}m${remSec}s`;
  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  return remMin === 0 ? `${hr}h` : `${hr}h${remMin}m`;
}
