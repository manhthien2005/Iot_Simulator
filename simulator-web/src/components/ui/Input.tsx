import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Optional label displayed above the input */
  label?: string;
  /** Error message displayed below the input */
  error?: string;
  /** Helper text displayed below the input (hidden when error is shown) */
  helperText?: string;
  /** Input size variant */
  inputSize?: "sm" | "md" | "lg";
  /** Full width (default true) */
  fullWidth?: boolean;
}

const sizeMap: Record<"sm" | "md" | "lg", React.CSSProperties> = {
  sm: { minHeight: "32px", padding: "4px 10px", fontSize: "12px" },
  md: { minHeight: "36px", padding: "8px 12px", fontSize: "13px" },
  lg: { minHeight: "42px", padding: "10px 14px", fontSize: "14px" },
};

export function Input({
  label,
  error,
  helperText,
  inputSize = "md",
  fullWidth = true,
  style,
  id,
  ...props
}: InputProps) {
  const inputId = id || (label ? `input-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  const hasError = Boolean(error);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: fullWidth ? "100%" : undefined }}>
      {label && (
        <label
          htmlFor={inputId}
          style={{
            color: "var(--text-secondary)",
            fontSize: "12px",
            fontWeight: 500,
          }}
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        {...props}
        style={{
          background: "var(--bg-base)",
          border: `1px solid ${hasError ? "var(--severity-critical)" : "var(--border-default)"}`,
          borderRadius: "var(--radius-md)",
          color: "var(--text-primary)",
          outline: "none",
          transition:
            "border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default)",
          width: fullWidth ? "100%" : undefined,
          ...sizeMap[inputSize],
          ...style,
        }}
      />
      {hasError && (
        <span style={{ color: "var(--severity-critical)", fontSize: "11px" }}>{error}</span>
      )}
      {!hasError && helperText && (
        <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>{helperText}</span>
      )}
    </div>
  );
}
