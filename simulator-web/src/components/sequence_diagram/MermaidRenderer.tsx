import { useEffect, useRef } from "react";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: false, theme: "neutral" });

interface MermaidRendererProps {
  code: string;
}

/** ADR-024 Phase 7 S15 — renders a Mermaid diagram string as inline SVG. */
export function MermaidRenderer({ code }: MermaidRendererProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !code.trim()) return;
    const id = `mermaid-${Date.now()}`;
    mermaid
      .render(id, code)
      .then(({ svg }) => {
        if (ref.current) {
          ref.current.innerHTML = svg;
        }
      })
      .catch(() => {
        // silently ignore render errors (empty diagram, syntax issues)
      });
  }, [code]);

  return <div ref={ref} style={{ minHeight: "80px", overflowX: "auto" }} />;
}
