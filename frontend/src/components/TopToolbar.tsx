/** Top toolbar: repo identity, branch pill, search, refresh (PLAN 4.1). */
import type { RepoInfo } from "../api/client";

interface Props {
  repo: RepoInfo | null;
  query: string;
  total: number;
  onQuery: (q: string) => void;
  onRefresh: () => void;
  searchRef: React.RefObject<HTMLInputElement>;
}

export default function TopToolbar({ repo, query, total, onQuery, onRefresh, searchRef }: Props) {
  return (
    <div className="top-toolbar">
      <span className="toolbar-repo">
        <span className="repo-icon" aria-hidden>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
            <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
          </svg>
        </span>
        {repo ? repo.name : "GitLane"}
      </span>
      {repo && (
        <span className="toolbar-branch-pill">
          <span className="dot" />
          {repo.head}
        </span>
      )}
      <span className="toolbar-sep" />
      <span className="toolbar-count">
        {repo ? `${total} commits` : "no repo"}
      </span>
      <span className="toolbar-spacer" />
      <input
        ref={searchRef}
        className="toolbar-search"
        type="search"
        placeholder="Search commit, sha, author…  ( / )"
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape") onQuery(""); }}
      />
      <button className="toolbar-btn" title="Refresh" onClick={onRefresh}>⟳</button>
    </div>
  );
}
