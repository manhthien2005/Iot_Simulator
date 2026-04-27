import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import {
  injectRiskScore,
  triggerRiskCalculation,
} from "../../services/analyticsApi";
import type { RiskLevel, RiskType } from "../../types/analytics";
import { notify } from "../../utils/toast";
import { fieldStyle } from "../../config/defaults";

// ---------------------------------------------------------------------------
// RiskInjectorPanel — operator-side risk tooling extracted from
// RiskAnalyticsTab (Module D.2 / D.5).  Lives in the Diagnostics surface so
// `/analytics` stays read-only for clinical viewers.
//
// The panel exposes two mutations against the backend:
//   1. `triggerRiskCalculation(deviceId)` — forces a fresh on-demand calc.
//   2. `injectRiskScore(...)` — writes a synthetic risk score + XAI explanation
//      into the simulator runtime (and ultimately the DB) to seed scenarios.
//
// Both mutations are written with `useMutation` so `mutation.isPending`
// drives button state directly — no local `useState` flags (plan §8.UX).
// `onMutated` is called after each successful action so the parent can
// invalidate the analytics queries (gauge, history, XAI).
// ---------------------------------------------------------------------------

interface RiskInjectorPanelProps {
  deviceId: string;
  onMutated?: () => void;
}

export function RiskInjectorPanel({ deviceId, onMutated }: RiskInjectorPanelProps) {
  const [riskType, setRiskType] = useState<RiskType>("general");
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("MEDIUM");
  const [injectScore, setInjectScore] = useState<string>("0.72");

  const triggerMutation = useMutation({
    mutationFn: (id: string) => triggerRiskCalculation(id),
    onSuccess: () => {
      notify.success("Đã chạy tính toán rủi ro.");
      onMutated?.();
    },
    onError: () => notify.error("Không thể chạy tính toán rủi ro."),
  });

  const injectMutation = useMutation({
    mutationFn: (payload: {
      device_id: string;
      risk_type: RiskType;
      risk_level: RiskLevel;
      score: number;
    }) => injectRiskScore(payload),
    onSuccess: () => {
      notify.success("Đã tiêm rủi ro và tạo XAI.");
      onMutated?.();
    },
    onError: () => notify.error("Không thể tiêm rủi ro."),
  });

  function handleTrigger() {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi chạy tính toán rủi ro.");
      return;
    }
    triggerMutation.mutate(deviceId);
  }

  function handleInject() {
    if (!deviceId) {
      notify.error("Cần chọn thiết bị trước khi tiêm rủi ro.");
      return;
    }
    const parsed = Number(injectScore);
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
      notify.error("Điểm phải nằm trong khoảng 0.0 đến 1.0.");
      return;
    }
    injectMutation.mutate({
      device_id: deviceId,
      risk_type: riskType,
      risk_level: riskLevel,
      score: parsed,
    });
  }

  const isBusy = triggerMutation.isPending || injectMutation.isPending;

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <strong>Risk Tools</strong>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            (chỉ dành cho operator — sẽ ghi vào DB)
          </span>
        </div>
      }
    >
      <div style={{ display: "grid", gap: "14px" }}>
        <div>
          <h3 style={sectionTitleStyle}>Chạy tính toán theo yêu cầu</h3>
          <p style={hintStyle}>
            Buộc backend tính lại điểm rủi ro cho thiết bị đang chọn rồi đẩy snapshot mới vào Analytics.
          </p>
          <Button
            variant="primary"
            onClick={handleTrigger}
            loading={triggerMutation.isPending}
            disabled={isBusy}
          >
            {triggerMutation.isPending ? "Đang tính toán…" : "Chạy tính toán rủi ro"}
          </Button>
        </div>

        <hr style={dividerStyle} />

        <div>
          <h3 style={sectionTitleStyle}>Tiêm rủi ro nhân tạo (chế độ hỗ trợ)</h3>
          <p style={hintStyle}>
            Ghi đè điểm + tạo giải thích XAI giả lập — chỉ dùng để dựng kịch bản test, sẽ ảnh hưởng tới analytics
            của thiết bị này.
          </p>
          <div style={injectGridStyle}>
            <label style={inputLabelStyle}>
              Loại rủi ro
              <select
                value={riskType}
                onChange={(event) => setRiskType(event.target.value as RiskType)}
                style={fieldStyle}
                disabled={isBusy}
              >
                <option value="general">Tổng quát</option>
                <option value="stroke">Đột quỵ</option>
                <option value="cardiac">Tim mạch</option>
              </select>
            </label>
            <label style={inputLabelStyle}>
              Mức rủi ro
              <select
                value={riskLevel}
                onChange={(event) => setRiskLevel(event.target.value as RiskLevel)}
                style={fieldStyle}
                disabled={isBusy}
              >
                <option value="LOW">Thấp</option>
                <option value="MEDIUM">Trung bình</option>
                <option value="HIGH">Cao</option>
                <option value="CRITICAL">Nguy kịch</option>
              </select>
            </label>
            <label style={inputLabelStyle}>
              Điểm (0.0 – 1.0)
              <input
                value={injectScore}
                onChange={(event) => setInjectScore(event.target.value)}
                style={fieldStyle}
                disabled={isBusy}
                inputMode="decimal"
              />
            </label>
            <Button
              variant="outline"
              onClick={handleInject}
              loading={injectMutation.isPending}
              disabled={isBusy}
            >
              {injectMutation.isPending ? "Đang tiêm…" : "Tiêm + tạo XAI"}
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

const sectionTitleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "13px",
  fontWeight: 600,
  color: "var(--text-primary)",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const hintStyle: React.CSSProperties = {
  margin: "4px 0 10px 0",
  fontSize: "12px",
  color: "var(--text-secondary)",
  lineHeight: 1.5,
};

const injectGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: "10px",
  alignItems: "end",
};

const inputLabelStyle: React.CSSProperties = {
  display: "grid",
  gap: "4px",
  color: "var(--text-secondary)",
  fontSize: "12px",
};

const dividerStyle: React.CSSProperties = {
  border: "none",
  borderTop: "1px solid var(--border-default)",
  margin: 0,
};
