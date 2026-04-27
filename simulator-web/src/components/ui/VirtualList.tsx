import { useRef, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

// ---------------------------------------------------------------------------
// VirtualList — Module G.16.
//
// Thin wrapper around `@tanstack/react-virtual` (already a dependency
// for the analytics tables) for the simple "fixed-height row, vertical
// scroll" case the simulator console keeps re-implementing — recent
// events log, log viewer, dense device tables.
//
// Use this when:
//   * The list can grow past ~50 items.
//   * Each row has a known stable height (or you can pass an estimator).
//   * You need keyboard/scroll smoothness on long sessions.
//
// Skip this for short lists (<50 items) — the overhead of measuring +
// the absolute-positioned row machinery is more code than the rows
// themselves.
//
// Generic on `T` so the row renderer is type-safe.
// ---------------------------------------------------------------------------

interface VirtualListProps<T> {
  items: T[];
  /** Fixed (or estimated) row height in px. */
  rowHeight: number;
  /** Total scrollable height, e.g. "320px" or 400. */
  height: number | string;
  /** Render a single row; receives the item + virtualizer-supplied index. */
  renderRow: (item: T, index: number) => ReactNode;
  /** Optional key extractor — defaults to index, but pass an id for
   *  stable identity across reorders. */
  getKey?: (item: T, index: number) => string | number;
  /** Number of rows to render outside the visible window (default 4). */
  overscan?: number;
  /** Optional aria-label on the scroll container. */
  ariaLabel?: string;
}

export function VirtualList<T>({
  items,
  rowHeight,
  height,
  renderRow,
  getKey,
  overscan = 4,
  ariaLabel,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement | null>(null);

  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan,
    getItemKey: getKey ? (index) => getKey(items[index], index) : undefined,
  });

  const totalHeight = rowVirtualizer.getTotalSize();
  const virtualRows = rowVirtualizer.getVirtualItems();

  return (
    <div
      ref={parentRef}
      aria-label={ariaLabel}
      style={{
        height: typeof height === "number" ? `${height}px` : height,
        overflowY: "auto",
        // Stable scrollbar gutter so the layout doesn't jitter when
        // the scrollbar appears between renders.
        scrollbarGutter: "stable",
      }}
    >
      <div
        style={{
          height: `${totalHeight}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualRows.map((virtualRow) => {
          const item = items[virtualRow.index];
          return (
            <div
              key={virtualRow.key}
              data-index={virtualRow.index}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
                height: `${virtualRow.size}px`,
              }}
            >
              {renderRow(item, virtualRow.index)}
            </div>
          );
        })}
      </div>
    </div>
  );
}
