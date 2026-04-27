import type { CSSProperties } from "react";
import { AlertTriangle, Check, Clock, MinusCircle } from "lucide-react";
import type { PipelineStage, PipelineStageStatus } from "../../types/verification";

// ---------------------------------------------------------------------------
// PipelineStageStrip — Module E.4.
//
// Horizontal strip that renders the device → publish → downstream evidence
// trail returned by `GET /api/sim/verification/latest`.  Each stage is one of
// `ok` / `pending` / `failed` / `skipped` so an operator can see exactly
// where the trail broke.
//
// Pure presentational — the parent owns fetching.  The component handles
// overflow gracefully on small screens by switching to vertical orientation.
// ---------------------------------------------------------------------------

interface PipelineStageStripProps {
  stages: PipelineStage[];
  /** Display orientation — defaults to horizontal; vertical shrinks for cards;
   *  grid renders 3 columns (no connectors) to avoid horizontal overflow. */
  orientation?: "horizontal" | "vertical" | "grid";
}

export function PipelineStageStrip({
  stages,
  orientation = "horizontal",
}: PipelineStageStripProps) {
  if (stages.length === 0) {
    return (
      <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0 }}>
        Chưa có dữ liệu pipeline — bắt đầu một phiên để thu thập bằng chứng.
      </p>
    );
  }

  if (orientation === "grid") {
    return (
      <ol
        role="list"
        aria-label="Tiến trình pipeline xác minh"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "6px",
          margin: 0,
          padding: 0,
          listStyle: "none",
        }}
      >
        {stages.map((stage) => (
          <li key={stage.key}>
            <StageNode stage={stage} />
          </li>
        ))}
      </ol>
    );
  }

  const isHorizontal = orientation === "horizontal";

  return (
    <ol
      role="list"
      aria-label="Tiến trình pipeline xác minh"
      style={{
        display: "flex",
        flexDirection: isHorizontal ? "row" : "column",
        flexWrap: isHorizontal ? "wrap" : "nowrap",
        gap: isHorizontal ? "0" : "8px",
        margin: 0,
        padding: 0,
        listStyle: "none",
      }}
    >
      {stages.map((stage, index) => {
        const isLast = index === stages.length - 1;
        return (
          <li
            key={stage.key}
            style={{
              display: "flex",
              alignItems: isHorizontal ? "center" : "flex-start",
              flex: isHorizontal ? "1 1 160px" : "0 0 auto",
              minWidth: isHorizontal ? "160px" : undefined,
            }}
          >
            <StageNode stage={stage} />
            {!isLast && isHorizontal && <Connector status={stage.status} />}
          </li>
        );
      })}
    </ol>
  );
}

// ── Stage node ───────────────────────────────────────────────────────────

function StageNode({ stage }: { stage: PipelineStage }) {
  const tone = STATUS_TONES[stage.status];
  return (
    <div
      title={stage.detail ?? undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "6px 10px",
        borderRadius: "var(--radius-md)",
        background: tone.bg,
        border: `1px solid ${tone.border}`,
        flex: 1,
      }}
    >
      <StageIcon status={stage.status} fg={tone.fg} />
      <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
        <strong
          style={{
            fontSize: "12px",
            color: tone.fg,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {stage.label}
        </strong>
        {stage.detail && (
          <span
            style={{
              fontSize: "11px",
              color: "var(--text-secondary)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              maxWidth: "240px",
            }}
          >
            {stage.detail}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Status icon (severity-driven) ────────────────────────────────────────

function StageIcon({ status, fg }: { status: PipelineStageStatus; fg: string }) {
  const props = { size: 14, color: fg, "aria-hidden": true } as const;
  switch (status) {
    case "ok":
      return <Check {...props} />;
    case "failed":
      return <AlertTriangle {...props} />;
    case "skipped":
      return <MinusCircle {...props} />;
    case "pending":
    default:
      return <Clock {...props} />;
  }
}

// ── Connector between adjacent stages ────────────────────────────────────

function Connector({ status }: { status: PipelineStageStatus }) {
  const tone = STATUS_TONES[status];
  return (
    <span
      aria-hidden
      style={{
        flex: "0 0 auto",
        width: "16px",
        height: "2px",
        background: tone.border,
        margin: "0 4px",
      }}
    />
  );
}

// ── Tones ────────────────────────────────────────────────────────────────

interface Tone {
  fg: string;
  bg: string;
  border: string;
}

const STATUS_TONES: Record<PipelineStageStatus, Tone> = {
  ok: {
    fg: "var(--severity-normal)",
    bg: "rgba(34,197,94,0.10)",
    border: "rgba(34,197,94,0.35)",
  },
  pending: {
    fg: "var(--text-secondary)",
    bg: "var(--bg-elevated)",
    border: "var(--border-default)",
  },
  failed: {
    fg: "var(--severity-critical)",
    bg: "rgba(239,68,68,0.10)",
    border: "rgba(239,68,68,0.45)",
  },
  skipped: {
    fg: "var(--text-muted)",
    bg: "transparent",
    border: "var(--border-default)",
  },
};

// Re-export for callers that want to render an inline severity dot without
// the full strip (e.g. table rows summarising a single stage).
export function PipelineStatusDot({ status }: { status: PipelineStageStatus }) {
  const tone = STATUS_TONES[status];
  const baseStyle: CSSProperties = {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: tone.fg,
    display: "inline-block",
  };
  return <span aria-hidden style={baseStyle} />;
}
