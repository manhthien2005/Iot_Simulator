// ---------------------------------------------------------------------------
// Sleep scenario catalogue (FE mirror of api_server/config/sleep_scenarios.yaml).
//
// Each scenario describes one sleep "personality" the simulator can replay:
//   - severity     -> drives the dot color in SleepScenarioCard.
//   - description  -> short prose for the operator.
//   - targets      -> expected metrics the BE will produce; rendered as a
//                     comparison table so operators can predict the push
//                     result before clicking.  Numbers mirror the YAML
//                     `stats_override` so FE shows what BE will deliver.
//   - disorderTags -> clinical labels the BE attaches to the session
//                     (`osa_severe`, `insomnia`, ...).  Rendered as chips.
//
// `sleepScenarioOptions` keeps the original `{id,label}` shape so existing
// callers (BackfillCard) stay green; rich data lives on each entry's
// extended fields and is opt-in for new components.
// ---------------------------------------------------------------------------

import type { ScenarioSeverity } from "../types/scenario";

export type SleepScenarioId =
  | "good_sleep_night"
  | "fragmented_sleep"
  | "sleep_apnea_mild"
  | "sleep_apnea_severe"
  | "insomnia_pattern"
  | "elderly_normal";

export interface SleepScenarioTargets {
  /** Sleep efficiency, 0-1. */
  efficiency: number;
  /** Stage proportions, 0-1, must sum ~1.0. */
  deepPct: number;
  remPct: number;
  lightPct: number;
  awakePct: number;
  /** Approximate wake count (BE may vary slightly). */
  wakeCount: number;
  /** Optional SpO2 floor override (apnea scenarios only). */
  spo2Min?: number;
  /** Apnea-Hypopnea Index hint, only on apnea scenarios. */
  ahiHint?: string;
}

export interface SleepScenarioOption {
  id: SleepScenarioId;
  label: string;
  severity: ScenarioSeverity;
  description: string;
  targets: SleepScenarioTargets;
  disorderTags: string[];
}

export const sleepScenarioOptions: readonly SleepScenarioOption[] = [
  {
    id: "good_sleep_night",
    label: "Đêm ngủ tốt (AASM chuẩn)",
    severity: "normal",
    description:
      "Chu kỳ NREM+REM theo chuẩn AASM, hiệu suất ≥85%, deep ≥15%, REM ≥20%, wake ít. Dùng làm baseline khoẻ mạnh cho mọi user.",
    targets: {
      efficiency: 0.85,
      deepPct: 0.18,
      remPct: 0.22,
      lightPct: 0.55,
      awakePct: 0.05,
      wakeCount: 1,
    },
    disorderTags: [],
  },
  {
    id: "fragmented_sleep",
    label: "Ngủ phân mảnh",
    severity: "warning",
    description:
      "Nhiều micro-arousal xen kẽ, hiệu suất ~72%, wake_count ≥3 lần. Mô phỏng giấc ngủ rối loạn nhẹ, vẫn còn deep nhưng đứt quãng.",
    targets: {
      efficiency: 0.72,
      deepPct: 0.10,
      remPct: 0.14,
      lightPct: 0.55,
      awakePct: 0.21,
      wakeCount: 4,
    },
    disorderTags: ["arousal"],
  },
  {
    id: "sleep_apnea_mild",
    label: "Ngưng thở nhẹ (AHI ~10)",
    severity: "warning",
    description:
      "Sleep apnea mức nhẹ, SpO2 dip xuống ~91%, 8 lần thức trong đêm. Phù hợp test cảnh báo SpO2 không phải critical nhưng đáng theo dõi.",
    targets: {
      efficiency: 0.76,
      deepPct: 0.10,
      remPct: 0.15,
      lightPct: 0.59,
      awakePct: 0.16,
      wakeCount: 8,
      spo2Min: 91,
      ahiHint: "AHI ~10",
    },
    disorderTags: ["osa_mild"],
  },
  {
    id: "sleep_apnea_severe",
    label: "Ngưng thở nặng (AHI >30)",
    severity: "critical",
    description:
      "Sleep apnea nặng, SpO2 dip tới 84%, 18 lần thức. BE sẽ tag trigger_osa_alert để chạy luồng cảnh báo nguy cấp.",
    targets: {
      efficiency: 0.62,
      deepPct: 0.05,
      remPct: 0.08,
      lightPct: 0.61,
      awakePct: 0.26,
      wakeCount: 18,
      spo2Min: 84,
      ahiHint: "AHI >30",
    },
    disorderTags: ["osa_severe", "trigger_osa_alert"],
  },
  {
    id: "insomnia_pattern",
    label: "Mất ngủ kinh niên",
    severity: "warning",
    description:
      "Pattern mất ngủ: ngủ <5h, hiệu suất 63%, deep và REM thiếu hụt. Latency dài, tỉnh vài lần ban đêm.",
    targets: {
      efficiency: 0.63,
      deepPct: 0.08,
      remPct: 0.12,
      lightPct: 0.65,
      awakePct: 0.15,
      wakeCount: 6,
    },
    disorderTags: ["insomnia"],
  },
  {
    id: "elderly_normal",
    label: "Ngủ người cao tuổi (bình thường)",
    severity: "normal",
    description:
      "Pattern bình thường theo tuổi tác: deep giảm (~11%), REM ~19%, nhiều light hơn. Không phải bệnh lý.",
    targets: {
      efficiency: 0.80,
      deepPct: 0.11,
      remPct: 0.19,
      lightPct: 0.60,
      awakePct: 0.10,
      wakeCount: 2,
    },
    disorderTags: ["age_related"],
  },
] as const;

export const DEFAULT_SLEEP_SCENARIO_ID: SleepScenarioId = "good_sleep_night";

export function getSleepScenario(id: string): SleepScenarioOption | undefined {
  return sleepScenarioOptions.find((option) => option.id === (id as SleepScenarioId));
}
