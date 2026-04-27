// ---------------------------------------------------------------------------
// Module C — Sessions / Fall Lab. Mirrors `api_server/schemas.py::MotionLatest`.
//
// Arrays are ~100 samples long and come straight from the dataset registry
// — there is no synthetic fallback on either side.  When the focal device
// hasn't produced a tick yet, the API returns the same shape with empty
// arrays so the FE can show a clear empty state instead of fabricating one.
// ---------------------------------------------------------------------------

export interface MotionLatest {
  deviceId: string;
  sessionId: string;
  emittedAt: string;
  activityState: string;
  fallVariant: string | null;
  sampleRate: number | null;
  accelX: number[];
  accelY: number[];
  accelZ: number[];
  accelMag: number[];
  gyroX: number[];
  gyroY: number[];
  gyroZ: number[];
}
