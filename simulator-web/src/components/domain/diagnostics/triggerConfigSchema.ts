import {
  AlertTriangle,
  Activity,
  Brain,
  Clock,
  Cpu,
  Database,
  FileInput,
  GitBranch,
  Layers,
  ListChecks,
  Settings2,
  ShieldCheck,
  Sliders,
  Target,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";

// ---------------------------------------------------------------------------
// triggerConfigSchema.ts — định nghĩa thứ tự + nhãn tiếng Việt + icon + mô
// tả ngắn cho từng section của `rules_config.json` và
// `fall_pipeline_wrist_config.json`.
//
// TriggerConfigPanel dùng schema này để render structured view (accordion
// theo từng section) thay vì dump JSON thô. Section nào không có trong
// schema sẽ vẫn được render ở cuối với label = key (fallback).
// ---------------------------------------------------------------------------

export interface ConfigSection {
  key: string;
  label: string;
  desc?: string;
  icon?: LucideIcon;
}

export const RULES_SECTIONS: ConfigSection[] = [
  {
    key: "scope",
    label: "Phạm vi & dân số",
    icon: Users,
    desc: "Đối tượng người lớn; context: resting / sleep / post_fall / active.",
  },
  {
    key: "severity",
    label: "Bậc độ nghiêm trọng",
    icon: AlertTriangle,
    desc: "Quy tắc escalation NORMAL → WATCH → SEND_TO_RISK_MODEL → URGENT.",
  },
  {
    key: "inputs",
    label: "Trường dữ liệu đầu vào",
    icon: FileInput,
    desc: "Profile, vitals và context fields mà rule engine cần.",
  },
  {
    key: "derived_metrics",
    label: "Chỉ số dẫn xuất",
    icon: Sliders,
    desc: "Công thức tính BMI, pulse pressure, MAP từ raw vitals.",
  },
  {
    key: "data_quality",
    label: "Chất lượng dữ liệu",
    icon: ShieldCheck,
    desc: "Drop/hold nếu signal_quality < 0.7 hoặc thiếu field bắt buộc.",
  },
  {
    key: "sampling",
    label: "Cửa sổ & lấy mẫu",
    icon: Clock,
    desc: "Khoảng cách tối thiểu giữa các lần đánh giá + cửa sổ baseline.",
  },
  {
    key: "context_policy",
    label: "Chính sách theo ngữ cảnh",
    icon: Layers,
    desc: "Điều chỉnh rule khi user đang resting / sleep / post_fall / active.",
  },
  {
    key: "baseline",
    label: "Baseline cá nhân",
    icon: Database,
    desc: "Cách tính median + MAD cho từng metric, cập nhật từ giấc ngủ và resting.",
  },
  {
    key: "profile",
    label: "Profile (tuổi/BMI)",
    icon: Users,
    desc: "Điều chỉnh độ nhạy cho người ≥65 tuổi hoặc BMI bất thường.",
  },
  {
    key: "instant_rules",
    label: "Rule tức thời",
    icon: AlertTriangle,
    desc: "Ngưỡng đơn giá trị → URGENT/WATCH ngay khi vượt.",
  },
  {
    key: "profile_adjusted_rules",
    label: "Rule điều chỉnh theo profile",
    icon: Sliders,
    desc: "Phiên bản nhạy hơn của instant rules cho nhóm rủi ro cao.",
  },
  {
    key: "time_series_rules",
    label: "Rule chuỗi thời gian",
    icon: Activity,
    desc: "Phát hiện trend kéo dài / drift baseline qua nhiều điểm.",
  },
  {
    key: "combination_rules",
    label: "Rule kết hợp",
    icon: GitBranch,
    desc: "Nhiều metric cùng bất thường → escalate severity.",
  },
  {
    key: "special_policies",
    label: "Chính sách đặc biệt",
    icon: ShieldCheck,
    desc: "Override cho trường hợp đặc thù (sốt, post-fall, ...).",
  },
  {
    key: "decision_engine",
    label: "Engine ra quyết định",
    icon: Brain,
    desc: "Cách tổng hợp severity từ tất cả rule layer.",
  },
  {
    key: "implementation_notes",
    label: "Ghi chú triển khai",
    icon: ListChecks,
    desc: "Hướng dẫn cho dev cài đặt rule engine.",
  },
];

export const FALL_SECTIONS: ConfigSection[] = [
  {
    key: "scope",
    label: "Phạm vi & thiết bị",
    icon: Target,
    desc: "Smartwatch đeo cổ tay; tần số mẫu mặc định 50Hz.",
  },
  {
    key: "input_schema",
    label: "Schema dữ liệu đầu vào",
    icon: FileInput,
    desc: "Cấu trúc IMU stream: accel, gyro, orientation, environment.",
  },
  {
    key: "derived_features",
    label: "Đặc trưng dẫn xuất",
    icon: Sliders,
    desc: "Công thức tính accel_mag, jerk, tilt từ raw IMU.",
  },
  {
    key: "streaming_policy",
    label: "Chính sách streaming",
    icon: Workflow,
    desc: "Cửa sổ phân tích, overlap, sliding window cho stage 1.",
  },
  {
    key: "stage1_pretrigger",
    label: "Stage 1 — Pre-trigger",
    icon: Cpu,
    desc: "Phát hiện sự kiện nghi ngờ té ngã trên thiết bị (low-power).",
  },
  {
    key: "stage2_event_model",
    label: "Stage 2 — Event model",
    icon: Brain,
    desc: "Model phân loại té ngã thật/giả khi stage 1 trigger.",
  },
  {
    key: "post_fall_validation",
    label: "Validation sau té ngã",
    icon: ShieldCheck,
    desc: "Kiểm tra vitals sau khi phát hiện té để xác nhận mức độ.",
  },
  {
    key: "fusion_logic",
    label: "Logic tổng hợp",
    icon: GitBranch,
    desc: "Cách kết hợp output stage 1 + stage 2 + post-fall validation.",
  },
  {
    key: "output_schema",
    label: "Schema kết quả",
    icon: Settings2,
    desc: "Format event được phát ra cho downstream risk model.",
  },
  {
    key: "example_output",
    label: "Ví dụ output",
    icon: ListChecks,
    desc: "Mẫu payload thực tế để so sánh khi debug.",
  },
];

const KNOWN_FIELDS = new Set(["version", "name", "description"]);

export function isMetaField(key: string): boolean {
  return KNOWN_FIELDS.has(key);
}

export function buildOrderedSections(
  json: Record<string, unknown>,
  schema: ConfigSection[],
): ConfigSection[] {
  const known = new Set(schema.map((s) => s.key));
  const ordered: ConfigSection[] = [];
  for (const section of schema) {
    if (Object.prototype.hasOwnProperty.call(json, section.key)) {
      ordered.push(section);
    }
  }
  for (const key of Object.keys(json)) {
    if (KNOWN_FIELDS.has(key) || known.has(key)) continue;
    ordered.push({ key, label: key });
  }
  return ordered;
}
