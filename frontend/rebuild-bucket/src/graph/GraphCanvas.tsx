/** Per-row lane graph canvas.
 *  The canvas measures its own cell (CSS --graph-width sets the width), so
 *  rows stay referentially stable when maxLane changes — no width prop. */
import { memo, useEffect, useRef } from "react";
import type { CommitItem } from "../api/client";
import { ROW_HEIGHT } from "./coords";
import { drawCommitGraph } from "./draw";

interface Props {
  commit: CommitItem;
  hovered: boolean;
  selected: boolean;
}

function GraphCanvasInner({ commit, hovered, selected }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const w = canvas.parentElement?.clientWidth || canvas.clientWidth || 180;
    drawCommitGraph(canvas, commit, w, ROW_HEIGHT, { hovered, selected });
  }, [commit, hovered, selected]);

  return (
    <div className="commit-graph-cell" aria-hidden="true">
      <canvas ref={ref} />
    </div>
  );
}

const GraphCanvas = memo(GraphCanvasInner);
export default GraphCanvas;
