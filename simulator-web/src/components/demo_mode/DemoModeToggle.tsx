import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSettings, updateRuntimeConfig } from "../../services/settingsApi";
import type { SimulatorSettingsResponse } from "../../types/settings";

const DEMO_TICK_S = 1;
const NORMAL_TICK_S = 5;

/** ADR-024 Phase 7 S17 — toggle between demo (1s tick) and normal (5s tick) mode. */
export function DemoModeToggle() {
  const queryClient = useQueryClient();

  const { data } = useQuery<SimulatorSettingsResponse>({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: 30_000,
  });

  const isDemoMode = (data?.runtime.tick_interval_seconds ?? NORMAL_TICK_S) <= DEMO_TICK_S;

  const { mutate, isPending } = useMutation({
    mutationFn: updateRuntimeConfig,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  function toggle() {
    const next = isDemoMode ? NORMAL_TICK_S : DEMO_TICK_S;
    mutate({ tick_interval_seconds: next, push_interval_seconds: next });
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "8px 14px",
        background: isDemoMode
          ? "rgba(255, 160, 0, 0.10)"
          : "var(--surface-2, #f5f5f5)",
        border: `1px solid ${isDemoMode ? "rgba(255,160,0,0.4)" : "var(--border-color, #e0e0e0)"}`,
        borderRadius: "8px",
        userSelect: "none",
      }}
    >
      <button
        onClick={toggle}
        disabled={isPending || !data}
        aria-label={isDemoMode ? "Turn off demo mode" : "Turn on demo mode"}
        style={{
          width: "40px",
          height: "22px",
          borderRadius: "11px",
          border: "none",
          cursor: isPending ? "wait" : "pointer",
          background: isDemoMode ? "#ffa000" : "var(--border-color, #ccc)",
          position: "relative",
          transition: "background 0.2s",
          flexShrink: 0,
          padding: 0,
        }}
      >
        <span
          style={{
            position: "absolute",
            top: "3px",
            left: isDemoMode ? "21px" : "3px",
            width: "16px",
            height: "16px",
            borderRadius: "50%",
            background: "#fff",
            transition: "left 0.2s",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
          }}
        />
      </button>

      <div>
        <div
          style={{
            fontSize: "12px",
            fontWeight: 700,
            color: isDemoMode ? "#ffa000" : "var(--text-secondary, #555)",
          }}
        >
          {isDemoMode ? "Demo Mode" : "Normal Mode"}
        </div>
        <div style={{ fontSize: "11px", color: "var(--text-muted, #888)" }}>
          Tick {isDemoMode ? DEMO_TICK_S : NORMAL_TICK_S}s
          {isDemoMode ? " — dramatic for demo" : " — production realistic"}
        </div>
      </div>
    </div>
  );
}
