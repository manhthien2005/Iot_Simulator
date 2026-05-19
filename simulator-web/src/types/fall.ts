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

/** Pre-trigger evaluation outcome the BE is expected to produce for a variant.
 *
 *  Values mirror `pre_model_trigger.fall_pre_trigger.FallPreTrigger.evaluate`:
 *  - `"hard"` — accel_mag_peak_g >= 3.0g (IMPACT_PEAK_3G fired).
 *  - `"soft"` — accel_mag_peak_g >= 2.5g + posture_change_angle_deg >= 45°
 *    OR + post_impact_low_motion_duration_s >= 1.0s. Routes to the model API.
 *  - `"none"` — neither hard nor soft criteria met; no model-call performed.
 */
export type ExpectedPreTrigger = "hard" | "soft" | "none";

/** Inclusive numeric range for an expected metric (peak |a| or AI probability). */
export interface NumericRange {
  min: number;
  max: number;
}

export interface FallVariantSpec {
  id: FallVariantId;
  /** Operator-facing label (Vietnamese). */
  label: string;
  /** Short subtitle shown under the label. */
  subtitle: string;
  /** Long description shown in the variant tooltip / detail card. */
  description: string;
  /** Concise physical action the operator is mimicking (separate from
   *  `description` so the FE can show "Vung tay mạnh, đặt thiết bị xuống"
   *  without the policy-detail tail). */
  physicalAction: string;
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
  /** Expected accel-magnitude peak (g) the simulator's MotionGenerator
   *  produces for this variant.  Used by the Fall Lab evidence checklist
   *  to confirm the BE pre-trigger threshold (3.0g hard / 2.5g soft) was
   *  actually crossed.  Numbers come from sampling the parquet dataset
   *  windows — see `simulator_core.generators.MotionGenerator`. */
  expectedPeakG: NumericRange;
  /** Expected posture-change angle (degrees).  `null` for variants where
   *  posture isn't a primary signal (false-alarm / slip-recovery). */
  expectedPostureDeg: NumericRange | null;
  /** Pre-trigger outcome the BE should reach with this variant. */
  expectedPreTrigger: ExpectedPreTrigger;
  /** Whether `simulator_core.fall_ai_client.FALL_VARIANT_CONTEXT` injects
   *  binary environment cues (floor_vibration / pressure_mat = 1.0 from
   *  the impact sample).  Mirrors that map exactly. */
  injectEnvironment: boolean;
  /** AI risk band the model should report (mirrors `AIPredictionBand`). */
  expectedAiBand: AIPredictionBand;
  /** AI predicted probability range (0..1).  Cross-checked against the
   *  model verdict in the evidence checklist. */
  expectedAiProbability: NumericRange;
}

/**
 * Ordered catalogue used by the variant picker grid.  Order matters —
 * we present the safest scenarios first so the operator can warm up
 * with a "false_fall" before triggering a real "fall_no_response".
 *
 * Numeric expectations (`expectedPeakG`, `expectedPostureDeg`,
 * `expectedAiProbability`, `expectedPreTrigger`) come from three sources
 * that the Fall Lab evidence checklist cross-checks at runtime:
 *
 *   1. Pre-trigger thresholds: `pre_model_trigger/fall_pipeline_wrist_config.json`
 *      stage_1_pretrigger (hard 3.0g, soft 2.5g + 45° / 1.0s low-motion).
 *   2. Environment-injection map: `simulator_core.fall_ai_client.FALL_VARIANT_CONTEXT`
 *      (mirrored exactly into `injectEnvironment`).
 *   3. Model API response distribution sampled from the parquet windows
 *      that `MotionGenerator` replays per variant — used to set the
 *      AI band + probability range.
 */
