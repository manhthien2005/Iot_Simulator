import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import "./index.css";

// ---------------------------------------------------------------------------
// Module G.8 — query cache persister.
//
// Hydrates React Query's cache from `localStorage` on cold-load so the
// operator sees the *previous* dashboard / device list / scenarios /
// sessions data within ~5 ms of HTML parse, then refetches in the
// background.  Eliminates the "blank-then-spinner-then-data" flash that
// makes a refresh feel slower than it actually is.
//
// Design notes:
//   1. `gcTime` is bumped to 24 h so persisted queries aren't garbage-
//      collected before the persister has a chance to write them.
//      (Default is 5 min — anything older never makes it to disk.)
//   2. We *deny* persisting transient / high-frequency queries via
//      `shouldDehydrateQuery`.  Persisting `["motion","latest",...]`,
//      `["fall","state",...]`, `["events","recent",...]` would write to
//      localStorage every poll tick and hand the operator stale state
//      on rehydrate.  Only "static-shaped" queries (scenarios, devices,
//      sessions, dashboard summary, db-devices, settings) are persisted
//      via the firstKey allowlist, plus a tuple allowlist for nested
//      keys like `["sim","health","v2"]` (Module H bug 1+2 — keep the
//      hero pills warm across navigations and short BE outages).
//   3. `buster: "v1"` invalidates the persisted blob if we ever rename
//      a queryKey or change a schema in a backwards-incompatible way.
//      Bump this when adding a breaking change to a persisted query.
// ---------------------------------------------------------------------------

const PERSIST_ALLOWLIST = new Set<string>([
  "scenarios",
  "sessions",
  "devices",
  "db-devices",
  "dashboard",
  "settings",
]);

// Tuple allowlist — for queryKeys whose firstKey is a generic namespace
// (e.g. "sim") that we don't want to whitelist wholesale.  Each tuple
// must match the leading segments of `queryKey` exactly.
const PERSIST_TUPLE_ALLOWLIST: ReadonlyArray<readonly string[]> = [
  ["sim", "health"], // matches ["sim","health","v2"] from useSystemHealth
];

function matchesTupleAllowlist(queryKey: readonly unknown[]): boolean {
  return PERSIST_TUPLE_ALLOWLIST.some((tuple) =>
    tuple.every((seg, i) => queryKey[i] === seg),
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      // 24h — long enough that persisted queries survive the gc sweep
      // before the persister flushes.  Active polling still keeps the
      // data fresh, this just controls when *idle* cache entries are
      // evicted.
      gcTime: 24 * 60 * 60 * 1000,
    },
  },
});

const persister = createSyncStoragePersister({
  storage: typeof window !== "undefined" ? window.localStorage : undefined,
  key: "iot-sim:react-query-cache",
  // Quiet failure on quota errors (private browsing, full disk, etc.).
  // The app degrades gracefully back to in-memory caching.
  retry: ({ error }) => {
    if (typeof console !== "undefined") {
      console.warn("[query-persister] failed to write cache:", error);
    }
    return undefined;
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        // 24h max — anything older is treated as cold and refetched.
        maxAge: 24 * 60 * 60 * 1000,
        // Bump when persisted-query schema changes break compatibility.
        buster: "v1",
        dehydrateOptions: {
          shouldDehydrateQuery: (query) => {
            const firstKey = query.queryKey[0];
            if (typeof firstKey !== "string") return false;
            if (PERSIST_ALLOWLIST.has(firstKey)) return true;
            return matchesTupleAllowlist(query.queryKey);
          },
        },
      }}
    >
      <BrowserRouter>
        <App />
        <Toaster position="bottom-right" richColors theme="dark" duration={4000} />
      </BrowserRouter>
    </PersistQueryClientProvider>
  </React.StrictMode>
);
