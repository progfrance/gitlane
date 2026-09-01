/** Right column: relative time, short SHA, status dots (PLAN.md 4.6). */
import type { CommitItem } from "../api/client";

export default function RightMeta({ commit }: { commit: CommitItem }) {
  return (
    <div className="right-meta">
      <span className="rel-time">{commit.relative_time}</span>
      <span className="sha mono">{commit.short_sha}</span>
      <StatusDots checks={commit.status_checks} />
    </div>
  );
}

function StatusDots({ checks }: { checks: string[] }) {
  if (!checks.length) return null;
  return (
    <span className="status-dots" title={checks.join(", ")}>
      {checks.slice(0, 5).map((c, i) => (
        <span key={i} className={`status-dot ${c}`} />
      ))}
    </span>
  );
}
