import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { Skeleton } from "../ui/Skeleton";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "auto 1fr", background: "var(--bg-base)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar />
        <main style={{ padding: "24px", maxWidth: "1600px" }}>
          <Suspense fallback={<RouteContentFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}

function RouteContentFallback() {
  return (
    <div style={{ display: "grid", gap: "14px" }}>
      <Skeleton style={{ height: "32px", width: "240px" }} />
      <Skeleton style={{ height: "18px", width: "420px", maxWidth: "100%" }} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px" }}>
        <Skeleton style={{ height: "120px" }} />
        <Skeleton style={{ height: "120px" }} />
        <Skeleton style={{ height: "120px" }} />
      </div>
    </div>
  );
}