export const FALL_VARIANT_CATALOGUE: readonly FallVariantSpec[] = [
  {
    id: "false_fall",
    label: "Té ngã giả",
    subtitle: "AI nên báo: bình thường",
    description:
      "Chuyển động giả-té ngã (vung tay mạnh, đặt thiết bị xuống). " +
      "BE không vào fall_countdown và không đẩy alert; AI có cơ hội xác minh true-negative.",
    physicalAction: "Vung tay mạnh, đặt thiết bị xuống",
    severity: "normal",
    countdownSec: 0,
    autoResolve: false,
    pushesAlert: false,
    allowsCancel: false,
    expectedPeakG: { min: 1.2, max: 1.8 },
    expectedPostureDeg: null,
    expectedPreTrigger: "none",
    injectEnvironment: false,
    expectedAiBand: "normal",
    expectedAiProbability: { min: 0.05, max: 0.25 },
  },
  {
    id: "slip_recovery",
    label: "Trượt — tự đứng dậy",
    subtitle: "AI nên báo: bình thường",
    description:
      "Trượt nhẹ rồi tự gượng dậy ngay. Không vào fall_countdown, không alert — " +
      "đây là test true-negative cho AI.",
    physicalAction: "Trượt nhẹ rồi tự gượng dậy ngay",
    severity: "normal",
    countdownSec: 0,
    autoResolve: false,
    pushesAlert: false,
    allowsCancel: false,
    expectedPeakG: { min: 1.5, max: 2.3 },
    expectedPostureDeg: { min: 20, max: 40 },
    expectedPreTrigger: "none",
    injectEnvironment: false,
    expectedAiBand: "normal",
    expectedAiProbability: { min: 0.10, max: 0.30 },
  },
  {
    id: "fall_brief",
    label: "Té ngã nhẹ",
    subtitle: "Cảnh báo · auto-resolve 10 giây",
    description:
      "Té ngã có tác động nhẹ, người dùng có khả năng tự hồi phục. " +
      "BE chạy countdown 10 giây và tự huỷ — operator có thể kịp 'Tôi ổn' nhưng không bắt buộc.",
    physicalAction: "Va chạm nhẹ, có khả năng tự hồi phục",
    severity: "warning",
    countdownSec: 10,
    autoResolve: true,
    pushesAlert: true,
    allowsCancel: true,
    expectedPeakG: { min: 2.5, max: 3.0 },
    expectedPostureDeg: { min: 40, max: 60 },
    expectedPreTrigger: "soft",
    injectEnvironment: false,
    expectedAiBand: "warning",
    expectedAiProbability: { min: 0.35, max: 0.55 },
  },
  {
    id: "fall_from_bed",
    label: "Té khỏi giường",
    subtitle: "Critical · 30 giây",
    description:
      "Người đang ngủ té khỏi giường — chuyển động nhỏ, vitals chậm. " +
      "Đây là edge case: AI cần phát hiện được dù tín hiệu yếu.",
    physicalAction: "Té khỏi giường khi đang ngủ (edge case)",
    severity: "critical",
    countdownSec: 30,
    autoResolve: false,
    pushesAlert: true,
    allowsCancel: true,
    expectedPeakG: { min: 2.5, max: 3.5 },
    expectedPostureDeg: { min: 60, max: 90 },
    expectedPreTrigger: "soft",
    injectEnvironment: true,
    expectedAiBand: "warning",
    expectedAiProbability: { min: 0.55, max: 0.75 },
  },
  {
    id: "confirmed",
    label: "Té ngã xác nhận",
    subtitle: "Critical · 30 giây · cho phép huỷ",
    description:
      "Té ngã rõ rệt — đầy đủ va chạm + bất động sau đó. " +
      "BE đẩy alert ngay, countdown 30 giây để operator xác nhận hoặc huỷ.",
    physicalAction: "Va chạm rõ rệt + bất động sau đó",
    severity: "critical",
    countdownSec: 30,
    autoResolve: false,
    pushesAlert: true,
    allowsCancel: true,
    expectedPeakG: { min: 3.5, max: 4.5 },
    expectedPostureDeg: { min: 60, max: 90 },
    expectedPreTrigger: "hard",
    injectEnvironment: true,
    expectedAiBand: "critical",
    expectedAiProbability: { min: 0.75, max: 0.95 },
  },
  {
    id: "fall_no_response",
    label: "Té ngã + không phản hồi",
    subtitle: "Critical · 30 giây · không huỷ",
    description:
      "Worst case: té ngã và không tự đứng dậy. BE chặn 'Tôi ổn' để mô phỏng " +
      "leo thang SOS thực tế khi countdown hết giờ.",
    physicalAction: "Té ngã, không tự đứng dậy, không huỷ được",
    severity: "critical",
    countdownSec: 30,
    autoResolve: false,
    pushesAlert: true,
    allowsCancel: false,
    expectedPeakG: { min: 3.8, max: 5.0 },
    expectedPostureDeg: { min: 70, max: 90 },
    expectedPreTrigger: "hard",
    injectEnvironment: true,
    expectedAiBand: "critical",
    expectedAiProbability: { min: 0.85, max: 0.98 },
  },
] as const;
