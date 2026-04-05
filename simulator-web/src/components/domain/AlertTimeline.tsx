import React from "react";
import type { AlertEvent } from "../../types/event";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

interface AlertTimelineProps {
  events: AlertEvent[];
}

function AlertTimelineInner({ events }: AlertTimelineProps) {
  return (
    <Card header={<strong>Dòng thời gian cảnh báo</strong>}>
      <div style={{ display: "grid", gap: "8px" }}>
        {events.slice(0, 10).map((event) => (
          <div
            key={event.id}
            style={{
              display: "grid",
              gridTemplateColumns: "120px 140px 1fr",
              gap: "12px",
              alignItems: "center",
              borderBottom: "1px solid var(--border-default)",
              paddingBottom: "8px",
            }}
          >
            <code style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
              {new Date(event.timestamp).toLocaleTimeString()}
            </code>
            <Badge severity={event.severity}>{event.eventType}</Badge>
            <span style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
              {event.deviceId} - {event.message}
            </span>
          </div>
        ))}
        {events.length === 0 ? <span style={{ color: "var(--text-muted)" }}>Chưa có sự kiện trong dòng thời gian.</span> : null}
      </div>
    </Card>
  );
}

export const AlertTimeline = React.memo(AlertTimelineInner);
