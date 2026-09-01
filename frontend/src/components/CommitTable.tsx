/** Commit table: dense rows inside a scroller (virtualized in Phase D). */
import { forwardRef } from "react";
import type { CommitItem } from "../api/client";
import CommitRow from "./CommitRow";
import { ROW_HEIGHT } from "../graph/coords";

interface Props {
  items: CommitItem[];
  graphWidth: number;
  hoveredSha: string | null;
  selectedSha: string | null;
  query: string;
  onHover: (sha: string | null) => void;
  onSelect: (sha: string) => void;
  onScroll: (e: React.UIEvent<HTMLDivElement>) => void;
}

const CommitTable = forwardRef<HTMLDivElement, Props>(function CommitTable(
  { items, graphWidth, hoveredSha, selectedSha, query, onHover, onSelect, onScroll },
  ref
) {
  return (
    <div className="commit-scroll" ref={ref} onScroll={onScroll}>
      <div className="commit-rows">
        {items.map((c, i) => (
          <CommitRow
            key={c.sha}
            commit={c}
            index={i}
            graphWidth={graphWidth}
            hovered={hoveredSha === c.sha}
            selected={selectedSha === c.sha}
            query={query}
            onHover={onHover}
            onSelect={onSelect}
          />
        ))}
      </div>
      <style>{`.commit-rows { --graph-width: ${graphWidth}px; }`}</style>
    </div>
  );
});

export { ROW_HEIGHT };
export default CommitTable;
