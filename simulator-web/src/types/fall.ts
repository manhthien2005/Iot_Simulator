// ---------------------------------------------------------------------------
// Module C + Module FA — Fall lifecycle mirror of `api_server/schemas.py`.
//
// Drives the Fall Lab page (`/fall-lab`) and `<MotionPreviewPanel/>`'s
// activity badge.  All fields are derived on the BE — the FE never invents
// the countdown, never runs its own setInterval clock, and never tracks
// the "last variant" locally.
//
// Module FA additions:
//   * `AIPrediction` — fall AI verdict from `healthguard-model-api`
//     `/api/v1/fall/predict` (port 8001), normalised by
//     `simulator_core.fall_ai_client.normalise_verdict()`.
//   * `MotionWindowRef` — pointer to the 50-sample window the verdict
//     was computed against.  Lets the FE align its trace highlight to
//     the same data the model classified.
//   * `CountdownPolicy` — variant-specific SOS countdown policy.  The
//     same `FallState` shape is returned for every variant; only the
//     *policy* differs (false_fall has 0 s; fall_brief auto-resolves
//     at 10 s; confirmed/no_response use the standard 30 s).
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

// ---- Module FA — AI verdict surface ---------------------------------------

export type AIPredictionLabel =
  | "normal"
  | "possible_fall"
  | "likely_fall"
  | "critical_fall";

export type AIPredictionBand = "normal" | "warning" | "critical";

/** ``modelStatus`` distinguishes ok / offline / no_window / skipped. */
export type AIModelStatus = "ok" | "offline" | "no_window" | "skipped";

export interface AITopFeature {
  featureName: string;
  contribution: number;
  vietnameseExplanation: string;
  severity: "normal" | "warning" | "critical";
}

export interface AIPrediction {
  label: AIPredictionLabel;
  probability: number;
  confidence: number;
  riskBand: AIPredictionBand;
  requiresAttention: boolean;
  highPriorityAlert: boolean;
  explanationSummary: string | null;
  topFeatures: AITopFeature[];
  predictedAt: string;
  modelStatus: AIModelStatus;
}

export interface MotionWindowRef {
  emittedAt: string;
  sampleCount: number;
  sampleRate: number | null;
  fallVariant: string | null;
}

export interface CountdownPolicy {
  totalSec: number;
  autoResolve: boolean;
  allowsCancel: boolean;
}

// ---- Aggregate fall state -------------------------------------------------

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
  /** Module FA — AI verdict for the most recent inject_event. */
  aiPrediction: AIPrediction | null;
  /** Module FA — motion window ref the verdict was computed on. */
  motionWindowRef: MotionWindowRef | null;
  /** Module FA — variant-specific countdown policy. */
  countdownPolicy: CountdownPolicy | null;
}

// ---- Variant catalogue (FE source of truth for the operator picker) ------

export type FallVariantId =
  | "false_fall"
  | "slip_recovery"
  | "fall_brief"
  | "fall_from_bed"
  | "confirmed"
  | "fall_no_response";

export interface FallVariantSpec {
  id: FallVariantId;
  /** Operator-facing label (Vietnamese). */
  label: string;
  /** Short subtitle shown under the label. */
  subtitle: string;
  /** Long description shown in the variant tooltip / detail card. */
  description: string;
  /** Severity of the *button* — driven by what the BE policy escalates to. */
  severity: "normal" | "warning" | "critical";
  /** SOS countdown the BE enforces for this variant. */
  countdownSec: number;
  /** Whether the BE auto-resolves the countdown without operator action. */
  autoResolve: boolean;
  /** Whether the BE pushes a real alert webhook on inject. */
  pushesAlert: boolean;
  /** Whether the operator's "Tôi ổn" button is honoured. */
  allowsCancel: boolean;
}

/**
 * Ordered catalogue used by the variant picker grid.  Order matters —
 * we present the safest scenarios first so the operator can warm up
 * with a "false_fall" before triggering a real "fall_no_response".
 */
export const FALL_VARIANT_CATALOGUE: readonly FallVariantSpec[] = [
  {
    id: "false_fall",
    label: "Té ngã giả",
    subtitle: "AI nên báo: bình thường",
    description:
      "Chuyển động giả-té ngã (vung tay mạnh, đặt thiết bị xuống). " +
      "BE không vào fall_countdown và không đẩy alert; AI có cơ hội xác minh true-negative.",
    severity: "normal",
    countdownSec: 0,
    autoResolve: false,
    pushesAlert: false,
    allowsCancel: false,
  },
  {
    id: "slip_recovery",
    label: "Trượt — tự đứng dậy",
    subtitle: "AI nên báo: bình thường",
    description:
      "Trượt nhẹ rồi tự gượng dậy ngay. Không vào fall_countdown, không alert — " +
      "đây là test true-negative cho AI.",
    severity: "normal",
    countdownSec: 0,
    autoResolve: false,
    pushesAlert: false,
    allowsCancel: false,
  },
  {
    id: "fall_brief",
    label: "Té ngã nhẹ",
    subtitle: "Cảnh báo · auto-resolve 10 giây",
    description:
      "Té ngã có tác động nhẹ, người dùng có khả năng tự hồi phục. " +
      "BE chạy countdown 10 giây và tự huỷ — operator có thể kịp 'Tôi ổn' nhưng không bắt buộc.",
    severity: "warning",
    countdownSec: 10,
    autoResolve: true,
    pushesAlert: true,
    allowsCancel: true,
  },
  {
    id: "fall_from_bed",
    label: "Té khỏi giường",
    subtitle: "Critical · 30 giây",
    description:
      "Người đang ngủ té khỏi giường — chuyển động nhỏ, vitals chậm. " +
      "Đây là edge case: AI cần phát hiện được dù tín hiệu yếu.",
    severity: "critical",
    countdownSec: 30,
    autoResolve: false,
    pushesAlert: true,
    allowsCancel: true,
  },
  {
    id: "confirmed",
    label: "Té ngã xác nhận",
    subtitle: "Critical · 30 giây · cho phép huỷ",
    description:
      "Té ngã rõ rệt — đầy đủ va chạm + bất động sau đó. " +
      "BE đẩy alert ngay, countdown 30 giây để operator xác nhận hoặc huỷ.",
    severity: "critical",
    countdownSec: 30,
    autoResolve: false,
    pushesAlert: true,
    allowsCancel: true,
  },
  {
    id: "fall_no_response",
    label: "Té ngã + không phản hồi",
    subtitle: "Critical · 30 giây · không huỷ",
    description:
      "Worst case: té ngã và không tự đứng dậy. BE chặn 'Tôi ổn' để mô phỏng " +
      "leo thang SOS thực tế khi countdown hết giờ.",
    severity: "critical",
    countdownSec: 30,
    autoResolve: false,
    pushesAlert: true,
    allowsCancel: false,
  },
] as const;
