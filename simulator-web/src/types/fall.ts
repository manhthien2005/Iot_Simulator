// ---------------------------------------------------------------------------
// Module C — Fall lifecycle mirror of `api_server/schemas.py::FallState`.
//
// Drives the Sessions page Fall Lab countdown and `<MotionPreviewPanel/>`'s
// activity badge.  All fields are derived on the BE — the FE never invents
// the countdown, never runs its own setInterval clock, and never tracks
// the "last variant" locally.
// ---------------------------------------------------------------------------

import type { DeviceState } from "./device";
import type { AlertSeverity } from "./event";

export type FallStateValue =
  | "idle"
  | "fall_detected"
  | "fall_countdown"
  | "sos_active"
  | "fall_resolved";

export interface FallEventEntry {
  id: string;
  timestamp: string;
  eventType: string;
  severity: AlertSeverity;
  variant: string | null;
}

export interface FallState {
  deviceId: string;
  sessionId: string;
  deviceState: DeviceState;
  activityState: string;
  fallVariant: string | null;
  fallState: FallStateValue;
  lastFallEventAt: string | null;
  countdownStartedAt: string | null;
  countdownRemainingSec: number;
  countdownTotalSec: number;
  sosActive: boolean;
  recentFallEvents: FallEventEntry[];
}
