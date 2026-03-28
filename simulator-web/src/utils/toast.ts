import { toast } from "sonner";

export const notify = {
  success: (msg: string) => toast.success(msg),
  error: (msg: string) => toast.error(msg),
  warning: (msg: string) => toast.warning(msg),
  info: (msg: string) => toast.info(msg),
  fall: (deviceName: string, variant: string) =>
    toast.error(`🚨 ${deviceName} — Phát hiện té ngã`, {
      description: variantDesc(variant),
      duration: 8000,
    }),
  stress: (deviceName: string) =>
    toast.warning(`⚡ ${deviceName} — Trạng thái căng thẳng kích hoạt`, {
      description: "HR +12bpm, BP +10mmHg",
      duration: 5000,
    }),
  vitalsAlert: (deviceName: string, severity: string) =>
    toast.error(`🩺 ${deviceName} — ${severity === "critical" ? "Sinh hiệu nguy kịch" : "Sinh hiệu cảnh báo"}`, {
      duration: 6000,
    }),
};

export function variantDesc(variant: string): string {
  if (variant === "fall_no_response") return "Bệnh nhân không phản hồi — nguy kịch";
  if (variant === "fall_brief") return "Té ngã nhẹ, theo dõi thêm";
  return "Sự kiện té ngã xác nhận — đếm ngược SOS";
}
