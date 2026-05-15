import { memo, useMemo } from "react";

// ---------------------------------------------------------------------------
// Sparkline — minimal SVG line trace for short numeric series.
//
// Used by Module C's `<MotionPreviewPanel/>` to render real accel/gyro
// arrays from the simulator dataset.  No animation, no domain padding —
// keeps the wire format honest by drawing exactly what the BE returned.
// ---------------------------------------------------------------------------

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  /** Force the y-domain. Falls back to [min, max] of `values`. */
  yDomain?: [number, number];
  /** Optional label rendered above the trace for accessibility. */
  ariaLabel?: string;
  /** When true, the SVG stretches to 100% of its parent width via viewBox.
   *  `width` is still used as the internal coordinate space. */
  fluid?: boolean;
}

function SparklineInner({
  values,
  width = 160,
  height = 28,
  stroke = "var(--accent-cyan)",
  fill = "none",
  yDomain,
  ariaLabel,
  fluid = false,
}: SparklineProps) {
  const path = useMemo(() => {
    if (values.length === 0) return "";
    const [yMin, yMax] = yDomain ?? deriveDomain(values);
    const range = yMax - yMin || 1;
    const stride = values.length > 1 ? width / (values.length - 1) : width;
    return values
      .map((value, index) => {
        const x = index * stride;
        const y = height - ((value - yMin) / range) * height;
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  }, [values, width, height, yDomain]);

  const svgSizeProps = fluid
    ? ({ width: "100%", height, viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: "none" } as const)
    : ({ width, height } as const);

  if (values.length === 0) {
    return (
      <svg
        {...svgSizeProps}
        role="img"
        aria-label={ariaLabel ?? "no data"}
        style={{ opacity: 0.4, display: "block" }}
      >
        <line
          x1={0}
          x2={width}
          y1={height / 2}
          y2={height / 2}
          stroke="var(--border-default)"
          strokeDasharray="3 3"
        />
      </svg>
    );
  }

  return (
    <svg
      {...svgSizeProps}
      role="img"
      aria-label={ariaLabel}
      style={{ display: "block" }}
    >
      <path d={path} fill={fill} stroke={stroke} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function deriveDomain(values: number[]): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (min === max) return [min - 0.5, max + 0.5];
  return [min, max];
}

export const Sparkline = memo(SparklineInner);
