import { useEffect, useState } from "react";

export interface LogEntry {
  level: "INFO" | "WARN" | "ERROR";
  session_id: string;
  device_id: string;
  message: string;
  ts: string | null;
}

export function useLogStream(sessionId: string | null) {
  const [logs, setLogs] = useState<LogEntry[]>([]);

  useEffect(() => {
    if (!sessionId) return;
    const wsBase = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8090";
    const ws = new WebSocket(`${wsBase}/ws/logs/${sessionId}`);
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data) as LogEntry;
      setLogs((prev) => [...prev.slice(-499), payload]);
    };
    return () => ws.close();
  }, [sessionId]);

  return logs;
}

