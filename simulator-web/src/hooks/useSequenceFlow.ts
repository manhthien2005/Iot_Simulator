import { useEffect, useState } from "react";

export type FlowStatus = "pending" | "running" | "done" | "error" | "skipped";

export interface FlowEvent {
  ts: string;
  session_id: string;
  device_id?: string;
  step: string;
  status: FlowStatus;
  payload?: Record<string, unknown>;
  type?: string;
}

const MAX_RETRIES = 4;
const BASE_DELAY = 1000;
const MAX_DELAY = 8000;
const MAX_EVENTS = 30;
const ACTIVE_CLEAR_MS = 500;

/** ADR-024 Phase 7 S15 — subscribe to /ws/flow/{sessionId} for live flow events. */
export function useSequenceFlow(sessionId: string | null) {
  const [events, setEvents] = useState<FlowEvent[]>([]);
  const [activeStep, setActiveStep] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setEvents([]);
      setConnected(false);
      return;
    }

    let ws: WebSocket | null = null;
    let retries = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let clearTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    function connect() {
      if (stopped) return;
      const wsBase =
        (import.meta.env.VITE_WS_BASE_URL as string | undefined) ??
        "ws://localhost:8090";
      ws = new WebSocket(`${wsBase}/ws/flow/${sessionId}`);

      ws.onopen = () => {
        if (stopped) return;
        retries = 0;
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data as string) as FlowEvent;
          if (payload.type === "keepalive") return;
          setEvents((prev) => [...prev.slice(-(MAX_EVENTS - 1)), payload]);
          setActiveStep(payload.step);
          if (clearTimer) clearTimeout(clearTimer);
          clearTimer = setTimeout(() => setActiveStep(null), ACTIVE_CLEAR_MS);
        } catch {
          // ignore malformed JSON
        }
      };

      ws.onerror = () => {
        if (stopped) return;
        setConnected(false);
      };

      ws.onclose = () => {
        if (stopped) return;
        setConnected(false);
        if (retries < MAX_RETRIES) {
          const delay = Math.min(BASE_DELAY * 2 ** retries, MAX_DELAY);
          retries++;
          retryTimer = setTimeout(connect, delay);
        }
      };
    }

    connect();

    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (clearTimer) clearTimeout(clearTimer);
      ws?.close();
    };
  }, [sessionId]);

  return { events, activeStep, connected };
}
