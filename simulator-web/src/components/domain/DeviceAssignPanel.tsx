import React from "react";
import type { SimulatedDevice } from "../../types/device";
import type { ScenarioOption } from "../../types/scenario";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

interface DeviceAssignPanelProps {
  devices: SimulatedDevice[];
  scenarios: ScenarioOption[];
  scenarioByDevice: Record<string, string>;
  onScenarioChange: (deviceId: string, scenarioId: string) => void;
  isApplying?: boolean;
}

const SEVERITY_EMOJI: Record<string, string> = {
  normal: "🟢",
  warning: "🟡",
  critical: "🔴",
};

function DeviceAssignPanelInner({ devices, scenarios, scenarioByDevice, onScenarioChange, isApplying = false }: DeviceAssignPanelProps) {
  const vitalsScenarios = scenarios.filter(
    (scenario) => scenario.category === "vitals" || scenario.category === "sleep"
  );
  const defaultScenarioId = vitalsScenarios[0]?.id ?? "";

  return (
    <Card header={<strong>Gán kịch bản cho thiết bị</strong>}>
      <div style={{ display: "grid", gap: "8px" }}>
        {devices.map((device) => {
          const selectedScenarioId = scenarioByDevice[device.id];
          const safeScenarioId = vitalsScenarios.some((scenario) => scenario.id === selectedScenarioId) ? selectedScenarioId : defaultScenarioId;
          const selectedScenario = vitalsScenarios.find((scenario) => scenario.id === safeScenarioId) ?? null;
          return (
            <div
              key={device.id}
              style={{
                display: "grid",
                gridTemplateColumns: "160px 1fr auto",
                gap: "12px",
                alignItems: "center",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-md)",
                padding: "10px",
              }}
            >
              <strong style={{ fontSize: "14px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{device.name}</strong>
              <div style={{ display: "grid", gap: "4px" }}>
                <select
                  value={safeScenarioId}
                  disabled={isApplying}
                  onChange={(event) => onScenarioChange(device.id, event.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--bg-base)",
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "var(--radius-md)",
                    padding: "7px 8px",
                    fontSize: "14px",
                    cursor: "pointer",
                  }}
                >
                  {vitalsScenarios.map((scenario) => (
                    <option key={scenario.id} value={scenario.id}>
                      {SEVERITY_EMOJI[scenario.severity] ?? "🟢"} {scenario.name}
                    </option>
                  ))}
                </select>
                {selectedScenario ? (
                  <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted)", lineHeight: 1.4 }}>
                    {selectedScenario.description}
                  </p>
                ) : null}
              </div>
              <div style={{ alignSelf: "center" }}>
                <Badge severity={device.isOnline ? "normal" : "offline"}>{device.isOnline ? "đang truyền" : "ngoại tuyến"}</Badge>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export const DeviceAssignPanel = React.memo(DeviceAssignPanelInner);
