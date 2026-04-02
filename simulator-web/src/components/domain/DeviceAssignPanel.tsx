import type { SimulatedDevice } from "../../types/device";
import type { ScenarioOption } from "../../types/scenario";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

interface DeviceAssignPanelProps {
  devices: SimulatedDevice[];
  scenarios: ScenarioOption[];
  scenarioByDevice: Record<string, string>;
  onScenarioChange: (deviceId: string, scenarioId: string) => void;
}

export function DeviceAssignPanel({ devices, scenarios, scenarioByDevice, onScenarioChange }: DeviceAssignPanelProps) {
  const vitalsScenarios = scenarios.filter((scenario) => scenario.category !== "fall");
  const fallScenarios = scenarios.filter((scenario) => scenario.category === "fall");
  const defaultScenarioId = vitalsScenarios[0]?.id ?? "";

  return (
    <Card header={<strong>Gán kịch bản cho thiết bị</strong>}>
      <div style={{ display: "grid", gap: "8px" }}>
        {devices.map((device) => (
          <div
            key={device.id}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 220px auto",
              gap: "10px",
              alignItems: "center",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
              padding: "10px",
            }}
          >
            <div>
              <strong>{device.name}</strong>
              <p style={{ margin: "4px 0 0", color: "var(--text-secondary)", fontSize: "12px" }}>{device.serialNumber}</p>
            </div>
            {(() => {
              const selectedScenarioId = scenarioByDevice[device.id];
              const safeScenarioId = vitalsScenarios.some((scenario) => scenario.id === selectedScenarioId) ? selectedScenarioId : defaultScenarioId;
              return (
                <select
                  value={safeScenarioId}
                  onChange={(event) => onScenarioChange(device.id, event.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--bg-base)",
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "var(--radius-md)",
                    padding: "8px",
                  }}
                >
                  {vitalsScenarios.map((scenario) => (
                    <option key={scenario.id} value={scenario.id}>
                      {scenario.name}
                    </option>
                  ))}
                </select>
              );
            })()}
            <Badge severity={device.isOnline ? "normal" : "offline"}>{device.isOnline ? "đang truyền" : "ngoại tuyến"}</Badge>
          </div>
        ))}
        {fallScenarios.length > 0 ? (
          <div
            style={{
              marginTop: "6px",
              padding: "6px 10px",
              borderRadius: "var(--radius-sm)",
              background: "rgba(245,158,11,0.08)",
              borderLeft: "3px solid var(--severity-warning)",
              fontSize: "12px",
              color: "var(--text-secondary)",
            }}
          >
            ⚠️ Kịch bản té ngã ({fallScenarios.map((scenario) => scenario.name).join(", ")}) được điều khiển riêng qua <strong>Phòng thí nghiệm té ngã</strong> bên dưới.
          </div>
        ) : null}
      </div>
    </Card>
  );
}
