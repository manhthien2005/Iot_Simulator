import React, { useMemo } from "react";
import type { CSSProperties } from "react";
import { Inbox } from "lucide-react";
import type { AlertEvent, AlertSeverity } from "../../../types/event";

// ---------------------------------------------------------------------------
// LiveFeed — dense, single-column event list for the Cockpit dashboard.
//
// Replaces the legacy `AlertTimeline` table layout with a compact log-style
// row optimised for an operator scanning many events at a glance:
//   * Severity rendered as a tiny color dot, not a full badge — dot color
//     IS the signal; the textual eventType handles disambiguation.
//   * Time is shown as HH:MM:SS in a monospace stripe so the eye can
//     vertically align rows.
//   * The header row carries a single "LIVE" status pulse + a count
//     so the duplicate "Dòng thời gian cảnh báo" card title is gone.
// ---------------------------------------------------------------------------

interface LiveFeedProps {
  events: AlertEvent[];
  /** Hard cap on rendered rows. Defaults to 12 — enough to fill the right
   *  column on a 1080p viewport without scrolling. */
  maxRows?: number;
}

const severityDotColor: Record<AlertSeverity, string> = {
  normal: "var(--severity-normal)",
  warning: "var(--severity-warning)",
  critical: "var(--severity-critical)",
  offline: "var(--severity-offline)",
};

function LiveFeedInner({ events, maxRows = 12 }: LiveFeedProps) {
  const visible = useMemo(() => events.slice(0, maxRows), [events, maxRows]);

  return (
    <section style={containerStyle} aria-label="Dòng sự kiện gần đây">
      <header style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            className="live-dot"
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: events.length > 0 ? "var(--severity-normal)" : "var(--severity-offline)",
            }}
            aria-hidden="true"
          />
          <strong
            style={{
              fontSize: "13px",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              color: "var(--text-primary)",
            }}
          >
            Dòng sự kiện
          </strong>
        </div>
        <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>
          {events.length > 0 ? `${events.length} sự kiện` : "—"}
        </span>
      </header>

      <div style={listStyle}>
        {visible.length === 0 ? (
          <EmptyRow />
        ) : (
          visible.map((event) => <FeedRow key={event.id} event={event} />)
        )}
      </div>
    </section>
  );
}

function FeedRow({ event }: { event: AlertEvent }) {
  const dotColor = severityDotColor[event.severity] ?? "var(--severity-offline)";
  return (
    <div style={rowStyle}>
      <code style={timeStyle}>{formatTime(event.timestamp)}</code>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: dotColor,
          flexShrink: 0,
        }}
        aria-label={event.severity}
      />
      <span style={typeStyle}>{event.eventType}</span>
      <span style={messageStyle}>
        <span style={{ color: "var(--text-secondary)" }}>{event.deviceId}</span>
        <span style={{ color: "var(--text-muted)" }}> · {event.message}</span>
      </span>
    </div>
  );
}

function EmptyRow() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "32px 16px",
        gap: "8px",
        color: "var(--text-muted)",
      }}
    >
      <Inbox size={20} aria-hidden="true" />
      <span style={{ fontSize: "13px" }}>Chưa có sự kiện trong dòng thời gian.</span>
    </div>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  return d.toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export const LiveFeed = React.memo(LiveFeedInner);

// ── Styles ──────────────────────────────────────────────────────────────

const containerStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  background: "var(--bg-elevated)",
  border: "1px solid rgba(255, 255, 255, 0.06)",
  borderRadius: "var(--radius-lg)",
  boxShadow: "var(--shadow-card)",
  overflow: "hidden",
};

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 14px",
  borderBottom: "1px solid var(--border-default)",
  flexShrink: 0,
};

const listStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  maxHeight: "360px",
  overflowY: "auto",
};

const rowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "70px 10px minmax(110px, max-content) 1fr",
  alignItems: "center",
  gap: "10px",
  padding: "8px 14px",
  borderBottom: "1px solid var(--border-default)",
  fontSize: "12.5px",
  lineHeight: 1.4,
};

const timeStyle: CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "11.5px",
  color: "var(--text-muted)",
};

const typeStyle: CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "11.5px",
  fontWeight: 600,
  color: "var(--text-primary)",
  letterSpacing: "0.02em",
  textTransform: "uppercase",
};

const messageStyle: CSSProperties = {
  fontSize: "12.5px",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
