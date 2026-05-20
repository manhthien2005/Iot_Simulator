// ---------------------------------------------------------------------------
// thresholdMeta.ts — metadata cho từng key threshold mà simulator phơi ra.
//
// Map từ key (snake_case match BE) sang nhóm (HR/SpO2/RR/BP/Sleep events),
// đơn vị, mức độ (warning/critical), bound (low/high/single) + 1 câu hint
// giải thích ý nghĩa lâm sàng. Dùng cho ThresholdInspectorPanel để render
// theo nhóm thay vì 1 bảng phẳng.
// ---------------------------------------------------------------------------

export type ThresholdGroup = "hr" | "spo2" | "rr" | "bp" | "sleep_event";
export type ThresholdSeverity = "critical" | "warning" | "info";
export type ThresholdBound = "low" | "high" | "single";

export interface ThresholdGroupMeta {
  key: ThresholdGroup;
  label: string;
  description: string;
  unit: string;
}

export interface ThresholdInfo {
  group: ThresholdGroup;
  severity: ThresholdSeverity;
  bound: ThresholdBound;
  label: string;
  hint: string;
}

export const THRESHOLD_GROUPS: ThresholdGroupMeta[] = [
  {
    key: "hr",
    label: "Nhịp tim",
    description: "Nhịp tim đo qua PPG/ECG, đơn vị bpm.",
    unit: "bpm",
  },
  {
    key: "spo2",
    label: "SpO₂",
    description: "Độ bão hòa oxy máu, đơn vị %.",
    unit: "%",
  },
  {
    key: "rr",
    label: "Nhịp thở",
    description: "Số lần thở/phút, đơn vị br/min.",
    unit: "br/min",
  },
  {
    key: "bp",
    label: "Huyết áp",
    description: "Huyết áp tâm thu/tâm trương, đơn vị mmHg.",
    unit: "mmHg",
  },
  {
    key: "sleep_event",
    label: "Sự kiện giấc ngủ",
    description: "Ngưỡng phát hiện OSA, ngưng thở, tachy ban đêm.",
    unit: "—",
  },
];

export const THRESHOLD_META: Record<string, ThresholdInfo> = {
  hr_critical_low: {
    group: "hr",
    severity: "critical",
    bound: "low",
    label: "Nguy hiểm — thấp",
    hint: "Dưới ngưỡng này coi như nhịp chậm nguy kịch (bradycardia nặng).",
  },
  hr_critical_high: {
    group: "hr",
    severity: "critical",
    bound: "high",
    label: "Nguy hiểm — cao",
    hint: "Trên ngưỡng này coi như nhịp nhanh nguy kịch (tachycardia nặng).",
  },
  hr_warning_low: {
    group: "hr",
    severity: "warning",
    bound: "low",
    label: "Cảnh báo — thấp",
    hint: "Báo trước nhịp chậm cần theo dõi.",
  },
  hr_warning_high: {
    group: "hr",
    severity: "warning",
    bound: "high",
    label: "Cảnh báo — cao",
    hint: "Báo trước nhịp nhanh cần theo dõi.",
  },
  spo2_critical: {
    group: "spo2",
    severity: "critical",
    bound: "low",
    label: "Nguy hiểm",
    hint: "SpO₂ dưới ngưỡng này → giảm oxy nặng, escalate ngay.",
  },
  spo2_warning: {
    group: "spo2",
    severity: "warning",
    bound: "low",
    label: "Cảnh báo",
    hint: "SpO₂ giảm nhẹ — bắt đầu theo dõi sát.",
  },
  rr_critical_low: {
    group: "rr",
    severity: "critical",
    bound: "low",
    label: "Nguy hiểm — thấp",
    hint: "Nhịp thở quá chậm (suy hô hấp / ngưng thở).",
  },
  rr_critical_high: {
    group: "rr",
    severity: "critical",
    bound: "high",
    label: "Nguy hiểm — cao",
    hint: "Thở nhanh nguy kịch (tachypnea).",
  },
  bp_sys_critical: {
    group: "bp",
    severity: "critical",
    bound: "high",
    label: "Tâm thu — nguy hiểm",
    hint: "Huyết áp tâm thu vượt ngưỡng tăng huyết áp cấp cứu.",
  },
  bp_dia_critical: {
    group: "bp",
    severity: "critical",
    bound: "high",
    label: "Tâm trương — nguy hiểm",
    hint: "Huyết áp tâm trương vượt ngưỡng tăng huyết áp cấp cứu.",
  },
  bp_sys_warning: {
    group: "bp",
    severity: "warning",
    bound: "high",
    label: "Tâm thu — cảnh báo",
    hint: "Tâm thu cao — bắt đầu theo dõi.",
  },
  bp_dia_warning: {
    group: "bp",
    severity: "warning",
    bound: "high",
    label: "Tâm trương — cảnh báo",
    hint: "Tâm trương cao — bắt đầu theo dõi.",
  },
  osa_alert_spo2_threshold: {
    group: "sleep_event",
    severity: "warning",
    bound: "low",
    label: "OSA — SpO₂",
    hint: "Mức SpO₂ tối thiểu để gắn cờ ngưng thở khi ngủ (OSA).",
  },
  nocturnal_tachy_hr: {
    group: "sleep_event",
    severity: "warning",
    bound: "high",
    label: "Tachy ban đêm",
    hint: "Nhịp tim cao bất thường khi ngủ — gợi ý nocturnal tachycardia.",
  },
  apnea_rr_threshold: {
    group: "sleep_event",
    severity: "warning",
    bound: "low",
    label: "Ngưng thở — RR",
    hint: "Ngưỡng nhịp thở để xem là ngưng thở/nông trong giấc ngủ.",
  },
};

export function getThresholdInfo(key: string): ThresholdInfo | undefined {
  return THRESHOLD_META[key];
}

export function getGroupMeta(group: ThresholdGroup): ThresholdGroupMeta {
  return THRESHOLD_GROUPS.find((g) => g.key === group) ?? THRESHOLD_GROUPS[0];
}
