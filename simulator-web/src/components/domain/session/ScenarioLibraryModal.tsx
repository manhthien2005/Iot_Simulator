import { useMemo, useState } from "react";
import { Modal } from "../../ui/Modal";
import { ScenarioCard } from "../ScenarioCard";
import type { ScenarioOption } from "../../../types/scenario";

// ---------------------------------------------------------------------------
// ScenarioLibraryModal — scenario browser embedded inside the Session page.
//
// Replaces the standalone `/scenarios` route.  Operators open this modal
// from the Session runner when they want to see the full catalogue (key
// signals, follow-up side-effects, active device counts) before applying
// a scenario.  The parent decides what "Run" means for the selected
// scenario (apply inline for vitals/sleep/risk, navigate to /fall-lab for
// fall scenarios) — the modal stays presentation-only.
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

interface ScenarioLibraryModalProps {
  open: boolean;
  onClose: () => void;
  scenarios: ScenarioOption[];
  /** Number of devices currently running each scenario, keyed by scenario.id. */
  activeDevicesByScenario: Record<string, number>;
  /** Caller decides what to do with the selected scenario (apply / navigate). */
  onSelect: (scenario: ScenarioOption) => void;
  /** Optional hint shown in the modal subheader, e.g. "Áp dụng cho: Watch-01". */
  targetDeviceLabel?: string;
}

export function ScenarioLibraryModal({
  open,
  onClose,
  scenarios,
  activeDevicesByScenario,
  onSelect,
  targetDeviceLabel,
}: ScenarioLibraryModalProps) {
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");

  const filteredScenarios = useMemo(() => {
    if (activeCategory === "all") return scenarios;
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

  const handleRun = (scenarioId: string) => {
    const scenario = scenarios.find((item) => item.id === scenarioId);
    if (!scenario) return;
    onSelect(scenario);
  };

  return (
    <Modal open={open} onClose={onClose} title="Thư viện kịch bản" maxWidth={1024}>
      {/* Subheader: target device hint */}
      {targetDeviceLabel ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 12px",
            borderRadius: "var(--radius-md)",
            background: "var(--bg-elevated)",
            border: "1px solid rgba(255,255,255,0.06)",
            marginBottom: "12px",
          }}
        >
          <span
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Áp dụng cho
          </span>
          <span style={{ fontSize: "13px", color: "var(--text-primary)", fontWeight: 600 }}>
            {targetDeviceLabel}
          </span>
        </div>
      ) : null}

      {/* Category tabs */}
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "14px" }}>
        {categoryTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveCategory(tab.id)}
            aria-pressed={activeCategory === tab.id}
            aria-label={`Lọc kịch bản theo nhóm: ${tab.label}`}
            style={{
              minHeight: "32px",
              padding: "6px 14px",
              borderRadius: "var(--radius-full)",
              border:
                activeCategory === tab.id
                  ? "1px solid var(--accent-cyan)"
                  : "1px solid rgba(255,255,255,0.08)",
              background:
                activeCategory === tab.id ? "rgba(6,182,212,0.12)" : "var(--bg-elevated)",
              color: activeCategory === tab.id ? "var(--accent-cyan)" : "var(--text-secondary)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
              transition: "background 120ms ease, color 120ms ease, border-color 120ms ease",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Scenario grid, grouped */}
      {filteredScenarios.length === 0 ? (
        <div
          style={{
            padding: "32px 16px",
            textAlign: "center",
            color: "var(--text-muted)",
            fontSize: "13px",
          }}
        >
          Không có kịch bản nào trong nhóm này.
        </div>
      ) : (
        <div style={{ display: "grid", gap: "16px" }}>
          {categoriesToRender.map((category) => {
            const items = groupedScenarios[category];
            if (items.length === 0) return null;
            return (
              <div key={category}>
                <h4
                  style={{
                    margin: "0 0 10px",
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "var(--text-secondary)",
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}
                >
                  {categoryLabel[category]}
                </h4>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                    gap: "12px",
                    alignItems: "start",
                  }}
                >
                  {items.map((scenario) => (
                    <ScenarioCard
                      key={scenario.id}
                      scenario={scenario}
                      activeDeviceCount={activeDevicesByScenario[scenario.id] ?? 0}
                      onRun={handleRun}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}
