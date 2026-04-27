import { useCallback, useRef } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// useHoverPrefetch — Module G.3.
//
// Returns a memoised handler set (`onMouseEnter`, `onFocus`) that
// `queryClient.prefetchQuery`s a single query when the operator hovers
// or keyboard-focuses the target element.  Used on the sidebar so the
// data for the destination page starts loading before the click lands.
//
// Subsequent hovers within `cooldownMs` are no-ops so a flick of the
// mouse across the sidebar doesn't fire 5 refetches.  Default cooldown
// is 30 s — long enough for normal navigation, short enough that a
// genuine return visit rehydrates.
// ---------------------------------------------------------------------------

interface HoverPrefetchOptions<T> {
  /** React Query key for the query you want to warm up. */
  queryKey: QueryKey;
  /** Fetcher matching the destination page's `queryFn`. */
  queryFn: () => Promise<T>;
  /** Min ms between prefetches — default 30 000. */
  cooldownMs?: number;
  /** When false, the handlers are no-ops. Useful when navigation is
   * already in flight. */
  enabled?: boolean;
}

interface HoverPrefetchHandlers {
  onMouseEnter: () => void;
  onFocus: () => void;
}

export function useHoverPrefetch<T>(options: HoverPrefetchOptions<T>): HoverPrefetchHandlers {
  const { queryKey, queryFn, cooldownMs = 30_000, enabled = true } = options;
  const queryClient = useQueryClient();
  const lastFiredAtRef = useRef<number>(0);

  const fire = useCallback(() => {
    if (!enabled) return;
    const now = Date.now();
    if (now - lastFiredAtRef.current < cooldownMs) return;
    lastFiredAtRef.current = now;
    void queryClient.prefetchQuery({
      queryKey,
      queryFn,
      // Treat the prefetched data as fresh for the cooldown window so a
      // navigation arriving within `cooldownMs` doesn't immediately
      // refetch.
      staleTime: cooldownMs,
    });
  }, [enabled, cooldownMs, queryClient, queryKey, queryFn]);

  return {
    onMouseEnter: fire,
    onFocus: fire,
  };
}
