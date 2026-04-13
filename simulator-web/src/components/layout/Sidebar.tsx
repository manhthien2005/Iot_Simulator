import { BarChart3, Clapperboard, LayoutDashboard, Play, Settings, ShieldCheck, Watch, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { useUiStore } from "../../stores/uiStore";

const links = [
  { to: "/dashboard", label: "Bảng điều khiển", icon: LayoutDashboard },
  { to: "/devices", label: "Thiết bị", icon: Watch },
  { to: "/scenarios", label: "Kịch bản", icon: Clapperboard },
  { to: "/session", label: "Phiên mô phỏng", icon: Play },
  { to: "/analytics", label: "Phân tích", icon: BarChart3 },
  { to: "/verification", label: "Xác minh", icon: ShieldCheck },
  { to: "/settings", label: "Cài đặt", icon: Settings },
];

export function Sidebar() {
  const { sidebarCollapsed, setSidebarCollapsed } = useUiStore();
  const width = sidebarCollapsed ? 64 : 240;

  useEffect(() => {
    const apply = () => {
      if (window.innerWidth < 1280) {
        setSidebarCollapsed(true);
      }
    };
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, [setSidebarCollapsed]);

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
