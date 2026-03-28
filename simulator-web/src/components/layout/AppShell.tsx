import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "auto 1fr", background: "var(--bg-base)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar />
        <main style={{ padding: "24px", maxWidth: "1600px" }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

