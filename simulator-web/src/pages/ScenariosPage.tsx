import { useQuery } from "@tanstack/react-query";
import { Clapperboard } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ScenarioCard } from "../components/domain/ScenarioCard";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { Skeleton } from "../components/ui/Skeleton";
import { useDevices } from "../hooks/useDevices";
import { fetchScenarios } from "../services/scenarioApi";
import type { ScenarioOption } from "../types/scenario";

// ---------------------------------------------------------------------------
// ScenariosPage — Module B.5 rebuild.
//
// Each scenario is rendered through `<ScenarioCard/>` so keySignals,
// severity, and follow-up side-effects are visible without opening the
// session runner.  The "active devices" pill mirrors `device.currentScenarioId`
// from `/api/sim/devices`, finally surfacing a piece of state the BE has
// always exposed but the FE used to ignore.
// ---------------------------------------------------------------------------

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

  // Map scenario id → number of devices currently running that scenario.
  // Sourced from `device.currentScenarioId` so we render BE truth, not
  // a FE-side guess.
  const activeDevicesByScenario = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const device of devices) {
      if (!device.currentScenarioId) continue;
      counts[device.currentScenarioId] = (counts[device.currentScenarioId] ?? 0) + 1;
    }
    return counts;
  }, [devices]);

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

  const categoriesToRender: ScenarioOption["category"][] =
    activeCategory === "all" ? ["vitals", "fall", "sleep", "risk"] : [activeCategory];

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
          <p className="page-subtitle">
            Mỗi card hiển thị key signals, mức nghiêm trọng và side-effect mà BE sẽ tự kích hoạt khi áp dụng — không
            cần đoán. Chạy trực tiếp trong Phiên mô phỏng.
          </p>
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
                    // Module H Block 3 — slightly wider min track + uniform
                    // top-alignment so the redesigned compact cards line
                    // up cleanly even when one is expanded.
                    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                    gap: "14px",
                    alignItems: "start",
                  }}
                >
                  {items.map((scenario) => (
                    <ScenarioCard
                      key={scenario.id}
                      scenario={scenario}
                      activeDeviceCount={activeDevicesByScenario[scenario.id] ?? 0}
                      onRun={runScenario}
                    />
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
