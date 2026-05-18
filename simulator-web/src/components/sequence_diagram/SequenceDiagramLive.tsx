import { useMemo } from "react";
import { useSequenceFlow, FlowEvent } from "../../hooks/useSequenceFlow";
import { MermaidRenderer } from "./MermaidRenderer";

const STEP_ARROW: Record<string, string> = {
  vitals_ingest: "SIM->>BE",
  imu_predict: "SIM->>BE",
  risk_eval: "BE->>AI",
  alert_push: "BE->>FCM",
  sleep_predict: "SIM->>BE",
  fcm_dispatch: "BE->>FCM",
  fall_persist: "BE->>DB",
  db_insert: "BE->>DB",
  websocket_emit: "BE-->>SIM",
  sos_create: "BE->>FCM",
};

const STATUS_ICON: Record<string, string> = {
  done: "OK",
  error: "ERR",
  running: "...",
  pending: "wait",
  skipped: "skip",
};

function buildMermaid(events: FlowEvent[], activeStep: string | null): string {
  const visible = events.filter((e) => STEP_ARROW[e.step]);

  if (visible.length === 0) {
    return [
      "sequenceDiagram",
      "    participant SIM as IoT Sim",
      "    participant BE as Mobile BE",
      "    Note over SIM,BE: Waiting for events...",
    ].join("\n");
  }

  const lines = visible.map((e) => {
    const arrow = STEP_ARROW[e.step] ?? "SIM->>BE";
    const icon = STATUS_ICON[e.status] ?? "";
    const extra = e.payload
      ? Object.entries(e.payload)
          .slice(0, 2)
          .map(([k, v]) => `${k}=${String(v)}`)
          .join(" ")
      : "";
    const label = `${e.step} [${icon}]${extra ? " " + extra : ""}`;
    if (e.step === activeStep) {
      return `    Note right of SIM: active\n    ${arrow}: ${label}`;
    }
    return `    ${arrow}: ${label}`;
  });

  return [
    "sequenceDiagram",
    "    participant SIM as IoT Sim",
    "    participant BE as Mobile BE",
    "    participant FCM as FCM/Push",
    "    participant AI as Model AI",
    "    participant DB as Database",
    ...lines,
  ].join("\n");
}

interface SequenceDiagramLiveProps {
  sessionId: string;
}

/** ADR-024 Phase 7 S15 — live sequence diagram consuming /ws/flow/{sessionId}. */
export function SequenceDiagramLive({ sessionId }: SequenceDiagramLiveProps) {
  const { events, activeStep, connected } = useSequenceFlow(sessionId);

  const mermaidCode = useMemo(
    () => buildMermaid(events, activeStep),
    [events, activeStep]
  );

  return (
    <div
      style={{
        background: "var(--surface-2, #f8f9fa)",
        borderRadius: "8px",
        padding: "16px",
        border: "1px solid var(--border-color, #e0e0e0)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "12px",
        }}
      >
        <span
          style={{
            fontSize: "12px",
            fontWeight: 700,
            color: "var(--text-muted, #888)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Flow Events — Live Sequence
        </span>
        <span
          style={{
            fontSize: "11px",
            padding: "2px 8px",
            borderRadius: "4px",
            background: connected
              ? "rgba(0,180,80,0.12)"
              : "rgba(200,50,50,0.12)",
            color: connected ? "#00b450" : "#c83232",
          }}
        >
          {connected ? "● Connected" : "○ Disconnected"}
        </span>
      </div>

      <MermaidRenderer code={mermaidCode} />

      {events.length > 0 && (
        <div
          style={{
            marginTop: "8px",
            fontSize: "11px",
            color: "var(--text-muted, #888)",
          }}
        >
          {events.length} events — latest:{" "}
          <strong>{events[events.length - 1]?.step}</strong>{" "}
          [{events[events.length - 1]?.status}]
        </div>
      )}
    </div>
  );
}
