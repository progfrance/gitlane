/** GitLane app shell: toolbar + mini timeline + commit table + detail drawer. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  fetchCurrentRepo, fetchHistory, fetchRecentRepos, fetchRefs, fetchTimeline, isAbort, openRepo,
} from "../api/client";
import { useRepoEvents } from "../api/events";
import { repoStore, useStore } from "../store/useRepoStore";
import { useI18n } from "../i18n";
import TopToolbar from "../components/TopToolbar";
import MiniTimeline from "../components/MiniTimeline";
import VirtualCommitTable from "../components/VirtualCommitTable";
import CommitDetailPanel from "../components/CommitDetail";
import { graphWidth as computeGraphWidth } from "../graph/coords";

export default function App() {
  // Selective subscriptions: each slice re-renders only on its own change.
  const repo = useStore((s) => s.repo);
  const repoPath = useStore((s) => s.repoPath);
  const items = useStore((s) => s.items);
  const total = useStore((s) => s.total);
  const maxLane = useStore((s) => s.maxLane);
  const timeline = useStore((s) => s.timeline);
  const status = useStore((s) => s.status);
  const error = useStore((s) => s.error);
  const query = useStore((s) => s.query);
  const hoveredSha = useStore((s) => s.hoveredSha);
  const selectedSha = useStore((s) => s.selectedSha);
  const lastFetchMs = useStore((s) => s.lastFetchMs);
  const activeRef = useStore((s) => s.activeRef);
  const branches = useStore((s) => s.branches);
  const recentRepos = useStore((s) => s.recentRepos);
  const remote = repo?.remote ?? null;

  const { t } = useI18n();
  const [pathInput, setPathInput] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<number | undefined>(undefined);
  const loadSeq = useRef(0); // stale-response guard: only the latest load writes
  const abortRef = useRef<AbortController | null>(null);
  // Set when WS events arrive while the tab is hidden; the focus handler
  // reloads only in that case instead of re-reading git on every alt-tab.
  const staleWhileHidden = useRef(false);

  // Cancel in-flight fetches before starting a new load (branch/search/
  // repo switches, WS events): a superseded response never writes.
  const cancelInflight = useCallback(() => {
    loadSeq.current += 1;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    return { seq: loadSeq.current, signal: ctrl.signal };
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  const load = useCallback(async (path: string, q: string, reopen = true, ref?: string) => {
    const { seq, signal } = cancelInflight();
    const t0 = performance.now();
    const prev = repoStore.get();
    repoStore.set({ status: prev.repoPath === path ? prev.status : "loading", error: null, repoPath: path });
    try {
      let repoPath = path;
      let repo = repoStore.get().repo;
      if (reopen || !repo) {
        // Full reopen re-reads git data and refreshes the server cache.
        repo = await openRepo(path, signal);
        repoPath = repo.path;
      }
      const [history, tl] = await Promise.all([
        fetchHistory(repoPath, { limit: 300, q, ref }, signal),
        fetchTimeline(repoPath, 90, ref, signal),
      ]);
      if (seq !== loadSeq.current || signal.aborted) return; // superseded
      repoStore.set({
        repo,
        repoPath,
        items: history.items,
        total: history.total,
        maxLane: history.max_lane,
        timeline: tl,
        status: "ready",
        lastFetchMs: Math.round(performance.now() - t0),
        nextCursor: history.next_cursor,
        hasMore: history.has_more,
        loadingMore: false,
        activeRef: history.active_ref,
      });
    } catch (e) {
      if (isAbort(e) || signal.aborted || seq !== loadSeq.current) return;
      repoStore.set({ status: "error", error: e instanceof Error ? e.message : String(e), loadingMore: false });
    }
  }, [cancelInflight]);

  // Refresh the branch list + recent repos for the header selectors.
  const refreshMeta = useCallback(async (path: string | null, signal?: AbortSignal) => {
    if (!path) return;
    try {
      const [refs, recents] = await Promise.all([fetchRefs(path, {}, signal), fetchRecentRepos(signal)]);
      const cur = repoStore.get();
      if (cur.repoPath !== path || signal?.aborted) return; // repo changed
      repoStore.set({
        branches: [...refs.local_branches, ...refs.remote_branches],
        recentRepos: recents,
      });
    } catch (e) {
      if (!isAbort(e)) throw e;
    }
  }, []);

  const resetScrollTop = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = 0;
  }, []);

  // Load the next page of history (infinite scroll).
  const loadMore = useCallback(async () => {
    const cur = repoStore.get();
    if (!cur.repoPath || !cur.nextCursor || !cur.hasMore || cur.loadingMore) return;
    const seq = loadSeq.current;
    repoStore.set({ loadingMore: true });
    try {
      const history = await fetchHistory(cur.repoPath, {
        limit: 300,
        q: cur.query,
        cursor: cur.nextCursor,
        ref: cur.activeRef === "HEAD" ? undefined : cur.activeRef,
      }, abortRef.current?.signal);
      if (seq !== loadSeq.current) return; // a full reload superseded this pagination
      const fresh = repoStore.get();
      repoStore.set({
        items: [...fresh.items, ...history.items],
        nextCursor: history.next_cursor,
        hasMore: history.has_more,
        loadingMore: false,
      });
    } catch (e) {
      if (!isAbort(e)) repoStore.set({ loadingMore: false });
    }
  }, []);

  const onHover = useCallback((sha: string | null) => {
    if (repoStore.get().hoveredSha !== sha) repoStore.set({ hoveredSha: sha });
  }, []);

  const onSelect = useCallback((sha: string) => {
    repoStore.set({ selectedSha: sha });
  }, []);

  const onQuery = useCallback((q: string) => {
    repoStore.set({ query: q });
  }, []);

  const onRefresh = useCallback(() => {
    const cur = repoStore.get();
    if (cur.repoPath) void load(cur.repoPath, cur.query, false, cur.activeRef === "HEAD" ? undefined : cur.activeRef);
    void refreshMeta(cur.repoPath, abortRef.current?.signal ?? undefined);
  }, [load, refreshMeta]);

  // Initial load: prefer the repo already open server-side (picker / last
  // session). When nothing is open anywhere, go to /picker instead of
  // guessing a machine-specific default path.
  useEffect(() => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    (async () => {
      const current = await fetchCurrentRepo(ctrl.signal).catch((e) => {
        if (!isAbort(e)) throw e;
        return null;
      });
      if (ctrl.signal.aborted) return;
      if (!current?.path) {
        window.location.href = "/picker";
        return;
      }
      await Promise.all([load(current.path, ""), refreshMeta(current.path)]);
    })();
    return () => ctrl.abort();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced search (100-150 ms per plan §11) — keep the active ref.
  useEffect(() => {
    if (!repoPath) return;
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      const cur = repoStore.get();
      if (cur.repoPath) void load(cur.repoPath, cur.query, false, cur.activeRef === "HEAD" ? undefined : cur.activeRef);
    }, 130);
    return () => window.clearTimeout(debounceRef.current);
  }, [query, repoPath, load]);

  // Branch switch from the header selector.
  const handleBranch = useCallback((ref: string) => {
    const cur = repoStore.get();
    repoStore.set({ activeRef: ref, items: [], nextCursor: null, hasMore: false, query: "", selectedSha: null });
    

    resetScrollTop();
    if (cur.repoPath) void load(cur.repoPath, "", false, ref);
  }, [load, resetScrollTop]);

  // Repo switch from the header selector.
  const handleRepo = useCallback((path: string) => {
    repoStore.set({ activeRef: "HEAD", query: "", selectedSha: null });
    resetScrollTop();
    void load(path, "", true);
    void refreshMeta(path);
  }, [load, refreshMeta, resetScrollTop]);

  // Keyboard shortcuts: Ctrl+O picker, "/" search, Escape clears, j/k moves.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const typing = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "o" && !typing) {
        e.preventDefault();
        window.location.href = "/picker";
        return;
      }
      if (e.key === "/" && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (e.key === "Escape" && typing) {
        (target as HTMLInputElement).blur();
        repoStore.set({ query: "" });
      } else if ((e.key === "j" || e.key === "k") && !typing) {
        e.preventDefault();
        const cur = repoStore.get();
        if (!cur.items.length) return;
        const idx = cur.items.findIndex((c) => c.sha === cur.selectedSha);
        const next = e.key === "j" ? Math.min(cur.items.length - 1, idx + 1) : Math.max(0, idx - 1);
        const sha = cur.items[idx === -1 ? 0 : next].sha;
        repoStore.set({ selectedSha: sha });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Reload on window focus ONLY when WS events arrived while hidden.
  useEffect(() => {
    const onFocus = () => {
      if (!staleWhileHidden.current) return;
      staleWhileHidden.current = false;
      const cur = repoStore.get();
      if (cur.repoPath) void load(cur.repoPath, cur.query, false, cur.activeRef === "HEAD" ? undefined : cur.activeRef);
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  // Live updates: websocket events from the .git watcher.
  const repoPathForWs = repoPath != null;
  useRepoEvents((ev) => {
    const cur = repoStore.get();
    if (!cur.repoPath) return;
    if (ev.path && ev.path !== cur.repoPath) return;
    if (ev.type === "repo_updated" || ev.type === "new_commit" || ev.type === "head_changed") {
      if (document.hidden) {
        staleWhileHidden.current = true;
        return;
      }
      staleWhileHidden.current = false;
      void load(cur.repoPath, cur.query, false, cur.activeRef === "HEAD" ? undefined : cur.activeRef);
      void refreshMeta(cur.repoPath);
    }
  }, repoPathForWs);

  const gw = useMemo(() => computeGraphWidth(maxLane), [maxLane]);
  const hasMore = useStore((s) => s.hasMore);
  const loadingMore = useStore((s) => s.loadingMore);

  return (
    <div className="app-shell">
      <TopToolbar
        repo={repo}
        activeRef={activeRef}
        branches={branches}
        recentRepos={recentRepos}
        query={query}
        total={total}
        onQuery={onQuery}
        onRefresh={onRefresh}
        onBranch={handleBranch}
        onRepo={handleRepo}
        searchRef={searchRef}
      />
      <MiniTimeline data={timeline} />
      <div className="main-area">
        <div className="commit-panel">
          {status === "loading" && !items.length && (
            <div className="state-block"><div className="spinner" /><span>{t("loading_repo")}</span></div>
          )}
          {status === "error" && (
            <div className="state-block error">
              <span className="state-title">{t("failed_open")}</span>
              <span>{error}</span>
              <div className="repo-picker">
                <input value={pathInput} onChange={(e) => setPathInput(e.target.value)} placeholder={t("manual_ph")} aria-label={t("manual_ph")} />
                <button className="toolbar-btn" onClick={() => void load(pathInput, query)}>{t("open")}</button>
                <button className="toolbar-btn" onClick={() => { window.location.href = "/picker"; }}>{t("browse_repo")}</button>
              </div>
            </div>
          )}
          {status !== "error" && items.length === 0 && status !== "loading" && (
            <div className="state-block">
              <span className="state-title">{t("no_commits")}</span>
              <span>{query ? t("no_result", { query }) : t("no_commits_on", { ref: activeRef })}</span>
            </div>
          )}
          {items.length > 0 && (
            <VirtualCommitTable
              scrollRef={scrollRef}
              items={items}
              graphWidth={gw}
              remote={remote}
              hoveredSha={hoveredSha}
              selectedSha={selectedSha}
              query={query}
              hasMore={hasMore}
              loadingMore={loadingMore}
              onLoadMore={() => void loadMore()}
              onHover={onHover}
              onSelect={onSelect}
            />
          )}
        </div>
        {lastFetchMs != null && (
          <div style={{ textAlign: "right", fontSize: 10.5, color: "var(--text-muted)", padding: "6px 2px 0" }}>
            {t("rows_loaded", { n: items.length, ms: lastFetchMs })}
          </div>
        )}
      </div>
      <CommitDetailPanel
        repoPath={repoPath}
        sha={selectedSha}
        onClose={() => repoStore.set({ selectedSha: null })}
      />
    </div>
  );
}
