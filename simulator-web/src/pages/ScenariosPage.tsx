import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clapperboard } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { Skeleton } from "../components/ui/Skeleton";
import { useDevices } from "../hooks/useDevices";
import { fetchScenarios } from "../services/scenarioApi";
import type { ScenarioOption } from "../types/scenario";

type CategoryFilter = "all" | ScenarioOption["category"];

const categoryTabs: Array<{ id: CategoryFilter; label: string }> = [
  { id: "all", label: "Tất cả" },
  { id: "vitals", label: "Sinh hiệu" },
  { id: "fall", label: "Té ngã" },
  { id: "sleep", label: "Giấc ngủ" },
  { id: "risk", label: "Rủi ro" },
];

const categoryLabel: Record<ScenarioOption["category"], string> = {
  vitals: "Sinh hiệu",
  fall: "Té ngã",
  sleep: "Giấc ngủ",
  risk: "Rủi ro",
};

const categoryColor: Record<ScenarioOption["category"], { bg: string; text: string; border: string }> = {
  vitals: {
    bg: "rgba(6,182,212,0.2)",
    text: "var(--accent-cyan)",
    border: "rgba(6,182,212,0.35)",
  },
  fall: {
    bg: "rgba(239,68,68,0.2)",
    text: "var(--severity-critical)",
    border: "rgba(239,68,68,0.35)",
  },
  sleep: {
    bg: "rgba(139,92,246,0.2)",
    text: "#8B5CF6",
    border: "rgba(139,92,246,0.4)",
  },
  risk: {
    bg: "rgba(245,158,11,0.2)",
    text: "var(--severity-warning)",
    border: "rgba(245,158,11,0.35)",
  },
};

export function ScenariosPage() {
  const navigate = useNavigate();
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const { data: devices = [] } = useDevices();
  const {
    data: scenarios = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["scenarios"],
    queryFn: fetchScenarios,
  });

  useEffect(() => {
    if (!selectedDeviceId && devices.length > 0) {
      setSelectedDeviceId(devices[0].id);
    }
  }, [devices, selectedDeviceId]);

  const filteredScenarios = useMemo(() => {
    if (activeCategory === "all") {
      return scenarios;
    }
    return scenarios.filter((scenario) => scenario.category === activeCategory);
  }, [activeCategory, scenarios]);

  const groupedScenarios = useMemo(() => {
    const groups: Record<ScenarioOption["category"], ScenarioOption[]> = {
      vitals: [],
      fall: [],
      sleep: [],
      risk: [],
    };
    filteredScenarios.forEach((scenario) => {
      groups[scenario.category].push(scenario);
    });
    return groups;
  }, [filteredScenarios]);

  const categoriesToRender: ScenarioOption["category"][] = activeCategory === "all" ? ["vitals", "fall", "sleep", "risk"] : [activeCategory];

  const runScenario = (scenarioId: string) => {
    const query = new URLSearchParams({ scenario: scenarioId });
    if (selectedDeviceId) {
      query.set("device", selectedDeviceId);
    }
    navigate(`/session?${query.toString()}`);
  };

  return (
    <section style={{ display: "grid", gap: "14px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: "12px", flexWrap: "wrap" }}>
        <div>
          <h1 className="page-title">Kịch bản</h1>
          <p className="page-subtitle">Duyệt các kịch bản mô phỏng sẵn sàng chạy và mở trực tiếp trong Phiên mô phỏng.</p>
        </div>
        <label style={{ display: "grid", gap: "6px", minWidth: "260px" }}>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Thiết bị mục tiêu</span>
          <select
            value={selectedDeviceId}
            onChange={(event) => setSelectedDeviceId(event.target.value)}
            style={{
              background: "var(--bg-base)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-md)",
              padding: "8px 10px",
            }}
          >
            {devices.length === 0 ? <option value="">Chưa chọn thiết bị</option> : null}
            {devices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name} ({device.serialNumber})
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
        {categoryTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveCategory(tab.id)}
            aria-label={`Lọc kịch bản theo nhóm: ${tab.label}`}
            style={{
              minHeight: "36px",
              padding: "8px 14px",
              borderRadius: "var(--radius-full)",
              border: activeCategory === tab.id ? "1px solid var(--accent-cyan)" : "1px solid var(--border-default)",
              background: activeCategory === tab.id ? "rgba(6,182,212,0.16)" : "transparent",
              color: activeCategory === tab.id ? "var(--accent-cyan)" : "var(--text-secondary)",
              fontWeight: 600,
              transition:
                "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <Skeleton style={{ height: "180px" }} />
      ) : error ? (
        <ErrorCard message="Không tải được danh sách kịch bản." onRetry={() => refetch()} />
      ) : filteredScenarios.length === 0 ? (
        <EmptyState icon={Clapperboard} title="Không có kịch bản" description="Danh sách kịch bản trống trong nhóm này." />
      ) : (
        <div style={{ display: "grid", gap: "16px" }}>
          {categoriesToRender.map((category) => {
            const items = groupedScenarios[category];
            if (items.length === 0) {
              return null;
            }
            return (
              <div key={category}>
                <h2 style={{ margin: "0 0 10px", fontSize: "15px", color: "var(--text-secondary)", letterSpacing: "0.03em" }}>
                  {categoryLabel[category]}
                </h2>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                    gap: "12px",
                  }}
                >
                  {items.map((scenario) => (
                    <Card key={scenario.id} hoverable>
                      <div style={{ display: "grid", gap: "10px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px" }}>
                          <h3 style={{ margin: 0, fontSize: "17px", lineHeight: 1.3 }}>{scenario.name}</h3>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              whiteSpace: "nowrap",
                              borderRadius: "var(--radius-full)",
                              border: `1px solid ${categoryColor[scenario.category].border}`,
                              background: categoryColor[scenario.category].bg,
                              color: categoryColor[scenario.category].text,
                              padding: "2px 8px",
                              fontSize: "11px",
                              textTransform: "uppercase",
                              letterSpacing: "0.04em",
                            }}
                          >
                            {categoryLabel[scenario.category]}
                          </span>
                        </div>

                        <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.55 }}>{scenario.description}</p>

                        <div
                          style={{
                            border: "1px solid var(--border-default)",
                            borderRadius: "var(--radius-md)",
                            padding: "10px",
                            background: "var(--bg-base)",
                          }}
                        >
                          <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                            Kết quả kỳ vọng
                          </div>
                          <div style={{ marginTop: "6px", fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
                            {scenario.expectedOutcome}
                          </div>
                        </div>

                        <button
                          onClick={() => runScenario(scenario.id)}
                          style={{
                            minHeight: "36px",
                            borderRadius: "var(--radius-md)",
                            border: "1px solid var(--accent-cyan)",
                            background: "rgba(6,182,212,0.12)",
                            color: "var(--accent-cyan)",
                            fontWeight: 600,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: "8px",
                            transition:
                              "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
                          }}
                        >
                          Chạy trong phiên <ArrowRight size={14} />
                        </button>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
