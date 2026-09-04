/** Top header: current-repo dropdown, branch dropdown, search, refresh, language. */
import { useCallback } from "react";
import type { RepoInfo } from "../api/client";
import DropdownSelector, { type DropdownGroup } from "./DropdownSelector";
import { useI18n, type Locale } from "../i18n";

interface Props {
  repo: RepoInfo | null;
  activeRef: string;
  branches: { name: string; kind: string; sha: string }[];
  recentRepos: { path: string; name: string }[];
  query: string;
  total: number;
  isRefreshing: boolean;
  onQuery: (q: string) => void;
  onRefresh: () => void;
  onBranch: (ref: string) => void;
  onRepo: (path: string) => void;
  searchRef: React.RefObject<HTMLInputElement | null>;
}

/** Folder icon SVG */
const RepoIcon = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
    <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
  </svg>
);

/** Git branch icon SVG */
const BranchIcon = (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
    <path d="M9.5 3.25a2.25 2.25 0 1 1 3 2.122V6A2.5 2.5 0 0 1 10 8.5H6a1 1 0 0 0-1 1v1.128a2.251 2.251 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.5 0v1.836A2.493 2.493 0 0 1 6 7h4a1 1 0 0 0 1-1v-.628A2.25 2.25 0 0 1 9.5 3.25Zm-6 0a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Zm8.25-.75a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM4.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z" />
  </svg>
);

export default function TopToolbar({
  repo, activeRef, branches, recentRepos, query, total, isRefreshing,
  onQuery, onRefresh, onBranch, onRepo, searchRef,
}: Props) {
  const { t, locale, setLocale } = useI18n();

  // Build branch groups for the dropdown: local first, then remote.
  const branchGroups: DropdownGroup[] = [];
  const locals = branches.filter((b) => b.kind === "local_branch");
  const remotes = branches.filter((b) => b.kind === "remote_branch");
  if (locals.length) {
    branchGroups.push({
      label: t("local_branches"),
      items: locals.map((b) => ({ value: b.name, label: b.name })),
    });
  }
  if (remotes.length) {
    branchGroups.push({
      label: t("remote_branches"),
      items: remotes.map((b) => ({ value: b.name, label: b.name })),
    });
  }

  // Build repo groups: current repo + recent repos.
  const repoGroups: DropdownGroup[] = [];
  const reposItems: { value: string; label: string; path?: string }[] = [];
  if (repo) {
    reposItems.push({ value: repo.path, label: repo.name, path: repo.path });
  }
  for (const r of recentRepos) {
    if (repo && r.path === repo.path) continue;
    reposItems.push({ value: r.path, label: r.name, path: r.path });
  }
  if (reposItems.length) {
    repoGroups.push({ items: reposItems });
  }
  repoGroups.push({
    items: [{ value: "__picker__", label: t("browse_repo") }],
  });

  const handleRepoSelect = useCallback(
    (val: string) => {
      if (val === "__picker__") {
        window.location.href = "/picker";
        return;
      }
      onRepo(val);
    },
    [onRepo],
  );

  const displayBranch = activeRef || repo?.head || "HEAD";

  const handleSearch = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => onQuery(e.target.value),
    [onQuery],
  );
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") onQuery("");
    },
    [onQuery],
  );

  const pick = (l: Locale) => () => setLocale(l);

  return (
    <div className="top-toolbar">
      <div className="header-selectors">
        <DropdownSelector
          label={t("current_repo")}
          icon={RepoIcon}
          value={repo?.name ?? "GitLane"}
          groups={repoGroups}
          onSelect={handleRepoSelect}
        />
        <DropdownSelector
          label={t("current_branch")}
          icon={BranchIcon}
          value={displayBranch}
          groups={branchGroups}
          onSelect={onBranch}
        />
      </div>
      <button
        type="button"
        className="toolbar-btn"
        title={t("change_repo")}
        aria-label={t("change_repo")}
        onClick={() => { window.location.href = "/picker"; }}
      >
        <span aria-hidden="true" style={{ marginRight: 4 }}>{RepoIcon}</span>
        {t("repo_btn")}
      </button>
      <span className="toolbar-sep" />
      <span className="toolbar-count">
        {repo ? t("commits_count", { total }) : t("no_repo")}
      </span>
      <span className="toolbar-spacer" />
      <input
        ref={searchRef as React.RefObject<HTMLInputElement>}
        className="toolbar-search"
        type="search"
        aria-label={t("search_placeholder")}
        placeholder={t("search_placeholder")}
        value={query}
        onChange={handleSearch}
        onKeyDown={handleKeyDown}
      />
      <div className="lang-toggle" role="group" aria-label={t("language")}>
        <button
          type="button"
          className={locale === "fr" ? "active" : ""}
          onClick={pick("fr")}
          aria-pressed={locale === "fr"}
        >
          FR
        </button>
        <button
          type="button"
          className={locale === "en" ? "active" : ""}
          onClick={pick("en")}
          aria-pressed={locale === "en"}
        >
          EN
        </button>
      </div>
      <button
        className={"toolbar-btn" + (isRefreshing ? " is-refreshing" : "")}
        title={t("refresh")}
        aria-label={t("refresh")}
        onClick={onRefresh}
      >
        <span className="refresh-icon" aria-hidden="true">⟳</span>
      </button>
    </div>
  );
}