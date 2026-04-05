import { BarChart3, Clapperboard, LayoutDashboard, Play, ShieldCheck, Watch, ChevronLeft, ChevronRight, Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { useUiStore } from "../../stores/uiStore";

const links = [
  { to: "/dashboard", label: "Bảng điều khiển", icon: LayoutDashboard },
  { to: "/devices", label: "Thiết bị", icon: Watch },
  { to: "/scenarios", label: "Kịch bản", icon: Clapperboard },
  { to: "/session", label: "Phiên mô phỏng", icon: Play },
  { to: "/analytics", label: "Phân tích", icon: BarChart3 },
  { to: "/verification", label: "Xác minh", icon: ShieldCheck },
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
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMobileOpen(false)}
                style={({ isActive }) => ({
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "8px 10px",
                  borderRadius: "var(--radius-md)",
                  border: `1px solid ${isActive ? "var(--accent-cyan)" : "transparent"}`,
                  background: isActive ? "rgba(6,182,212,0.12)" : "transparent",
                  color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                  transition:
                    "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
                  justifyContent: "flex-start",
                })}
              >
                <link.icon size={16} strokeWidth={1.5} />
                <span>{link.label}</span>
              </NavLink>
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
          <NavLink
            key={link.to}
            to={link.to}
            style={({ isActive }) => ({
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: sidebarCollapsed ? "8px" : "8px 10px",
              borderRadius: "var(--radius-md)",
              border: `1px solid ${isActive ? "var(--accent-cyan)" : "transparent"}`,
              background: isActive ? "rgba(6,182,212,0.12)" : "transparent",
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              transition:
                "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
              justifyContent: sidebarCollapsed ? "center" : "flex-start",
            })}
          >
            <link.icon size={16} strokeWidth={1.5} />
            {!sidebarCollapsed ? <span>{link.label}</span> : null}
          </NavLink>
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
