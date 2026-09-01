/** Right column: relative time, short SHA, GitHub-style diff stat (+N -M + 5 squares). */
import type { CommitItem } from "../api/client";

export default function RightMeta({ commit }: { commit: CommitItem }) {
  const adds = commit.additions ?? 0;
  const dels = commit.deletions ?? 0;
  return (
    <div className="right-meta">
      <span className="rel-time">{commit.relative_time}</span>
      <span className="sha mono">{commit.short_sha}</span>
      {(adds > 0 || dels > 0) && <DiffStat adds={adds} dels={dels} />}
    </div>
  );
}

function DiffStat({ adds, dels }: { adds: number; dels: number }) {
  const total = adds + dels;
  const green = total ? Math.round((adds / total) * 5) : 0;
  const red = 5 - green;
  return (
    <span className="diff-stat">
      <span className="diff-num add">+{adds}</span>
      <span className="diff-num del">−{dels}</span>
      <span className="diff-squares">
        {Array.from({ length: green }, (_, i) => <span key={`a${i}`} className="diff-square add" />)}
        {Array.from({ length: red }, (_, i) => <span key={`d${i}`} className="diff-square del" />)}
      </span>
    </span>
  );
}
