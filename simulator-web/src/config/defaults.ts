// ── Polling intervals (ms) ──────────────────────────────────────────
export const POLL_INTERVALS = {
  sessions: 3_000,
  verification: 3_000,
  events: 3_000,
  dashboard: 5_000,
  devices: 5_000,
  dbDevices: 5_000,
  vitals: 1_000,
  health: 15_000,
  analytics: 15_000,
  analyticsRisk: 10_000,
  motionPreview: 1_000,
  fallLabEvents: 1_500,
} as const;

// ── Fall detection ──────────────────────────────────────────────────
export const FALL_COUNTDOWN_SECONDS = 30;
export const FALL_LAB_RECENT_EVENTS_LIMIT = 30;
