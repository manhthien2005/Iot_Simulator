import type { CSSProperties, ReactNode } from "react";

// ---------------------------------------------------------------------------
// JsonAutoView — render JSON value với heuristic dễ đọc.
//
// Cases:
//   - primitive (string/number/boolean/null) → KeyValueRow
//   - array of primitive → chip list
//   - array of object → table (cột = union keys)
//   - object phẳng (chỉ chứa primitive) → 2-column table
//   - object lồng → recurse, depth tối đa 3 → fallback <pre>
// ---------------------------------------------------------------------------

interface JsonAutoViewProps {
  value: unknown;
  depth?: number;
  maxDepth?: number;
}

export function JsonAutoView({ value, depth = 0, maxDepth = 3 }: JsonAutoViewProps) {
  if (value === null || value === undefined) {
    return <Mono>{value === null ? "null" : "—"}</Mono>;
  }
  if (typeof value !== "object") {
    return <PrimitiveView value={value} />;
  }
  if (Array.isArray(value)) {
    return <ArrayView value={value} depth={depth} maxDepth={maxDepth} />;
  }
  return (
    <ObjectView
      value={value as Record<string, unknown>}
      depth={depth}
      maxDepth={maxDepth}
    />
  );
}

function PrimitiveView({ value }: { value: unknown }) {
  if (typeof value === "boolean") {
    return (
      <span style={{ color: value ? "var(--severity-normal, #22c55e)" : "var(--text-muted)" }}>
        {value ? "true" : "false"}
      </span>
    );
  }
  if (typeof value === "number") {
    return <Mono>{String(value)}</Mono>;
  }
  return <span style={{ color: "var(--text-primary)" }}>{String(value)}</span>;
}

function Mono({ children }: { children: ReactNode }) {
  return (
    <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{children}</span>
  );
}

function ObjectView({
  value,
  depth,
  maxDepth,
}: {
  value: Record<string, unknown>;
  depth: number;
  maxDepth: number;
}) {
  const entries = Object.entries(value);
  if (entries.length === 0) {
    return <span style={{ color: "var(--text-muted)" }}>{"{}"} (rỗng)</span>;
  }
  if (depth >= maxDepth) {
    return <RawJson value={value} />;
  }
  return (
    <table style={tableStyle}>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k} style={{ borderBottom: "1px solid var(--border-subtle, var(--border-default))" }}>
            <td style={{ ...tdStyle, width: "32%", color: "var(--text-secondary)", fontFamily: "var(--font-mono)", verticalAlign: "top" }}>
              {k}
            </td>
            <td style={tdStyle}>
              <JsonAutoView value={v} depth={depth + 1} maxDepth={maxDepth} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RawJson({ value }: { value: unknown }) {
  return (
    <pre style={rawJsonStyle}>{JSON.stringify(value, null, 2)}</pre>
  );
}

function ArrayView({
  value,
  depth,
  maxDepth,
}: {
  value: unknown[];
  depth: number;
  maxDepth: number;
}) {
  if (value.length === 0) {
    return <span style={{ color: "var(--text-muted)" }}>[] (rỗng)</span>;
  }
  const allPrimitive = value.every((v) => v === null || typeof v !== "object");
  if (allPrimitive) {
    return (
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
        {value.map((v, i) => (
          <span key={i} style={chipStyle}>
            {String(v)}
          </span>
        ))}
      </div>
    );
  }
  const allObject = value.every((v) => v !== null && typeof v === "object" && !Array.isArray(v));
  if (allObject && depth < maxDepth) {
    const rows = value as Record<string, unknown>[];
    const keys = Array.from(
      rows.reduce<Set<string>>((acc, row) => {
        for (const k of Object.keys(row)) acc.add(k);
        return acc;
      }, new Set()),
    );
    return (
      <div style={{ overflowX: "auto" }}>
        <table style={tableStyle}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-default)" }}>
              {keys.map((k) => (
                <th key={k} style={thStyle}>
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border-subtle, var(--border-default))" }}>
                {keys.map((k) => (
                  <td key={k} style={tdStyle}>
                    {row[k] === undefined ? (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    ) : (
                      <JsonAutoView value={row[k]} depth={depth + 1} maxDepth={maxDepth} />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return (
    <ol style={listStyle}>
      {value.map((v, i) => (
        <li key={i} style={listItemStyle}>
          <JsonAutoView value={v} depth={depth + 1} maxDepth={maxDepth} />
        </li>
      ))}
    </ol>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "12px",
};

const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  color: "var(--text-secondary)",
  fontWeight: 600,
  fontSize: "11px",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  whiteSpace: "nowrap",
};

const tdStyle: CSSProperties = {
  padding: "6px 8px",
  color: "var(--text-primary)",
  verticalAlign: "top",
};

const chipStyle: CSSProperties = {
  fontSize: "12px",
  fontFamily: "var(--font-mono)",
  padding: "2px 8px",
  borderRadius: "var(--radius-full)",
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
  color: "var(--text-primary)",
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: "18px",
  display: "grid",
  gap: "6px",
};

const listItemStyle: CSSProperties = {
  fontSize: "12px",
  color: "var(--text-primary)",
};

const rawJsonStyle: CSSProperties = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "10px",
  fontSize: "12px",
  fontFamily: "var(--font-mono)",
  margin: 0,
  overflow: "auto",
  maxHeight: "300px",
};
