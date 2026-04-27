import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

// ---------------------------------------------------------------------------
// Tooltip — Module G.15.
//
// Portal-based, position-aware tooltip for severity rationale, truncated
// cells, icon-only buttons, etc.  No external dependency — pure CSS +
// `getBoundingClientRect`.
//
// Design choices:
//   * Renders in a `document.body` portal so `overflow: hidden` parents
//     (cards, sidebars) don't clip the bubble.
//   * Auto-flips placement when the bubble would overflow the viewport.
//     Default: `top`.  Falls back to `bottom`, `right`, `left` in that
//     order until one fits.
//   * Triggers on `mouseenter` / `focusin` (keyboard parity), dismisses
//     on `mouseleave` / `blur` / `Escape`.
//   * `delayMs` (default 250) prevents flickering on quick mouse-overs.
//   * Wires `aria-describedby` on the trigger so screen readers
//     announce the tooltip.
// ---------------------------------------------------------------------------

type Placement = "top" | "bottom" | "left" | "right";

interface TooltipProps {
  /** Single React element that becomes the trigger. */
  children: ReactElement;
  /** Tooltip body — string or any node. */
  content: ReactNode;
  /** Preferred placement; auto-flips if the viewport doesn't fit. */
  placement?: Placement;
  /** ms to wait before showing (default 250). */
  delayMs?: number;
  /** Disable tooltip entirely (e.g. while a parent is loading). */
  disabled?: boolean;
}

const PLACEMENT_FALLBACKS: Record<Placement, Placement[]> = {
  top: ["top", "bottom", "right", "left"],
  bottom: ["bottom", "top", "right", "left"],
  left: ["left", "right", "top", "bottom"],
  right: ["right", "left", "top", "bottom"],
};

const VIEWPORT_MARGIN = 6;
const TOOLTIP_OFFSET = 8;

export function Tooltip({
  children,
  content,
  placement = "top",
  delayMs = 250,
  disabled = false,
}: TooltipProps) {
  const triggerRef = useRef<HTMLElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const showTimerRef = useRef<number | null>(null);

  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number; placement: Placement }>({
    top: 0,
    left: 0,
    placement,
  });

  const tooltipId = useId();

  const clearShowTimer = () => {
    if (showTimerRef.current != null) {
      window.clearTimeout(showTimerRef.current);
      showTimerRef.current = null;
    }
  };

  const requestShow = useCallback(() => {
    if (disabled) return;
    clearShowTimer();
    showTimerRef.current = window.setTimeout(() => {
      setOpen(true);
    }, delayMs);
  }, [delayMs, disabled]);

  const dismiss = useCallback(() => {
    clearShowTimer();
    setOpen(false);
  }, []);

  // Recompute coords whenever the tooltip becomes visible or content
  // changes — the bubble may have a different width after the first
  // measurement so we re-flip if needed.
  useLayoutEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    const bubble = tooltipRef.current;
    if (!trigger || !bubble) return;

    const triggerRect = trigger.getBoundingClientRect();
    const bubbleRect = bubble.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    function computeFor(p: Placement) {
      let top = 0;
      let left = 0;
      switch (p) {
        case "top":
          top = triggerRect.top - bubbleRect.height - TOOLTIP_OFFSET;
          left = triggerRect.left + triggerRect.width / 2 - bubbleRect.width / 2;
          break;
        case "bottom":
          top = triggerRect.bottom + TOOLTIP_OFFSET;
          left = triggerRect.left + triggerRect.width / 2 - bubbleRect.width / 2;
          break;
        case "left":
          top = triggerRect.top + triggerRect.height / 2 - bubbleRect.height / 2;
          left = triggerRect.left - bubbleRect.width - TOOLTIP_OFFSET;
          break;
        case "right":
          top = triggerRect.top + triggerRect.height / 2 - bubbleRect.height / 2;
          left = triggerRect.right + TOOLTIP_OFFSET;
          break;
      }
      const fits =
        top >= VIEWPORT_MARGIN &&
        left >= VIEWPORT_MARGIN &&
        top + bubbleRect.height <= vh - VIEWPORT_MARGIN &&
        left + bubbleRect.width <= vw - VIEWPORT_MARGIN;
      return { top, left, fits };
    }

    let chosen: { top: number; left: number; placement: Placement } | null = null;
    for (const candidate of PLACEMENT_FALLBACKS[placement]) {
      const result = computeFor(candidate);
      if (result.fits) {
        chosen = { top: result.top, left: result.left, placement: candidate };
        break;
      }
    }

    if (!chosen) {
      // Nothing fits — clamp the preferred placement into the viewport.
      const fallback = computeFor(placement);
      chosen = {
        top: clamp(fallback.top, VIEWPORT_MARGIN, vh - bubbleRect.height - VIEWPORT_MARGIN),
        left: clamp(fallback.left, VIEWPORT_MARGIN, vw - bubbleRect.width - VIEWPORT_MARGIN),
        placement,
      };
    }

    setCoords(chosen);
  }, [open, content, placement]);

  // Global ESC dismiss for keyboard users.
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, dismiss]);

  // Cleanup pending timer on unmount.
  useEffect(() => () => clearShowTimer(), []);

  if (!isValidElement(children)) {
    return children;
  }

  type TriggerProps = {
    ref?: (node: HTMLElement | null) => void;
    onMouseEnter?: (event: unknown) => void;
    onMouseLeave?: (event: unknown) => void;
    onFocus?: (event: unknown) => void;
    onBlur?: (event: unknown) => void;
    "aria-describedby"?: string;
  };
  const childProps = (children.props ?? {}) as TriggerProps;

  const enhanced = cloneElement(children as ReactElement<TriggerProps>, {
    ref: (node: HTMLElement | null) => {
      triggerRef.current = node;
      // Forward ref to the original child if it had one.  React 18
      // children may carry a ref via `children.ref` — we don't try to
      // chain it here because the simulator codebase doesn't pass refs
      // through `<Tooltip/>` triggers.
    },
    onMouseEnter: (event: unknown) => {
      childProps.onMouseEnter?.(event);
      requestShow();
    },
    onMouseLeave: (event: unknown) => {
      childProps.onMouseLeave?.(event);
      dismiss();
    },
    onFocus: (event: unknown) => {
      childProps.onFocus?.(event);
      requestShow();
    },
    onBlur: (event: unknown) => {
      childProps.onBlur?.(event);
      dismiss();
    },
    "aria-describedby": open ? tooltipId : childProps["aria-describedby"],
  });

  return (
    <>
      {enhanced}
      {open
        ? createPortal(
            <div
              ref={tooltipRef}
              id={tooltipId}
              role="tooltip"
              style={{
                position: "fixed",
                top: `${coords.top}px`,
                left: `${coords.left}px`,
                zIndex: "var(--z-toast)" as unknown as number,
                background: "var(--bg-elevated)",
                color: "var(--text-primary)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-sm)",
                padding: "6px 10px",
                fontSize: "12px",
                lineHeight: 1.45,
                maxWidth: "280px",
                boxShadow: "0 6px 20px rgba(0,0,0,0.35)",
                pointerEvents: "none",
              }}
            >
              {content}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}
