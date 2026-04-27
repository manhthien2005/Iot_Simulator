import { toast } from "sonner";

export const notify = {
  success: (msg: string) => toast.success(msg),
  error: (msg: string) => toast.error(msg),
  warning: (msg: string) => toast.warning(msg),
  info: (msg: string) => toast.info(msg),
};

// ---------------------------------------------------------------------------
// runWithToast — Module G.1.
//
// Wraps a promise (typically a mutation) with sonner's `toast.promise`
// so callers don't have to juggle three things (loading state, success
// toast, error toast) for every single button.  The previous pattern
// across the codebase was:
//
//   setIsX(true);
//   try {
//     await mutate();
//     notify.success("...");
//   } catch (e) {
//     notify.error("...");
//   } finally {
//     setIsX(false);
//   }
//
// `runWithToast` collapses that to:
//
//   await runWithToast(mutate(), {
//     loading: "Đang gửi…",
//     success: "Đã gửi.",
//     error: "Gửi thất bại.",
//   });
//
// The pending state is handled by sonner's loading toast UI, so the
// caller usually no longer needs `isPending` for the button label —
// `disabled` during the await is enough.  When the caller does need
// imperative pending state (e.g. to disable other buttons), keep it.
// ---------------------------------------------------------------------------

interface RunWithToastMessages<T> {
  /** Loading toast copy. */
  loading: string;
  /** Success copy — string, or function returning a string from the resolved value. */
  success: string | ((value: T) => string);
  /** Error copy — string, or function returning a string from the thrown error. */
  error: string | ((error: unknown) => string);
}

/**
 * Wrap a promise with sonner's `toast.promise` and return the original
 * promise so the caller can `await` the resolved value or rethrow.
 *
 * IMPORTANT: re-throws on failure so React Query / caller code can react
 * (e.g. revalidate cache, log telemetry). The toast is fire-and-forget.
 */
export async function runWithToast<T>(
  promise: Promise<T>,
  messages: RunWithToastMessages<T>,
): Promise<T> {
  toast.promise(promise, {
    loading: messages.loading,
    success: messages.success,
    error: messages.error,
  });
  return promise;
}
