import { Activity, AlertTriangle, BarChart3, BedDouble, LayoutDashboard, Play, Settings, ShieldCheck, Watch, Wrench, ChevronLeft, ChevronRight, Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import type { QueryKey } from "@tanstack/react-query";
import { useUiStore } from "../../stores/uiStore";
import { useHoverPrefetch } from "../../hooks/useHoverPrefetch";
import { fetchDashboardSummary } from "../../services/dashboardApi";
import { fetchDbDevices } from "../../services/deviceApi";
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

const mainLinks: NavLinkSpec[] = [
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
    to: "/session",
    label: "Mô phỏng sinh tồn",
    icon: Play,
    prefetch: { queryKey: ["sessions"], queryFn: fetchSessions },
  },
  {
    to: "/fall-lab",
    label: "Phòng lab té ngã",
    icon: AlertTriangle,
    prefetch: { queryKey: ["sessions"], queryFn: fetchSessions },
  },
  {
    to: "/sleep-lab",
    label: "Mô phỏng giấc ngủ",
    icon: BedDouble,
    prefetch: { queryKey: ["db-devices"], queryFn: fetchDbDevices },
  },
  { to: "/analytics", label: "Phân tích", icon: BarChart3 },
  { to: "/diagnostics", label: "Diagnostics", icon: Wrench },
  {
    to: "/verification",
    label: "Trung tâm Bằng chứng",
    icon: ShieldCheck,
    prefetch: { queryKey: ["sessions"], queryFn: fetchSessions },
  },
];

const utilityLinks: NavLinkSpec[] = [
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
            borderRight: "1px solid rgba(255,255,255,0.06)",
            background: "var(--bg-surface)",
            padding: "12px 10px",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
        >
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 6px 14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ width: "30px", height: "30px", borderRadius: "var(--radius-md)", background: "var(--accent-cyan-bg-active)", display: "grid", placeItems: "center", flexShrink: 0 }}>
                <Activity size={16} color="var(--accent-cyan)" />
              </div>
              <span style={{ fontWeight: 700, fontSize: "14px", letterSpacing: "-0.01em" }}>IoT Simulator</span>
            </div>
            <button
              onClick={() => setMobileOpen(false)}
              style={{ border: "none", background: "transparent", color: "var(--text-secondary)", padding: "4px", borderRadius: "var(--radius-md)" }}
            >
              <ChevronLeft size={16} />
            </button>
          </div>

          <nav style={{ display: "flex", flexDirection: "column", gap: "2px", flex: 1 }}>
            {mainLinks.map((link) => (
              <SidebarLink key={link.to} link={link} collapsed={false} onNavigate={() => setMobileOpen(false)} />
            ))}
          </nav>

          <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "8px", marginTop: "4px", display: "flex", flexDirection: "column", gap: "2px" }}>
            {utilityLinks.map((link) => (
              <SidebarLink key={link.to} link={link} collapsed={false} onNavigate={() => setMobileOpen(false)} />
            ))}
            <div style={{ padding: "6px 10px" }}>
              <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "11px" }}>v0.3</span>
            </div>
          </div>
        </aside>
      </>
    );
  }

  return (
    <aside
      style={{
        width: `${width}px`,
        transition: "width var(--duration-normal) var(--ease-default)",
        borderRight: "1px solid rgba(255,255,255,0.06)",
        background: "var(--bg-surface)",
        padding: "12px 10px",
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        position: "sticky",
        top: 0,
        height: "100vh",
        alignSelf: "start",
        overflowY: "auto",
        overflowX: "hidden",
      }}
    >
      {/* Logo / Brand */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: sidebarCollapsed ? "center" : "space-between",
          padding: "4px 4px 16px",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "var(--radius-md)",
              background: "var(--accent-cyan-bg-active)",
              display: "grid",
              placeItems: "center",
              flexShrink: 0,
            }}
          >
            <Activity size={17} color="var(--accent-cyan)" />
          </div>
          {!sidebarCollapsed && (
            <span style={{ fontWeight: 700, fontSize: "14px", letterSpacing: "-0.01em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              IoT Simulator
            </span>
          )}
        </div>
        {!sidebarCollapsed && (
          <button
            onClick={() => setSidebarCollapsed(true)}
            aria-label="Thu gọn sidebar"
            style={{ border: "none", background: "transparent", color: "var(--text-muted)", padding: "4px", borderRadius: "var(--radius-md)", flexShrink: 0 }}
          >
            <ChevronLeft size={15} />
          </button>
        )}
        {sidebarCollapsed && (
          <button
            onClick={() => setSidebarCollapsed(false)}
            aria-label="Mở rộng sidebar"
            style={{ border: "none", background: "transparent", color: "var(--text-muted)", padding: "4px", borderRadius: "var(--radius-md)" }}
          >
            <ChevronRight size={15} />
          </button>
        )}
      </div>

      {/* Main navigation */}
      <nav style={{ display: "flex", flexDirection: "column", gap: "2px", flex: 1 }}>
        {mainLinks.map((link) => (
          <SidebarLink key={link.to} link={link} collapsed={sidebarCollapsed} />
        ))}
      </nav>

      {/* Utility / Settings section */}
      <div
        style={{
          borderTop: "1px solid rgba(255,255,255,0.06)",
          paddingTop: "8px",
          marginTop: "4px",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
        }}
      >
        {utilityLinks.map((link) => (
          <SidebarLink key={link.to} link={link} collapsed={sidebarCollapsed} />
        ))}
        {!sidebarCollapsed && (
          <div style={{ padding: "6px 10px" }}>
            <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "11px" }}>
              simulator-web v0.3
            </span>
          </div>
        )}
      </div>
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
      title={collapsed ? link.label : undefined}
      style={({ isActive }) => ({
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: collapsed ? "9px" : "9px 12px",
        borderRadius: "var(--radius-md)",
        border: "none",
        background: isActive ? "var(--accent-cyan-bg-active)" : "transparent",
        color: isActive ? "var(--accent-cyan)" : "var(--text-secondary)",
        fontWeight: isActive ? 600 : 400,
        fontSize: "13.5px",
        transition: "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default)",
        justifyContent: collapsed ? "center" : "flex-start",
        textDecoration: "none",
      })}
    >
      <link.icon size={17} strokeWidth={1.8} style={{ flexShrink: 0 }} />
      {!collapsed ? <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{link.label}</span> : null}
    </NavLink>
  );
}

// Sentinel fetcher used when a link has no `prefetch` descriptor.  The
// hook is `enabled: false` in that case so this is never called — but
// React Query's typing requires a function reference.
const noopFetcher = (): Promise<unknown> => Promise.resolve(null);
