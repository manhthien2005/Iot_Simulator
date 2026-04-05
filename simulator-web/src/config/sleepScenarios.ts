export const sleepScenarioOptions = [
  { id: "good_sleep_night", label: "Đêm ngủ tốt (AASM chuẩn)" },
  { id: "fragmented_sleep", label: "Ngủ phân mảnh" },
  { id: "sleep_apnea_mild", label: "Ngưng thở nhẹ (AHI ~10)" },
  { id: "sleep_apnea_severe", label: "Ngưng thở nặng (AHI >30)" },
  { id: "insomnia_pattern", label: "Mất ngủ kinh niên" },
  { id: "elderly_normal", label: "Ngủ người cao tuổi (bình thường)" },
] as const;

export type SleepScenarioId = (typeof sleepScenarioOptions)[number]["id"];
