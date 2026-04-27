import { BarChart3, Clapperboard, LayoutDashboard, Play, Settings, ShieldCheck, Watch, Wrench, ChevronLeft, ChevronRight, Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import type { QueryKey } from "@tanstack/react-query";
import { useUiStore } from "../../stores/uiStore";
import { useHoverPrefetch } from "../../hooks/useHoverPrefetch";
import { fetchDashboardSummary } from "../../services/dashboardApi";
import { fetchDbDevices } from "../../services/deviceApi";
import { fetchScenarios } from "../../services/scenarioApi";
import { fetchSessions } from "../../services/sessionApi";

// ---------------------------------------------------------------------------
// Module G.6 — hover prefetch.
//
// Each main-route entry carries an optional `prefetch` descriptor that
// matches the destination page's primary `useQuery({queryKey, queryFn})`.
// On hover/focus we warm React Query's cache so the destination renders
// from cache rather than spinner-then-fetch.  A 30 s cooldown (in
// `useHoverPrefetch`) keeps a sweep of the sidebar from firing five
// network requests in a row.
//
// Routes whose primary data depends on runtime params (e.g. /analytics
// needs `deviceId`, /verification needs the active `sessionId`) get no
// prefetch hint — we don't want to guess a deviceId.
// ---------------------------------------------------------------------------

interface NavLinkPrefetch {
  queryKey: QueryKey;
  // Loose type to accept all 4 fetcher signatures (no shared shape).
  queryFn: () => Promise<unknown>;
}

interface NavLinkSpec {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  prefetch?: NavLinkPrefetch;
}

const links: NavLinkSpec[] = [
  {
    to: "/dashboard",
    label: "Bảng điều khiển",
    icon: LayoutDashboard,
    prefetch: { queryKey: ["dashboard", "summary"], queryFn: fetchDashboardSummary },
  },
  {
    to: "/devices",
    label: "Thiết bị",
    icon: Watch,
    prefetch: { queryKey: ["db-devices"], queryFn: fetchDbDevices },
  },
  {
    to: "/scenarios",
    label: "Kịch bản",
    icon: Clapperboard,
    prefetch: { queryKey: ["scenarios"], queryFn: fetchScenarios },
  },
  {
    to: "/session",
    label: "Phiên mô phỏng",
    icon: Play,
    prefetch: { queryKey: ["sessions"], queryFn: fetchSessions },
  },
  { to: "/analytics", label: "Phân tích", icon: BarChart3 },
  { to: "/diagnostics", label: "Diagnostics", icon: Wrench },
  {
    to: "/verification",
    label: "Trung tâm Bằng chứng",
    icon: ShieldCheck,
    // Verification page first reads `useSessions` to find the active
    // session, then derives `useVerification(sessionId)` from there.
    // Warming sessions covers the first half; the cooldown in
    // `useHoverPrefetch` dedupes against the /session prefetch.
    prefetch: { queryKey: ["sessions"], queryFn: fetchSessions },
  },
  { to: "/settings", label: "Cấu hình runtime", icon: Settings },
];

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(typeof window !== "undefined" && window.innerWidth < breakpoint);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < breakpoint);
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, [breakpoint]);
  return isMobile;
}

