import { type ReactNode, useState, useId } from "react";

export interface TabItem {
  key: string;
  label: string;
  icon?: ReactNode;
}

interface TabsProps {
  items: TabItem[];
  activeKey: string;
  onChange: (key: string) => void;
  /** Visual variant */
  variant?: "underline" | "pill";
}

export function Tabs({ items, activeKey, onChange, variant = "pill" }: TabsProps) {
  const baseId = useId();

  if (variant === "underline") {
    return (
      <div
        role="tablist"
        aria-label="Tabs"
        style={{
          display: "flex",
          gap: "0",
          borderBottom: "1px solid var(--border-default)",
        }}
      >
        {items.map((item) => {
          const isActive = item.key === activeKey;
          return (
            <button
              key={item.key}
              role="tab"
              id={`${baseId}-tab-${item.key}`}
              aria-selected={isActive}
              aria-controls={`${baseId}-panel-${item.key}`}
              onClick={() => onChange(item.key)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 16px",
                fontSize: "13px",
                fontWeight: isActive ? 600 : 400,
                color: isActive ? "var(--accent-cyan)" : "var(--text-secondary)",
                background: "transparent",
                border: "none",
                borderBottom: `2px solid ${isActive ? "var(--accent-cyan)" : "transparent"}`,
                marginBottom: "-1px",
                transition:
                  "color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
                cursor: "pointer",
              }}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    );
  }

  // Default: pill variant
  return (
    <div
      role="tablist"
      aria-label="Tabs"
      style={{
        display: "inline-flex",
        gap: "4px",
        background: "var(--bg-surface)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-lg)",
        padding: "3px",
      }}
    >
      {items.map((item) => {
        const isActive = item.key === activeKey;
        return (
          <button
            key={item.key}
            role="tab"
            id={`${baseId}-tab-${item.key}`}
            aria-selected={isActive}
            aria-controls={`${baseId}-panel-${item.key}`}
            onClick={() => onChange(item.key)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 14px",
              fontSize: "13px",
              fontWeight: isActive ? 600 : 400,
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              background: isActive ? "var(--bg-elevated)" : "transparent",
              border: `1px solid ${isActive ? "var(--border-default)" : "transparent"}`,
              borderRadius: "var(--radius-md)",
              transition:
                "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default)",
              cursor: "pointer",
            }}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}

interface TabPanelProps {
  tabKey: string;
  activeKey: string;
  children: ReactNode;
}

/** Companion panel – renders children only when active */
export function TabPanel({ tabKey, activeKey, children }: TabPanelProps) {
  if (tabKey !== activeKey) return null;
  return (
    <div role="tabpanel" aria-labelledby={`tab-${tabKey}`}>
      {children}
    </div>
  );
}
