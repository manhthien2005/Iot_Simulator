import type { CSSProperties } from "react";
import { AlertOctagon, CloudOff, FileWarning, Hourglass, Link2Off } from "lucide-react";
import type { AIPrediction } from "../../../types/fall";

// ---------------------------------------------------------------------------
// FailureReasonBanner — Module FA, Phase 1.
//
// Maps the structured `AIPrediction.failureReason` enum from
// `api_server/schemas.py` into Vietnamese operator-facing copy.  Lives
// next to the AI verdict block so that when the model API is unreachable
// or rejects the payload, the operator immediately sees *why* — instead
// of a silent "AI offline" badge with no diagnostic detail.
//
// Returns `null` for the success case (`failureReason === "ok"`) so the
// caller can render unconditionally without an extra guard.
// ---------------------------------------------------------------------------

interface Props {
  prediction: AIPrediction | null;
}

interface Mapping {
  title: string;
  detail: string;
  icon: typeof CloudOff;
}

const REASON_MAP: Record<string, Mapping> = {
  transport_error: {
    title: "Mất kết nối tới Model API (port 8001)",
    detail:
      "Simulator không tới được healthguard-model-api — kiểm tra service đang chạy, " +
      "firewall và biến môi trường INTERNAL_SERVICE_SECRET.",
    icon: CloudOff,
  },
  model_unavailable: {
    title: "Model API trả unavailable",
    detail:
      "Model API đang lên (đang load weights) hoặc rơi vào fallback rule-based. " +
      "Verdict hiện tại derive từ pre-trigger, không phải AI thật.",
    icon: AlertOctagon,
  },
  validation_422: {
    title: "Payload sai format (422 Unprocessable Entity)",
    detail:
      "Schema sample không khớp model API — thường do orientation pitch/roll " +
      "không nằm trong khoảng -180..180 hoặc thiếu trường environment.",
    icon: FileWarning,
  },
  insufficient_samples: {
    title: "Cửa sổ chưa đủ 50 mẫu",
    detail:
      "MotionGenerator chưa publish đủ 50 sample cho variant này — chờ tick kế tiếp " +
      "hoặc tăng tần số tick để cửa sổ build nhanh hơn.",
    icon: Hourglass,
  },
  device_unbound: {
    title: "Thiết bị giả lập chưa bound DB device",
    detail:
      "Sim device chưa map vào db_device_id — sang tab Thiết bị bind cho user trước.",
    icon: Link2Off,
  },
};

export function FailureReasonBanner({ prediction }: Props) {
  if (!prediction || prediction.failureReason === "ok") return null;
  const mapping = REASON_MAP[prediction.failureReason];
  if (!mapping) return null;
  const Icon = mapping.icon;
  return (
    <div style={bannerStyle} role="status">
      <Icon size={16} style={{ color: "var(--severity-warning)", flexShrink: 0, marginTop: "2px" }} />
      <div style={{ display: "grid", gap: "2px" }}>
        <strong style={{ fontSize: "12px", color: "var(--text-primary)" }}>{mapping.title}</strong>
        <span style={{ fontSize: "11px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
          {mapping.detail}
        </span>
      </div>
    </div>
  );
}

const bannerStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  alignItems: "flex-start",
  padding: "10px 12px",
  background: "var(--severity-warning-bg)",
  border: "1px solid var(--severity-warning-border)",
  borderRadius: "var(--radius-md)",
};
