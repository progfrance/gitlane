/** Windowed commit table: renders only visible rows + overdraw (PLAN §11).
 *
 * The full list is positioned via absolute offsets inside a spacer div; the
 * scroller is the same element, so native scrolling stays smooth.
 * Scroll geometry is reported to the viewport bus (rAF-coalesced) so the
 * mini-timeline viewport stays in sync without re-rendering the app.
 * Graph width flows through the --graph-width CSS variable, set once per
 * maxLane change on this container — rows never re-render for it.
 */
import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CommitItem } from "../api/client";
import CommitRow from "./CommitRow";
import { ROW_HEIGHT } from "../graph/coords";
import { reportViewport } from "../store/viewport";
import { useI18n } from "../i18n";

const OVERDRAW = 8; // rows rendered above/below the viewport
const LOAD_MORE_EDGE = 400; // px from bottom to trigger the next page

interface Props {
  items: CommitItem[];
  graphWidth: number;
  remote: string | null;
  hoveredSha: string | null;
  selectedSha: string | null;
  query: string;
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  onHover: (sha: string | null) => void;
  onSelect: (sha: string) => void;
  scrollRef: React.RefObject<HTMLDivElement | null>;
}

function VirtualCommitTableInner({
  items, graphWidth, remote, hoveredSha, selectedSha, query,
  hasMore, loadingMore, onLoadMore, onHover, onSelect, scrollRef,
}: Props) {
  const { t } = useI18n();
  const [range, setRange] = useState({ start: 0, end: Math.min(items.length, 40) });
  const frame = useRef<number | undefined>(undefined);
  const guard = useRef({ hasMore, loadingMore, onLoadMore, length: items.length });

  // Keep the latest pagination facts available to the rAF scroll handler.
  useEffect(() => {
    guard.current = { hasMore, loadingMore, onLoadMore, length: items.length };
  }, [hasMore, loadingMore, onLoadMore, items.length]);

  const recompute = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const first = Math.max(0, Math.floor(el.scrollTop / ROW_HEIGHT) - OVERDRAW);
    const visible = Math.ceil(el.clientHeight / ROW_HEIGHT) + 2 * OVERDRAW;
    setRange((prev) => {
      const next = { start: first, end: Math.min(guard.current.length, first + visible) };
      return prev.start === next.start && prev.end === next.end ? prev : next;
    });
    reportViewport({ top: el.scrollTop, height: el.scrollHeight, client: el.clientHeight });

    // Infinite scroll: load the next page when the user nears the bottom.
    if (
      guard.current.hasMore &&
      !guard.current.loadingMore &&
      el.scrollTop + el.clientHeight >= el.scrollHeight - LOAD_MORE_EDGE
    ) {
      guard.current.onLoadMore();
    }
  }, [scrollRef]);

  // New list (branch switch, repo switch, search): reset to top.
  const len = items.length;
  const firstSha = items[0]?.sha;
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = 0;
    setRange({ start: 0, end: Math.min(len, 40) });
    reportViewport({ top: 0, height: el?.scrollHeight ?? 1, client: el?.clientHeight ?? 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstSha, len === 0]);

  useEffect(() => {
    recompute();
  }, [recompute, firstSha, len]);

  const onScrollWrapped = useCallback(() => {
    if (frame.current !== undefined) cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(recompute);
  }, [recompute]);

  const slice = items.slice(range.start, range.end);

  return (
    <div
      className="commit-scroll"
      ref={scrollRef as React.RefObject<HTMLDivElement>}
      onScroll={onScrollWrapped}
      role="grid"
      aria-label="commits"
      aria-rowcount={items.length}
      style={{ "--graph-width": `${graphWidth}px` } as React.CSSProperties}
    >
      <div style={{ height: items.length * ROW_HEIGHT, position: "relative" }}>
        <div
          style={{
            position: "absolute",
            top: range.start * ROW_HEIGHT,
            left: 0,
            right: 0,
          }}
        >
          {slice.map((c, i) => (
            <CommitRow
              key={c.sha}
              commit={c}
              index={range.start + i}
              remote={remote}
              hovered={hoveredSha === c.sha}
              selected={selectedSha === c.sha}
              query={query}
              onHover={onHover}
              onSelect={onSelect}
            />
          ))}
        </div>
      </div>
      <div className="commit-scroll-footer" aria-live="polite">
        {loadingMore
          ? t("loading_more")
          : hasMore
            ? t("scroll_for_more")
            : t("end_of_history")}
      </div>
    </div>
  );
}

// Parent passes fresh inline closures for onHover/onSelect; without a custom
// compare the memo would be useless. Compare data, ignore callback identity.
const VirtualCommitTable = memo(VirtualCommitTableInner, (a, b) =>
  a.items === b.items &&
  a.graphWidth === b.graphWidth &&
  a.remote === b.remote &&
  a.hoveredSha === b.hoveredSha &&
  a.selectedSha === b.selectedSha &&
  a.query === b.query &&
  a.hasMore === b.hasMore &&
  a.loadingMore === b.loadingMore &&
  a.scrollRef === b.scrollRef,
);
export default VirtualCommitTable;
