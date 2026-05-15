import { useMemo } from "react";
import { Info } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { aiLabelText, fallSeverityRowBg, fallSeverityRowColor } from "../../../utils/severity";
import type { AlertEvent } from "../../../types/event";

interface Props {
  events: AlertEvent[];
}

export function RecentEventsCard({ events }: Props) {
  const fallEvents = useMemo(
    () => events.filter((e) => e.eventType === "fall_detected" || e.eventType === "sos_cancel"),
    [events],
  );

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <strong>Sự kiện gần đây ({fallEvents.length})</strong>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>BE-recorded · không invent</span>
        </div>
      }
    >
      {fallEvents.length === 0
        ? (
          <EmptyState
            icon={Info}
            title="Chưa có sự kiện té ngã"
            description="Các fall_detected / sos_cancel cho thiết bị này sẽ xuất hiện ở đây."
          />
        )
        : (
          <div style={{ display: "grid", gap: "6px" }}>
            {fallEvents.map((event) => (
              <FallEventRow key={event.id} event={event} />
            ))}
          </div>
        )}
    </Card>
  );
}

function FallEventRow({ event }: { event: AlertEvent }) {
  const variant = event.metadata.variant || null;
  const aiLabel = event.metadata.ai_label ?? null;
  const aiBand = event.metadata.ai_band ?? null;
  const aiProbability = event.metadata.ai_probability;
  const aiStatus = event.metadata.ai_status ?? null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "100px 130px 1fr auto",
        gap: "8px",
        alignItems: "center",
        padding: "6px 10px",
        borderRadius: "var(--radius-sm)",
        background: fallSeverityRowBg(event.severity),
        borderLeft: `3px solid ${fallSeverityRowColor(event.severity)}`,
      }}
    >
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-muted)" }}>
        {new Date(event.timestamp).toLocaleTimeString("vi-VN", { hour12: false })}
      </span>
      <span style={{ fontSize: "12px" }}>
        {event.eventType === "fall_detected" ? "🔴 Fall detected" : "🟢 SOS cancelled"}
      </span>
      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
        {variant ? <code>{variant}</code> : event.message}
      </span>
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", justifyContent: "flex-end" }}>
        {aiLabel
          ? (
            <Badge
              severity={aiBand === "critical" ? "critical" : aiBand === "warning" ? "warning" : "normal"}
            >
              AI: {aiLabelText(aiLabel)}
              {aiProbability ? ` · ${Math.round(parseFloat(aiProbability) * 100)}%` : ""}
            </Badge>
          )
          : null}
        {aiStatus && aiStatus !== "ok"
          ? <Badge severity="offline">{aiStatus}</Badge>
          : null}
      </div>
    </div>
  );
}
