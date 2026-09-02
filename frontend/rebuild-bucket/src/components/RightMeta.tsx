/** Right metadata zone: author | date | SHA (GitHub link) | diff stat (+N -M + squares).
 *  Strict flex row with fixed gaps — no text overlap (PLAN2 fix). */
import type { CommitItem } from "../api/client";
import Avatar from "./Avatar";
import { formatRelativeTime, useI18n } from "../i18n";

interface Props {
  commit: CommitItem;
  remote: string | null;
}

export default function RightMeta({ commit, remote }: Props) {
  useI18n(); // subscribe so the date re-renders when the language switches
  const adds = commit.additions ?? 0;
  const dels = commit.deletions ?? 0;
  const shaUrl = remote ? `${remote}/commit/${commit.sha}` : null;
  return (
    <div className="commit-meta-right">
      <div className="commit-author" title={commit.author_name}>
        <Avatar name={commit.author_name} email={commit.author_email} />
        <span className="author-name">{commit.author_name}</span>
      </div>
      <span className="commit-date">{formatRelativeTime(commit.timestamp)}</span>
      <span className="commit-sha mono">
        {shaUrl ? (
          <a href={shaUrl} target="_blank" rel="noopener noreferrer">{commit.short_sha}</a>
        ) : (
          commit.short_sha
        )}
      </span>
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