import type { CSSProperties } from "react";
import { useMemo, useState } from "react";
import { Info } from "lucide-react";
import { Badge } from "../../ui/Badge";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { aiLabelText, fallSeverityRowBg, fallSeverityRowColor } from "../../../utils/severity";
import type { AlertEvent } from "../../../types/event";

// ---------------------------------------------------------------------------
// FallEventsTimelineCard — Module FA Phase 1, Section F.
//
// Replaces the old `<RecentEventsCard/>` with three additions:
//
//   1. Group rows by `metadata.session_id` — operators running multiple
//      sessions back-to-back can compare verdicts within the same run
//      without scrolling past unrelated events.
//   2. Click row → expand snapshot showing AI verdict + variant + sample
//      timestamp (the data we *do* have client-side; vitals delta + motion
//      peak need an additional BE field, deferred to Phase 3).
//   3. Multi-select up to 2 rows → enable "So sánh" button (placeholder
//      for the side-by-side modal landing in a follow-up — disabled UI
//      stub today so the affordance is visible to research operators).
// ---------------------------------------------------------------------------

interface Props {
  events: AlertEvent[];
}

export function FallEventsTimelineCard({ events }: Props) {
  const fallEvents = useMemo(
    () => events.filter((e) => e.eventType === "fall_detected" || e.eventType === "sos_cancel"),
    [events],
  );

  // Group by session_id (falls back to "no-session" bucket for legacy events
  // that pre-date the session-id metadata field).
  const grouped = useMemo(() => groupBySession(fallEvents), [fallEvents]);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      // Cap at 2 — drop the oldest selection.
      const next = [...prev, id];
      return next.slice(-2);
    });
  };

  return (
    <Card
      header={
        <div style={cardHeadStyle}>
          <strong style={{ fontSize: "13px" }}>
            Sự kiện gần đây ({fallEvents.length}) · checkbox 2 events để so sánh
          </strong>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            BE-recorded · không invent
          </span>
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
          <div style={{ display: "grid", gap: "10px" }}>
            <CompareBar
              selectedCount={selectedIds.length}
              onClear={() => setSelectedIds([])}
            />
            {grouped.map((group) => (
              <SessionGroup
                key={group.sessionId}
                group={group}
                expandedId={expandedId}
                selectedIds={selectedIds}
                onExpand={setExpandedId}
                onToggleSelect={toggleSelect}
              />
            ))}
          </div>
        )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Compare bar — placeholder until the modal lands.  Visible affordance only.
// ---------------------------------------------------------------------------

function CompareBar({ selectedCount, onClear }: { selectedCount: number; onClear: () => void }) {
  const enabled = selectedCount === 2;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "10px",
        padding: "8px 12px",
        borderRadius: "var(--radius-md)",
        background: enabled ? "var(--accent-cyan-bg)" : "var(--bg-base)",
        border: `1px solid ${enabled ? "var(--accent-cyan-border)" : "var(--border-default)"}`,
      }}
    >
      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
        <strong style={{ color: enabled ? "var(--accent-cyan)" : "var(--text-secondary)" }}>
          {selectedCount} / 2 events đã chọn
        </strong>
        {selectedCount > 0 && (
          <button
            type="button"
            onClick={onClear}
            style={{ marginLeft: "8px", border: "none", background: "transparent", color: "var(--text-muted)", cursor: "pointer", fontSize: "11px", textDecoration: "underline" }}
          >
            bỏ chọn
          </button>
        )}
      </span>
      <button
        type="button"
        disabled={!enabled}
        style={{
          padding: "4px 10px",
          borderRadius: "var(--radius-md)",
          border: `1px solid ${enabled ? "var(--accent-cyan)" : "var(--border-default)"}`,
          background: enabled ? "var(--accent-cyan)" : "var(--bg-elevated)",
          color: enabled ? "#001019" : "var(--text-muted)",
          fontSize: "12px",
          fontWeight: 500,
          cursor: enabled ? "pointer" : "not-allowed",
        }}
      >
        So sánh 2 events →
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Session group — header + rows
// ---------------------------------------------------------------------------

interface Group {
  sessionId: string;
  events: AlertEvent[];
  startedAt: string;
  endedAt: string;
}

function groupBySession(events: AlertEvent[]): Group[] {
  // Sort newest first to keep the recent session at the top.
  const sorted = [...events].sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
  const map = new Map<string, AlertEvent[]>();
  for (const event of sorted) {
    const key = event.metadata.session_id || "no-session";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(event);
  }
  return Array.from(map.entries()).map(([sessionId, evts]) => {
    const sortedAsc = [...evts].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
    return {
      sessionId,
      events: evts, // newest first
      startedAt: sortedAsc[0]?.timestamp ?? "",
      endedAt: sortedAsc[sortedAsc.length - 1]?.timestamp ?? "",
    };
  });
}

