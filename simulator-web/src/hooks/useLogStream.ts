import { useEffect, useRef, useState } from "react";

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

export function useLogStream(sessionId: string | null) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const retriesRef = useRef(0);
  const unmountedRef = useRef(false);

  useEffect(() => {
    unmountedRef.current = false;
    if (!sessionId) {
      setConnected(false);
      return;
    }

    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (unmountedRef.current) return;
      const wsBase = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8090";
      ws = new WebSocket(`${wsBase}/ws/logs/${sessionId}`);

      ws.onopen = () => {
        if (unmountedRef.current) return;
        setConnected(true);
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as LogEntry;
          setLogs((prev) => [...prev.slice(-499), payload]);
        } catch {
          // Ignore malformed JSON messages
        }
      };

      ws.onerror = () => {
        if (unmountedRef.current) return;
        setConnected(false);
      };

      ws.onclose = () => {
        if (unmountedRef.current) return;
        setConnected(false);
        if (retriesRef.current < MAX_RETRIES) {
          const delay = Math.min(BASE_DELAY * 2 ** retriesRef.current, MAX_DELAY);
          retriesRef.current += 1;
          retryTimer = setTimeout(connect, delay);
        }
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (ws) ws.close();
    };
  }, [sessionId]);

  return { logs, connected };
}
