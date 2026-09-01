/** Per-row lane graph canvas. */
import { useEffect, useRef } from "react";
import type { CommitItem } from "../api/client";
import { ROW_HEIGHT } from "./coords";
import { drawCommitGraph } from "./draw";

interface Props {
  commit: CommitItem;
  width: number;
  hovered: boolean;
  selected: boolean;
}

export default function GraphCanvas({ commit, width, hovered, selected }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (ref.current) {
      drawCommitGraph(ref.current, commit, width, ROW_HEIGHT, { hovered, selected });
    }
  }, [commit, width, hovered, selected]);

  return (
    <div className="commit-graph-cell">
      <canvas ref={ref} />
    </div>
  );
}
