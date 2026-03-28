import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "outline";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  disabled?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
}

const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  primary: { background: "var(--accent-cyan)", color: "var(--text-inverse)", border: "1px solid transparent" },
  secondary: { background: "var(--bg-elevated)", color: "var(--text-primary)", border: "1px solid var(--border-default)" },
  danger: { background: "var(--severity-critical)", color: "#fff", border: "1px solid transparent" },
  ghost: { background: "transparent", color: "var(--text-secondary)", border: "1px solid transparent" },
  outline: { background: "transparent", color: "var(--accent-cyan)", border: "1px solid var(--accent-cyan)" },
};

const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
  sm: { minHeight: "32px", padding: "6px 12px", fontSize: "12px" },
  md: { minHeight: "36px", padding: "8px 16px", fontSize: "13px" },
  lg: { minHeight: "42px", padding: "10px 18px", fontSize: "14px" },
};

export function Button({
  children,
  variant = "secondary",
  size = "md",
  loading = false,
  disabled = false,
  leftIcon,
  rightIcon,
  onClick,
  type = "button",
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      type={type}
      disabled={isDisabled}
      onClick={onClick}
      style={{
        ...variantStyles[variant],
        ...sizeStyles[size],
        borderRadius: "var(--radius-md)",
        fontWeight: 600,
        display: "inline-flex",
        alignItems: "center",
        gap: "8px",
        transition:
          "color var(--duration-fast) var(--ease-default), background-color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default)",
        opacity: isDisabled ? 0.6 : 1,
      }}
    >
      {loading ? <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>...</span> : leftIcon}
      <span>{children}</span>
      {!loading ? rightIcon : null}
    </button>
  );
}

