/** Windowed commit table: renders only visible rows + overdraw (PLAN §11).
 *
 * The full list is positioned via absolute offsets inside a spacer div; the
 * scroller is the same element, so native scrolling stays smooth and the
 * mini-timeline viewport stays in sync via the onScroll handler.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { CommitItem } from "../api/client";
import CommitRow from "./CommitRow";
import { ROW_HEIGHT } from "../graph/coords";
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
  onScroll: (e: React.UIEvent<HTMLDivElement>) => void;
  scrollRef: React.RefObject<HTMLDivElement | null>;
}

export default function VirtualCommitTable({
  items, graphWidth, remote, hoveredSha, selectedSha, query,
  hasMore, loadingMore, onLoadMore, onHover, onSelect, onScroll, scrollRef,
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
    setRange({ start: first, end: Math.min(items.length, first + visible) });

    // Infinite scroll: load the next page when the user nears the bottom.
    if (
      guard.current.hasMore &&
      !guard.current.loadingMore &&
      el.scrollTop + el.clientHeight >= el.scrollHeight - LOAD_MORE_EDGE
    ) {
      guard.current.onLoadMore();
    }
  }, [items.length, scrollRef]);

  useEffect(() => {
    setRange({ start: 0, end: Math.min(items.length, 40) });
    const el = scrollRef.current;
    if (el) el.scrollTop = 0;
  }, [items.length === 0]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    recompute();
  }, [recompute]);

  const onScrollWrapped = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      if (frame.current !== undefined) cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(recompute);
      onScroll(e);
    },
    [recompute, onScroll]
  );

  const slice = items.slice(range.start, range.end);

  return (
    <div className="commit-scroll" ref={scrollRef as React.RefObject<HTMLDivElement>} onScroll={onScrollWrapped}>
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
              graphWidth={graphWidth}
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
      <div className="commit-scroll-footer">
        {loadingMore
          ? t("loading_more")
          : hasMore
            ? t("scroll_for_more")
            : t("end_of_history")}
      </div>
      <style>{`.commit-rows { --graph-width: ${graphWidth}px; }`}</style>
    </div>
  );
}