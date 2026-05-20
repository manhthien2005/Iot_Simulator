import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSettings, updateRuntimeConfig } from "../../services/settingsApi";
import type { SimulatorSettingsResponse } from "../../types/settings";

// ---------------------------------------------------------------------------
// DemoModeToggle — ADR-024 Phase 7 S17 + Module H follow-up.
//
// Originally a 2-state toggle (`demo` 1s/1s vs `normal` 5s/5s) writing
// directly to `runtime.json`.  The Settings page now exposes the same
// knobs with finer presets, so when a user picks "Realistic" (5/30) or
// edits values manually, this toggle used to mis-label the live runtime
// as "Normal Mode · Tick 5s" — the label was hard-coded.
//
// Fix: derive a 3rd state `custom` from the live runtime values and
// reflect the *actual* tick in the helper line.  Clicking while in
// `custom` jumps back to `demo` (1s/1s) — the most common need during
// a live presentation, and the same target the toggle already served
// before this fix.
// ---------------------------------------------------------------------------

const DEMO_TICK_S = 1;
const NORMAL_TICK_S = 5;

type ToggleMode = "demo" | "normal" | "custom";

function classifyMode(tick: number, push: number): ToggleMode {
  if (tick === DEMO_TICK_S && push === DEMO_TICK_S) return "demo";
  if (tick === NORMAL_TICK_S && push === NORMAL_TICK_S) return "normal";
  return "custom";
}

interface ModeMeta {
  label: string;
  hint: string;
  accent: string;
  background: string;
  border: string;
  trackOn: boolean;
}

function metaFor(mode: ToggleMode, tick: number): ModeMeta {
  switch (mode) {
    case "demo":
      return {
        label: "Demo Mode",
        hint: `Tick ${DEMO_TICK_S}s — dramatic for demo`,
        accent: "#ffa000",
        background: "rgba(255, 160, 0, 0.10)",
        border: "rgba(255,160,0,0.4)",
        trackOn: true,
      };
    case "normal":
      return {
        label: "Normal Mode",
        hint: `Tick ${NORMAL_TICK_S}s — production realistic`,
        accent: "var(--text-secondary, #555)",
        background: "var(--surface-2, #f5f5f5)",
        border: "var(--border-color, #e0e0e0)",
        trackOn: false,
      };
    case "custom":
      return {
        label: "Tuỳ chỉnh",
        hint: `Tick ${tick}s — đặt trong Cấu hình runtime`,
        accent: "var(--accent-cyan, #06b6d4)",
        background: "var(--accent-cyan-bg, rgba(6,182,212,0.08))",
        border: "var(--accent-cyan-border, rgba(6,182,212,0.30))",
        trackOn: false,
      };
  }
}

export function DemoModeToggle() {
  const queryClient = useQueryClient();

  const { data } = useQuery<SimulatorSettingsResponse>({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: 30_000,
  });

  const tick = data?.runtime.tick_interval_seconds ?? NORMAL_TICK_S;
  const push = data?.runtime.push_interval_seconds ?? NORMAL_TICK_S;
  const mode = classifyMode(tick, push);
  const meta = metaFor(mode, tick);

  const { mutate, isPending } = useMutation({
    mutationFn: updateRuntimeConfig,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  function toggle() {
    // demo → normal, normal → demo, custom → demo (return to canonical preset).
    const nextTick = mode === "demo" ? NORMAL_TICK_S : DEMO_TICK_S;
    mutate({ tick_interval_seconds: nextTick, push_interval_seconds: nextTick });
  }

  const ariaLabel =
    mode === "demo"
      ? "Turn off demo mode"
      : mode === "normal"
        ? "Turn on demo mode"
        : "Switch to demo mode (1s tick)";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "8px 14px",
        background: meta.background,
        border: `1px solid ${meta.border}`,
        borderRadius: "8px",
        userSelect: "none",
      }}
    >
      <button
        onClick={toggle}
        disabled={isPending || !data}
        aria-label={ariaLabel}
        style={{
          width: "40px",
          height: "22px",
          borderRadius: "11px",
          border: "none",
          cursor: isPending ? "wait" : "pointer",
          background: meta.trackOn ? "#ffa000" : "var(--border-color, #ccc)",
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
            left: meta.trackOn ? "21px" : "3px",
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
            color: meta.accent,
          }}
        >
          {meta.label}
        </div>
        <div style={{ fontSize: "11px", color: "var(--text-muted, #888)" }}>
          {meta.hint}
        </div>
      </div>
    </div>
  );
}
