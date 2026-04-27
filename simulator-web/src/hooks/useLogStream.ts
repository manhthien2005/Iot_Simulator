import { useEffect, useState } from "react";

export interface LogEntry {
  level: "INFO" | "WARN" | "ERROR";
  session_id: string;
  device_id: string;
  message: string;
  ts: string | null;
}

const MAX_RETRIES = 4;
const BASE_DELAY = 1000;
const MAX_DELAY = 8000;

/** Open one WebSocket per session ID and merge all log streams. */
export function useLogStream(sessionIds: string[]) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const stableKey = [...sessionIds].sort().join(",");

  useEffect(() => {
    if (sessionIds.length === 0) {
      setLogs([]);
      setConnected(false);
      return;
    }

    let connectedCount = 0;
    const controllers: Array<() => void> = [];

    for (const sessionId of sessionIds) {
      let ws: WebSocket | null = null;
      let retries = 0;
      let retryTimer: ReturnType<typeof setTimeout> | null = null;
      let stopped = false;

      function connect() {
        if (stopped) return;
        const wsBase = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8090";
        ws = new WebSocket(`${wsBase}/ws/logs/${sessionId}`);

        ws.onopen = () => {
          if (stopped) return;
          connectedCount++;
          retries = 0;
          setConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data) as LogEntry;
            setLogs((prev) => [...prev.slice(-499), payload]);
          } catch {
            // Ignore malformed JSON
          }
        };

        ws.onerror = () => {
          if (stopped) return;
          connectedCount = Math.max(0, connectedCount - 1);
          setConnected(connectedCount > 0);
        };

        ws.onclose = () => {
          if (stopped) return;
          connectedCount = Math.max(0, connectedCount - 1);
          setConnected(connectedCount > 0);
          if (retries < MAX_RETRIES) {
            const delay = Math.min(BASE_DELAY * 2 ** retries, MAX_DELAY);
            retries++;
            retryTimer = setTimeout(connect, delay);
          }
        };
      }

      connect();

      controllers.push(() => {
        stopped = true;
        if (retryTimer) clearTimeout(retryTimer);
        if (ws) ws.close();
      });
    }

    return () => controllers.forEach((stop) => stop());
    // stableKey captures the sorted session list without causing closure issues
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stableKey]);

  return { logs, connected };
}
