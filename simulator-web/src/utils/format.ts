export function formatBpm(value: number): string {
  return `${Math.round(value)} bpm`;
}

export function formatTime(iso: string | null): string {
  if (!iso) return "-";
  const date = new Date(iso);
  return date.toLocaleTimeString();
}

export function formatBattery(value: number): string {
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}