export function Sidebar() {
  const { sidebarCollapsed, setSidebarCollapsed } = useUiStore();
  const isMobile = useIsMobile();
  const [mobileOpen, setMobileOpen] = useState(false);
  const width = sidebarCollapsed ? 64 : 240;

  useEffect(() => {
    const apply = () => {
      if (window.innerWidth < 1280 && window.innerWidth >= 768) {
        setSidebarCollapsed(true);
      }
    };
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, [setSidebarCollapsed]);

  // Close mobile sidebar on route changes or resize to desktop
  useEffect(() => {
    if (!isMobile) setMobileOpen(false);
  }, [isMobile]);

  if (isMobile) {
    return (
      <>
        {/* Hamburger button - rendered via portal or placed in topbar area */}
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Mở menu"
          style={{
            position: "fixed",
            top: "10px",
            left: "10px",
            zIndex: "var(--z-toast)" as unknown as number,
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            color: "var(--text-primary)",
            width: "36px",
            height: "36px",
            display: "grid",
            placeItems: "center",
          }}
        >
          <Menu size={18} />
        </button>

        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            className="sidebar-overlay"
            onClick={() => setMobileOpen(false)}
            role="presentation"
          />
        )}

        {/* Mobile sidebar */}
        <aside
          className={`sidebar ${mobileOpen ? "sidebar--open" : ""}`}
          style={{
            borderRight: "1px solid var(--border-default)",
            background: "var(--bg-surface)",
            padding: "10px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
            <strong style={{ fontSize: "14px" }}>Điều hướng</strong>
            <button
              onClick={() => setMobileOpen(false)}
              style={{
                border: "1px solid var(--border-default)",
                background: "var(--bg-elevated)",
                color: "var(--text-secondary)",
                borderRadius: "var(--radius-md)",
                width: "28px",
                height: "28px",
                display: "grid",
                placeItems: "center",
              }}
            >
              <ChevronLeft size={14} />
            </button>
          </div>

          <nav style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
            {links.map((link) => (
              <SidebarLink
                key={link.to}
                link={link}
                collapsed={false}
                onNavigate={() => setMobileOpen(false)}
              />
            ))}
          </nav>

          <small
            style={{
              color: "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
            }}
          >
            simulator-web v0.3
          </small>
        </aside>
      </>
    );
  }

  return (
    <aside
      style={{
        width: `${width}px`,
        transition: "width var(--duration-fast) var(--ease-default)",
        borderRight: "1px solid var(--border-default)",
        background: "var(--bg-surface)",
        padding: "10px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        // Module H — bug 5 fix: pin desktop sidebar to viewport so the
        // navigation stays visible while the main content scrolls.  The
        // grid layout in `<AppShell/>` lets the sidebar be its own
        // scrolling container (auto on Y), preserving access to all nav
        // links on short viewports.
        position: "sticky",
        top: 0,
        height: "100vh",
        alignSelf: "start",
        overflowY: "auto",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: sidebarCollapsed ? "center" : "space-between", marginBottom: "8px" }}>
        {!sidebarCollapsed ? <strong style={{ fontSize: "14px" }}>Điều hướng</strong> : null}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          style={{
            border: "1px solid var(--border-default)",
            background: "var(--bg-elevated)",
            color: "var(--text-secondary)",
            borderRadius: "var(--radius-md)",
            width: "28px",
            height: "28px",
            display: "grid",
            placeItems: "center",
          }}
        >
          {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
        {links.map((link) => (
          <SidebarLink key={link.to} link={link} collapsed={sidebarCollapsed} />
        ))}
      </nav>

      <small
        style={{
          color: "var(--text-muted)",
          textAlign: sidebarCollapsed ? "center" : "left",
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
        }}
      >
        {sidebarCollapsed ? "v0.3" : "simulator-web v0.3"}
      </small>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// SidebarLink — wraps `<NavLink/>` with the G.6 hover prefetch wiring.
// Lives outside `<Sidebar/>` so the `useHoverPrefetch` call is stable
// per link (one hook per render, not per array length).
// ---------------------------------------------------------------------------

interface SidebarLinkProps {
  link: NavLinkSpec;
  collapsed: boolean;
  onNavigate?: () => void;
}

function SidebarLink({ link, collapsed, onNavigate }: SidebarLinkProps) {
  const prefetchHandlers = useHoverPrefetch({
    enabled: Boolean(link.prefetch),
    queryKey: link.prefetch?.queryKey ?? ["__noop__", link.to],
    queryFn: link.prefetch?.queryFn ?? noopFetcher,
  });

  return (
    <NavLink
      to={link.to}
      onClick={onNavigate}
      onMouseEnter={prefetchHandlers.onMouseEnter}
      onFocus={prefetchHandlers.onFocus}
      style={({ isActive }) => ({
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: collapsed ? "8px" : "8px 10px",
        borderRadius: "var(--radius-md)",
        border: `1px solid ${isActive ? "var(--accent-cyan)" : "transparent"}`,
        background: isActive ? "rgba(6,182,212,0.12)" : "transparent",
        color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
        transition:
          "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
        justifyContent: collapsed ? "center" : "flex-start",
      })}
    >
      <link.icon size={16} strokeWidth={1.5} />
      {!collapsed ? <span>{link.label}</span> : null}
    </NavLink>
  );
}

// Sentinel fetcher used when a link has no `prefetch` descriptor.  The
// hook is `enabled: false` in that case so this is never called — but
// React Query's typing requires a function reference.
const noopFetcher = (): Promise<unknown> => Promise.resolve(null);