function SessionGroup({
  group, expandedId, selectedIds, onExpand, onToggleSelect,
}: {
  group: Group;
  expandedId: string | null;
  selectedIds: string[];
  onExpand: (id: string | null) => void;
  onToggleSelect: (id: string) => void;
}) {
  return (
    <div style={groupStyle}>
      <div style={groupHeadStyle}>
        <strong style={{ fontSize: "12px", color: "var(--text-primary)" }}>
          {group.sessionId === "no-session" ? "(không có session id)" : `Session ${group.sessionId}`}
        </strong>
        <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          {formatTime(group.startedAt)} → {formatTime(group.endedAt)} · {group.events.length} events
        </span>
      </div>
      {group.events.map((event) => (
        <FallEventRow
          key={event.id}
          event={event}
          expanded={expandedId === event.id}
          selected={selectedIds.includes(event.id)}
          onExpand={() => onExpand(expandedId === event.id ? null : event.id)}
          onToggleSelect={() => onToggleSelect(event.id)}
        />
      ))}
    </div>
  );
}

function FallEventRow({
  event, expanded, selected, onExpand, onToggleSelect,
}: {
  event: AlertEvent;
  expanded: boolean;
  selected: boolean;
  onExpand: () => void;
  onToggleSelect: () => void;
}) {
  const variant = event.metadata.variant || null;
  const aiLabel = event.metadata.ai_label ?? null;
  const aiBand = event.metadata.ai_band ?? null;
  const aiProbability = event.metadata.ai_probability;
  const aiStatus = event.metadata.ai_status ?? null;

  return (
    <>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "22px 90px 130px 1fr auto",
          gap: "10px",
          alignItems: "center",
          padding: "8px 12px",
          background: selected ? "var(--accent-cyan-bg)" : fallSeverityRowBg(event.severity),
          borderLeft: `3px solid ${selected ? "var(--accent-cyan)" : fallSeverityRowColor(event.severity)}`,
          borderBottom: "1px solid var(--border-default)",
          cursor: "pointer",
          fontSize: "12px",
        }}
        onClick={onExpand}
      >
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggleSelect}
          onClick={(e) => e.stopPropagation()}
          aria-label="Select event for compare"
          style={{ accentColor: "var(--accent-cyan)", cursor: "pointer" }}
        />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-muted)" }}>
          {formatTime(event.timestamp)}
        </span>
        <span style={{ fontWeight: 600, color: event.eventType === "fall_detected" ? "var(--severity-critical)" : "var(--severity-normal)" }}>
          {event.eventType === "fall_detected" ? "▲ Fall detected" : "● SOS cancelled"}
        </span>
        <span style={{ color: "var(--text-secondary)" }}>
          {variant ? <code>{variant}</code> : event.message}
        </span>
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", justifyContent: "flex-end" }}>
          {aiLabel && (
            <Badge severity={aiBand === "critical" ? "critical" : aiBand === "warning" ? "warning" : "normal"}>
              AI: {aiLabelText(aiLabel)}
              {aiProbability ? ` · ${Math.round(parseFloat(aiProbability) * 100)}%` : ""}
            </Badge>
          )}
          {aiStatus && aiStatus !== "ok" && <Badge severity="offline">{aiStatus}</Badge>}
        </div>
      </div>
      {expanded && <ExpandedSnapshot event={event} />}
    </>
  );
}

function ExpandedSnapshot({ event }: { event: AlertEvent }) {
  const aiLabel = event.metadata.ai_label;
  const aiProbability = event.metadata.ai_probability;
  const aiConfidence = event.metadata.ai_confidence;
  const fallEventId = event.metadata.fall_event_id;
  const modelRequestId = event.metadata.model_request_id;
  const variant = event.metadata.variant;

  return (
    <div style={expandedStyle}>
      <div>
        <h5 style={paneTitleStyle}>AI verdict snapshot</h5>
        <KvRow label="Label" value={aiLabel ?? "—"} />
        <KvRow label="Probability" value={aiProbability ? `${Math.round(parseFloat(aiProbability) * 100)}%` : "—"} />
        <KvRow label="Confidence" value={aiConfidence ? `${Math.round(parseFloat(aiConfidence) * 100)}%` : "—"} />
      </div>
      <div>
        <h5 style={paneTitleStyle}>Inject metadata</h5>
        <KvRow label="Variant" value={variant ?? "—"} />
        <KvRow label="Severity" value={event.severity} />
        <KvRow label="Source" value={event.metadata.source ?? "—"} />
      </div>
      <div>
        <h5 style={paneTitleStyle}>BE persistence</h5>
        <KvRow label="Fall event id" value={fallEventId ?? "—"} />
        <KvRow label="Model request id" value={modelRequestId ?? "—"} />
        <KvRow label="Event id" value={event.id} />
      </div>
    </div>
  );
}

function KvRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", padding: "2px 0", fontSize: "11px", color: "var(--text-secondary)" }}>
      <span>{label}</span>
      <code style={{ color: "var(--text-primary)", fontSize: "10.5px" }}>{value}</code>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("vi-VN", { hour12: false });
  } catch {
    return "—";
  }
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const cardHeadStyle: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap",
};

const groupStyle: CSSProperties = {
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  overflow: "hidden",
};

const groupHeadStyle: CSSProperties = {
  padding: "8px 12px",
  background: "var(--bg-base)",
  borderBottom: "1px solid var(--border-default)",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "10px",
};

const expandedStyle: CSSProperties = {
  padding: "12px 14px",
  background: "var(--bg-base)",
  borderBottom: "1px solid var(--border-default)",
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: "12px",
};

const paneTitleStyle: CSSProperties = {
  margin: "0 0 4px",
  fontSize: "10.5px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "var(--text-muted)",
};
