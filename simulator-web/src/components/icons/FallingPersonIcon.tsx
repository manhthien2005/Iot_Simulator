import type { SVGProps } from "react";

// ---------------------------------------------------------------------------
// FallingPersonIcon — sidebar nav icon for `/fall-lab` (Mô phỏng té ngã).
//
// Stylistic match for lucide-react icons:
//   * 24x24 viewBox
//   * stroke + fill="none" so callers can override stroke color via CSS
//     (we use `currentColor` so the active/inactive nav color follows the
//     `<NavLink/>` style block).
//   * Default `strokeWidth=1.8` + `strokeLinecap="round"` + `strokeLinejoin="round"`
//     identical to the lucide-react default sidebar render path.
//
// API mirrors lucide-react: `size` (number|string) + the standard
// `SVGProps<SVGSVGElement>` so `<link.icon size={17} strokeWidth={1.8} />`
// in [Sidebar.tsx](../layout/Sidebar.tsx) just works.
//
// Visual: a stick figure mid-fall — head tilted forward, torso slanted,
// one arm extended down toward a horizontal ground line.  Avoids medical
// alarm imagery (no SOS chevron, no red cross) so it reads as "research /
// simulation" rather than "live emergency".
// ---------------------------------------------------------------------------

interface FallingPersonIconProps extends SVGProps<SVGSVGElement> {
  size?: number | string;
}

export function FallingPersonIcon({
  size = 24,
  strokeWidth = 1.8,
  ...rest
}: FallingPersonIconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {/* Ground line */}
      <line x1="3" y1="21" x2="21" y2="21" />
      {/* Head — tilted forward toward the ground */}
      <circle cx="7.5" cy="6.5" r="2.2" />
      {/* Torso — diagonal stroke from upper-left toward lower-right */}
      <path d="M9 8 L15 14" />
      {/* Trailing arm — back/up */}
      <path d="M9 8 L5.5 11" />
      {/* Leading arm — extended toward the ground */}
      <path d="M15 14 L18 18" />
      {/* Trailing leg */}
      <path d="M15 14 L13 19" />
      {/* Leading leg — knee bent, foot near ground */}
      <path d="M15 14 L18.5 17" />
    </svg>
  );
}
