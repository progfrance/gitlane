/** One dense commit row: graph lane | content (pills + message) | right meta.
 *  Pills are inline-flex BEFORE the message — single line, no overlap (PLAN2 fix). */
import type { CommitItem } from "../api/client";
import GraphCanvas from "../graph/GraphCanvas";
import RefsPills from "./RefsPills";
import RightMeta from "./RightMeta";
import { hexToRgba } from "../graph/coords";

interface Props {
  commit: CommitItem;
  index: number;
  graphWidth: number;
  remote: string | null;
  hovered: boolean;
  selected: boolean;
  query: string;
  onHover: (sha: string | null) => void;
  onSelect: (sha: string) => void;
}

function highlight(text: string, q: string) {
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark>{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

export default function CommitRow({
  commit, index, graphWidth, remote, hovered, selected, query, onHover, onSelect,
}: Props) {
  const hit = query.length > 0 && commit.message_subject.toLowerCase().includes(query.toLowerCase());
  const laneTint = commit.node ? hexToRgba(commit.node.color, 0.12) : undefined;
  return (
    <div
      className={[
        "commit-row",
        index % 2 === 0 ? "even" : "",
        hovered ? "hover" : "",
        selected ? "selected" : "",
        hit ? "commit-search-hit" : "",
      ].join(" ")}
      style={laneTint ? ({ backgroundColor: laneTint } as React.CSSProperties) : undefined}
      onMouseEnter={() => onHover(commit.sha)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onSelect(commit.sha)}
    >
      <GraphCanvas commit={commit} width={graphWidth} hovered={hovered} selected={selected} />
      <div className="commit-content">
        <RefsPills refs={commit.refs} />
        <span className="commit-message">
          <span className="msg-text">{highlight(commit.message_subject, query)}</span>
        </span>
      </div>
      <RightMeta commit={commit} remote={remote} />
    </div>
  );
}