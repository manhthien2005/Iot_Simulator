import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input(props: InputProps) {
  return (
    <input
      {...props}
      style={{
        background: "var(--bg-base)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)",
        color: "var(--text-primary)",
        padding: "8px 12px",
        fontSize: "13px",
        width: "100%",
        ...props.style,
      }}
    />
  );
}

