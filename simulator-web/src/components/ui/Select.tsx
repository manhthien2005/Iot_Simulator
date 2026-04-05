import type { SelectHTMLAttributes, ReactNode } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Optional label displayed above the select */
  label?: string;
  /** Error message displayed below the select */
  error?: string;
  /** Helper text displayed below the select (hidden when error is shown) */
  helperText?: string;
  /** Size variant */
  selectSize?: "sm" | "md" | "lg";
  /** Full width */
  fullWidth?: boolean;
  children: ReactNode;
}

const sizeMap: Record<"sm" | "md" | "lg", React.CSSProperties> = {
  sm: { minHeight: "32px", padding: "4px 10px", fontSize: "12px" },
  md: { minHeight: "36px", padding: "6px 12px", fontSize: "13px" },
  lg: { minHeight: "42px", padding: "8px 14px", fontSize: "14px" },
};

export function Select({
  label,
  error,
  helperText,
  selectSize = "md",
  fullWidth = false,
  children,
  style,
  id,
  ...rest
}: SelectProps) {
  const selectId = id || (label ? `select-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  const hasError = Boolean(error);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: fullWidth ? "100%" : undefined }}>
      {label && (
        <label
          htmlFor={selectId}
          style={{
            color: "var(--text-secondary)",
            fontSize: "12px",
            fontWeight: 500,
          }}
        >
          {label}
        </label>
      )}
      <select
        id={selectId}
        {...rest}
        style={{
          background: "var(--bg-base)",
          color: "var(--text-primary)",
          border: `1px solid ${hasError ? "var(--severity-critical)" : "var(--border-default)"}`,
          borderRadius: "var(--radius-md)",
          outline: "none",
          transition:
            "border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default)",
          appearance: "none",
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 10px center",
          paddingRight: "32px",
          width: fullWidth ? "100%" : undefined,
          ...sizeMap[selectSize],
          ...style,
        }}
      >
        {children}
      </select>
      {hasError && (
        <span style={{ color: "var(--severity-critical)", fontSize: "11px" }}>{error}</span>
      )}
      {!hasError && helperText && (
        <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>{helperText}</span>
      )}
    </div>
  );
}
