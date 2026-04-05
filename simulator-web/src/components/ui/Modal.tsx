import { useCallback, useEffect, useRef, type ReactNode } from "react";

interface ModalProps {
  /** Whether the modal is currently visible */
  open: boolean;
  /** Called when the user requests closing (ESC / backdrop click) */
  onClose: () => void;
  /** Modal title shown in the header */
  title?: string;
  /** Content rendered inside the modal panel */
  children: ReactNode;
  /** Footer content (e.g. action buttons) */
  footer?: ReactNode;
  /** Max-width of the modal panel (default 520px) */
  maxWidth?: number | string;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Modal({ open, onClose, title, children, footer, maxWidth = 520 }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Auto-focus first focusable element when modal opens
  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => {
      const el = panelRef.current?.querySelector<HTMLElement>("input, select, textarea");
      el?.focus();
    }, 0);
    return () => clearTimeout(timer);
  }, [open]);

  // ESC close + focus trap
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }

      if (event.key === "Tab" && panelRef.current) {
        const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey) {
          if (document.activeElement === first) {
            event.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, handleKeyDown]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--bg-overlay)",
        zIndex: "var(--z-modal)" as unknown as number,
        display: "grid",
        placeItems: "center",
        padding: "16px",
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="presentation"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? "modal-title" : undefined}
        className="surface-card modal-panel"
        style={{
          width: "100%",
          maxWidth: typeof maxWidth === "number" ? `${maxWidth}px` : maxWidth,
          maxHeight: "calc(100vh - 48px)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        {title && (
          <div
            style={{
              padding: "16px 18px 12px",
              borderBottom: "1px solid var(--border-default)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <h3 id="modal-title" style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
              {title}
            </h3>
            <button
              onClick={onClose}
              aria-label="Đóng"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-muted)",
                fontSize: "18px",
                lineHeight: 1,
                padding: "4px",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Body */}
        <div style={{ padding: "18px", overflowY: "auto", flex: 1 }}>{children}</div>

        {/* Footer */}
        {footer && (
          <div
            style={{
              padding: "12px 18px",
              borderTop: "1px solid var(--border-default)",
              display: "flex",
              justifyContent: "flex-end",
              gap: "8px",
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
