import { useEffect } from "react";
import { useLocation } from "react-router-dom";

// ---------------------------------------------------------------------------
// useScrollToTop — Module G.13.
//
// React Router v6's `<BrowserRouter>` (non-data router) does **not**
// auto-restore scroll on navigation; clicking a sidebar entry while
// scrolled halfway down the dashboard leaves the destination page
// scrolled to the same y-offset.  This hook listens for `pathname`
// changes and resets `window` to (0, 0) on each transition.
//
// We *don't* persist + restore previous scroll position when going
// back — the operator is on a single-page sim console with no deep
// scrollable history; "always start at the top" matches expectation.
// If a future view needs preserve-on-back, we'd swap to the data-router
// `<ScrollRestoration/>` component.
//
// Hash-only changes (`#sleep`, `#risk-tools`) are excluded because the
// Diagnostics page already uses them for tab deep-linking — scrolling
// to top would fight the browser's anchor jump.
// ---------------------------------------------------------------------------

export function useScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    // Use `instant` if available — `smooth` looks janky when paired
    // with the route's lazy-Suspense fallback.
    try {
      window.scrollTo({ top: 0, left: 0, behavior: "instant" as ScrollBehavior });
    } catch {
      window.scrollTo(0, 0);
    }
  }, [pathname]);
}
