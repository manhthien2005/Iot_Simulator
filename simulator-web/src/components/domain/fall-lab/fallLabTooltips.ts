// ---------------------------------------------------------------------------
// Fall Lab tooltip copy — Module FA Phase 4.
//
// Centralised Vietnamese tooltip text shown via the `<InfoTooltip/>` icon
// across the 5 Fall Lab cards.  Keeping the copy in one file lets us:
//   * Iterate on phrasing without grepping through five components.
//   * Keep each card's JSX scannable — call sites just reference a key.
//   * Localise later by swapping this map for a `useT()` hook.
//
// Each entry intentionally short (1–3 sentences); the tooltip bubble caps
// at 280px so longer copy wraps awkwardly.
// ---------------------------------------------------------------------------

export const FALL_LAB_TOOLTIPS = {
  // -------------------------------------------------------------------------
  // Section A — Scenario matrix column headers + evidence checklist rows.
  // -------------------------------------------------------------------------
  scenarioPeakG:
    "Đỉnh gia tốc tổng |a| (đơn vị g, 1g = 9.8 m/s²) trong cửa sổ 50 mẫu. " +
    "Tham chiếu ngưỡng pre-trigger: 3.0g HARD · 2.5g SOFT.",
  scenarioPostureDeg:
    "Góc thay đổi tư thế (so với trục thẳng đứng) trong cửa sổ. " +
    "Soft-trigger fire khi posture ≥ 45° kèm impact ≥ 2.5g.",
  scenarioPreTrigger:
    "Stage 1 BE: kiểm tra ngưỡng cơ học trước khi gọi AI. " +
    "HARD = chắc chắn impact (peak ≥ 3.0g) · SOFT = nghi ngờ + bằng chứng phụ · NONE = không đủ điều kiện.",
  scenarioInjectEnv:
    "Có inject các tín hiệu môi trường (rung sàn, áp lực) vào window không. " +
    "True chỉ với các kịch bản té ngã thật — false_fall/slip giữ env=0 để AI test true-negative.",
  scenarioAiBand:
    "Band AI kỳ vọng cho variant này. AI rơi vào band khác = sai lệch cần điều tra " +
    "(persona engine sinh sai signal hoặc model drift).",
  scenarioCountdown:
    "Thời gian SOS countdown BE chạy sau khi inject. " +
    "0s = không countdown, 10s/30s = thời gian operator có để bấm 'Tôi ổn'. " +
    "auto = BE tự huỷ khi hết giờ; không huỷ = bypass nút 'Tôi ổn'.",
  scenarioPushAlert:
    "Có gửi webhook alert sang HealthGuard backend (port 8000) không. " +
    "Variant nhẹ không push để giảm noise; variant critical push ngay.",

  // -------------------------------------------------------------------------
  // Section B — AI pipeline 4 stages.
  // -------------------------------------------------------------------------
  pipelineStage1:
    "Stage 1 — Cửa sổ 50 mẫu IMU (accel + gyro × 50Hz = 1 giây dữ liệu). " +
    "Nguồn: parquet dataset replay hoặc synthetic. AI chỉ chạy khi đủ 50 sample.",
  pipelineStage2:
    "Stage 2 — Pre-trigger evaluator chạy server-side trên cửa sổ. " +
    "Kiểm tra hard/soft thresholds rồi quyết định có đẩy lên model API không.",
  pipelineStage3:
    "Stage 3 — POST /api/v1/fall/predict tới healthguard-model-api (port 8001). " +
    "Roundtrip 50–200ms trong giả lập, 1–3s trên mobile thực.",
  pipelineStage4:
    "Stage 4 — BE FSM cập nhật theo verdict + variant policy. " +
    "fall_countdown = đang đếm ngược · fall_resolved = đã hủy/auto-cancel · sos_active = đã leo thang.",
  pipelineReasonCodes:
    "Mã lý do pre-trigger fire. " +
    "IMPACT_PEAK_3G = đỉnh ≥ 3.0g; IMPACT_PLUS_POSTURE_CHANGE = đỉnh 2.5g + góc xoay 45°; " +
    "IMPACT_PLUS_LOW_MOTION = đỉnh 2.5g + bất động ≥ 1s; GYRO_PLUS_POSTURE_CHANGE = quay nhanh + xoay người.",
  pipelineFailureReason:
    "Lý do AI không trả verdict bình thường. " +
    "transport_error = mất kết nối; model_unavailable = model đang load; validation_422 = sai schema; " +
    "insufficient_samples = window <50; device_unbound = thiết bị chưa bind DB.",

  // -------------------------------------------------------------------------
  // Section C — Motion window 50 samples.
  // -------------------------------------------------------------------------
  motionPeak:
    "Đỉnh gia tốc tổng |a| = √(x² + y² + z²) trong toàn bộ window. " +
    "Đỏ = vượt ngưỡng HARD 3.0g (té ngã rõ rệt).",
  motionMean:
    "Gia tốc trung bình toàn window. " +
    "Đứng yên ≈ 1.0g (chỉ trọng lực); vận động ≈ 1.2–1.6g; té ngã ≈ 1.8–2.5g (do post-impact bất động).",
  motionPeakIndex:
    "Vị trí mẫu (0–49) đỉnh xảy ra. " +
    "Dùng làm điểm chia pre-impact/post-impact để tính độ ổn định sau va chạm.",
  motionSampleRate:
    "Tần số lấy mẫu IMU. " +
    "50 Hz = 1 sample mỗi 20ms, đủ để bắt được va chạm (typical fall impact 50–100ms).",
  motionThresholdHard:
    "Đường ngưỡng HARD 3.0g — vượt sẽ trigger pre-trigger HARD bất kể signal khác. " +
    "Tương ứng impact phổ biến trong dataset té ngã thật (3.0–6.0g).",
  motionThresholdSoft:
    "Đường ngưỡng SOFT 2.5g — kết hợp với posture/low-motion mới fire SOFT trigger. " +
    "Bắt được va chạm nhẹ + bằng chứng phụ.",
  motionPreImpact:
    "Mẫu trước peak (chuẩn bị/đang ngã). " +
    "AI dùng mean |a|, peak |a| ở vùng này để phân biệt vận động bình thường vs ngã.",
  motionPostImpact:
    "Mẫu từ peak trở đi (sau va chạm). " +
    "Std |a| thấp = bất động (té ngã thật); std cao = tiếp tục vận động (false alarm).",
  motionGyroMag:
    "|gyro| = √(gx² + gy² + gz²) đơn vị dps (deg/s). " +
    "Té ngã có gyro 200–500 dps khi cơ thể quay; vận động bình thường ≤ 100 dps.",
  motionOrientationPitch:
    "Góc nghiêng theo trục Y (deg). " +
    "Đứng thẳng ≈ 0°, nằm ngửa ≈ 90°. " +
    "Sự thay đổi đột ngột pitch là tín hiệu té ngã chính.",

  // -------------------------------------------------------------------------
  // Section D — Vitals after fall.
  // -------------------------------------------------------------------------
  vitalsHr:
    "Nhịp tim sau té ngã thường tăng do phản ứng giao cảm (sympathetic spike). " +
    "Delta > +20 bpm = warning · > +30 bpm = critical.",
  vitalsSpo2:
    "SpO₂ có thể giảm nếu té úp ngực hoặc chấn thương phổi. " +
    "Delta < -3% = warning · < -5% = critical (cần khám ngay).",
  vitalsBpSys:
    "HA tâm thu thường tăng do stress + đau. " +
    "Delta > +15 mmHg = warning. Tăng đột biến + bradycardia = nghi cushing reflex.",
  vitalsRr:
    "Nhịp thở tăng do hoảng + đau. " +
    "Delta > +5 br/m = warning. RR > 30 br/m kéo dài = nguy hiểm.",
  vitalsBaselinePre:
    "Trung bình cộng trong 30 giây trước thời điểm fall event. " +
    "Là baseline để so sánh với 30s sau fall.",
  vitalsBaselinePost:
    "Trung bình cộng trong 30 giây sau thời điểm fall event. " +
    "Hiệu (post − pre) là delta hiển thị ở chip phía trên.",
  vitalsFallMarker:
    "Vạch đỏ dọc = thời điểm fall_detected event được ghi nhận trên BE. " +
    "Đối chiếu với accelMag spike ở Section C để verify timing.",

  // -------------------------------------------------------------------------
  // Section E — AI verdict + countdown.
  // -------------------------------------------------------------------------
  verdictProbability:
    "Xác suất té ngã do model XGBoost trả về (0–100%). " +
    "Chuyển thành band: < 50% = normal · 50–75% = warning · ≥ 75% = critical.",
  verdictConfidence:
    "Độ tin cậy của model với prediction này. " +
    "Khác với probability — confidence cao + probability thấp = chắc chắn không phải té ngã.",
  verdictBand:
    "Band rủi ro do model trả. Đây là quyết định escalation chính: " +
    "critical = đẩy alert + countdown 30s; warning = soft-alert; normal = bỏ qua.",
  verdictTopFeatures:
    "3 đặc trưng SHAP đóng góp lớn nhất cho verdict. " +
    "Số dương = tăng risk score · số âm = giảm. " +
    "Vd: floor_vibration_mean +0.52 = tiếp xúc sàn đẩy verdict tăng 0.52.",
  verdictRequiresAttention:
    "Flag từ model — true khi probability + confidence vượt ngưỡng nội bộ. " +
    "Hiển thị trên mobile app dưới dạng push notif không yêu cầu phản hồi ngay.",
  verdictHighPriorityAlert:
    "Flag từ model — true khi cần leo thang ngay (gọi caregiver, hiển thị full-screen). " +
    "Override variant policy: kể cả false_fall mà model trả high-priority cũng push alert.",
  countdownRemaining:
    "Thời gian còn lại trước khi BE leo thang sang sos_active. " +
    "Operator/user có thể bấm 'Tôi ổn' để huỷ trong khoảng này.",
  countdownPolicy:
    "Policy do variant quyết định, không phải user. " +
    "auto-resolve = tự huỷ khi hết giờ; không cho huỷ = nút 'Tôi ổn' bị disable (mô phỏng worst case).",
} as const;

export type FallLabTooltipKey = keyof typeof FALL_LAB_TOOLTIPS;
