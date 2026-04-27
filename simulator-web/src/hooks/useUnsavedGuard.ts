import { useEffect } from "react";

// ---------------------------------------------------------------------------
// useUnsavedGuard — Module G.14.
//
// Hooks a `beforeunload` listener while `dirty` is true so the browser
// prompts the operator before refreshing / closing the tab on a form
// with un-persisted edits.  Modern browsers ignore custom messages and
// show a generic "Changes you made may not be saved" string — that's
// fine; the prompt itself is the value.
//
// Limitations:
//   * In-app navigation (sidebar click, programmatic `navigate(...)`) is
//     **not** intercepted.  React Router v6 with `<BrowserRouter>` (non-
//     data router, which we use today) doesn't support `useBlocker`.  If
//     we ever migrate to `createBrowserRouter`, this hook can be
//     extended with `useBlocker` and a `<ConfirmDialog/>` swap.
//   * Browsers throttle / suppress this prompt if the page hasn't seen
//     a user gesture, which is the right call for unattended tabs.
//
// Typical usage:
//
//   const isDirty = inputs.tickInterval !== String(serverData.tick) ||
//                   inputs.pushInterval !== String(serverData.push);
//   useUnsavedGuard(isDirty);
// ---------------------------------------------------------------------------

export function useUnsavedGuard(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      // Required for Chromium + Firefox; modern browsers display their
      // own canned message regardless of the `returnValue` string.
      event.preventDefault();
      event.returnValue = "";
      return "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
}
