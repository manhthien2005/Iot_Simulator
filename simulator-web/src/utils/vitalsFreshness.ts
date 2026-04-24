export function parseVitalsTimestamp(value: string | number | Date | null | undefined): Date | null {
  if (value == null) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === "number") {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const text = String(value).trim();
  if (!text) return null;
  const hasZone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(text);
  const date = new Date(hasZone ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function inferExpectedIntervalMsFromSamples(
  timestamps: Array<string | number | Date | null | undefined>,
  fallbackMs = 15_000
): number {
  if (timestamps.length < 2) return fallbackMs;
  const latest = parseVitalsTimestamp(timestamps[timestamps.length - 1]);
  const previous = parseVitalsTimestamp(timestamps[timestamps.length - 2]);
  if (!latest || !previous) return fallbackMs;
  return Math.max(1_000, latest.getTime() - previous.getTime());
}

export function resolveVitalsFreshnessTimestamp(...values: Array<string | number | Date | null | undefined>): Date | null {
  const validDates = values
    .map((value) => parseVitalsTimestamp(value))
    .filter((value): value is Date => value instanceof Date);

  if (!validDates.length) return null;
  return validDates.reduce((latest, current) => (current.getTime() > latest.getTime() ? current : latest));
}

export function isVitalsStreamStale(params: {
  sampleTimestamp?: string | number | Date | null;
  runtimeTickAt?: string | number | Date | null;
  deviceLastSeenAt?: string | number | Date | null;
  expectedIntervalMs?: number;
  nowMs?: number;
}): boolean {
  const freshest = resolveVitalsFreshnessTimestamp(
    params.runtimeTickAt,
    params.deviceLastSeenAt,
    params.sampleTimestamp
  );

  if (!freshest) return false;

  const thresholdMs = Math.max((params.expectedIntervalMs ?? 15_000) * 2, 10_000);
  return (params.nowMs ?? Date.now()) - freshest.getTime() > thresholdMs;
}
