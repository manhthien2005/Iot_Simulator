import type { CSSProperties } from "react";

interface SkeletonProps {
  className?: string;
  style?: CSSProperties;
}

export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      className={className}
      style={{
        borderRadius: "var(--radius-md)",
        background: "linear-gradient(90deg, rgba(30,45,74,0.25) 25%, rgba(51,65,90,0.45) 50%, rgba(30,45,74,0.25) 75%)",
        backgroundSize: "200px 100%",
        animation: "shimmer 1.4s infinite linear",
        ...style,
      }}
    />
  );
}
