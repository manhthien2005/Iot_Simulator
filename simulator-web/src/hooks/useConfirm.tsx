import { useCallback, useRef, useState } from "react";
import { AlertTriangle, ShieldAlert } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/Button";

// ---------------------------------------------------------------------------
// useConfirm — Module G.2.
//
// Async-await ergonomics for "are you sure?" prompts.  Returns a tuple of
// `[confirm, dialog]` — the caller renders `{dialog}` once anywhere in
// the tree (it's a portal-friendly `<Modal/>`) and calls `confirm({...})`
// from any handler.  `confirm` resolves to `true` if the operator
// confirms, `false` if they cancel / ESC / click the backdrop.
//
// This is hook-local rather than a global provider so adopting modules
// don't have to touch `App.tsx` — the modal mounts wherever the hook
// lives and is `position: fixed` so it floats above the page anyway.
//
// Typical usage:
//
//   const [confirm, confirmDialog] = useConfirm();
//
//   async function onClick() {
//     const ok = await confirm({
//       severity: "critical",
//       title: "Xác nhận té ngã?",
//       description: "Sự kiện này kích hoạt SOS countdown 30 s.",
//       confirmLabel: "Gửi té ngã",
//     });
//     if (!ok) return;
//     await doDangerousThing();
//   }
//
//   return <>...JSX... {confirmDialog}</>;
// ---------------------------------------------------------------------------

export type ConfirmSeverity = "info" | "warning" | "critical";

export interface ConfirmOptions {
  /** Modal title — usually a question. */
  title: string;
  /** Long-form explanation of what the confirm action will do. */
  description: string;
  /** Confirm button copy (default "Xác nhận"). */
  confirmLabel?: string;
  /** Cancel button copy (default "Hủy"). */
  cancelLabel?: string;
  /** Visual tone of the modal — defaults to `warning`. */
  severity?: ConfirmSeverity;
}

interface PendingConfirm extends Required<Omit<ConfirmOptions, "severity">> {
  severity: ConfirmSeverity;
  resolve: (value: boolean) => void;
}

const DEFAULTS = {
  confirmLabel: "Xác nhận",
  cancelLabel: "Hủy",
  severity: "warning" as ConfirmSeverity,
};

export function useConfirm(): [
  (options: ConfirmOptions) => Promise<boolean>,
  React.ReactElement,
] {
  const [pending, setPending] = useState<PendingConfirm | null>(null);

  // Track latest pending in a ref so close handlers can resolve cleanly
  // even if the component re-renders mid-prompt.
  const pendingRef = useRef<PendingConfirm | null>(null);
  pendingRef.current = pending;

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      setPending({
        title: options.title,
        description: options.description,
        confirmLabel: options.confirmLabel ?? DEFAULTS.confirmLabel,
        cancelLabel: options.cancelLabel ?? DEFAULTS.cancelLabel,
        severity: options.severity ?? DEFAULTS.severity,
        resolve,
      });
    });
  }, []);

  const close = useCallback((value: boolean) => {
    const current = pendingRef.current;
    if (current) {
      current.resolve(value);
    }
    setPending(null);
  }, []);

  const open = pending !== null;
  const severity = pending?.severity ?? "warning";

  const dialog = (
    <Modal
      open={open}
      onClose={() => close(false)}
      title={pending?.title}
      maxWidth={460}
      footer={
        <>
          <Button variant="ghost" onClick={() => close(false)}>
            {pending?.cancelLabel ?? DEFAULTS.cancelLabel}
          </Button>
          <Button
            variant={severity === "critical" ? "danger" : "primary"}
            onClick={() => close(true)}
          >
            {pending?.confirmLabel ?? DEFAULTS.confirmLabel}
          </Button>
        </>
      }
    >
      <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
        <SeverityIcon severity={severity} />
        <p style={{ margin: 0, lineHeight: 1.55, color: "var(--text-primary)" }}>
          {pending?.description}
        </p>
      </div>
    </Modal>
  );

  return [confirm, dialog];
}

function SeverityIcon({ severity }: { severity: ConfirmSeverity }) {
  if (severity === "critical") {
    return (
      <ShieldAlert
        size={22}
        style={{ color: "var(--severity-critical)", flexShrink: 0, marginTop: "2px" }}
      />
    );
  }
  if (severity === "warning") {
    return (
      <AlertTriangle
        size={22}
        style={{ color: "var(--severity-warning)", flexShrink: 0, marginTop: "2px" }}
      />
    );
  }
  return null;
}
