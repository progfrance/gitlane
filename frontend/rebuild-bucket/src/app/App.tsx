/** GitLane app shell: toolbar + mini timeline + commit table (PLAN sections 2 & 4). */
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import {
  fetchCurrentRepo, fetchHistory, fetchRecentRepos, fetchRefs, fetchTimeline, openRepo,
  type CommitItem,
} from "../api/client";
import { useRepoEvents } from "../api/events";
import { repoStore } from "../store/useRepoStore";
import { useI18n } from "../i18n";
import TopToolbar from "../components/TopToolbar";
import MiniTimeline from "../components/MiniTimeline";
import VirtualCommitTable from "../components/VirtualCommitTable";
import { graphWidth as computeGraphWidth } from "../graph/coords";

function useStore() {
  return useSyncExternalStore(repoStore.subscribe, repoStore.get);
}

export default function App() {
  const s = useStore();
  const { t } = useI18n();
  const [pathInput, setPathInput] = useState("");
  const [scroll, setScroll] = useState({ top: 0, height: 1, client: 1 });
  const searchRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<number | undefined>(undefined);
  const loadSeq = useRef(0); // stale-response guard: only the latest load writes
  // Set when WS events arrive while the tab is hidden; the focus handler
  // reloads only in that case instead of re-reading git on every alt-tab.
  const staleWhileHidden = useRef(false);

  const load = useCallback(async (path: string, q: string, reopen = true, ref?: string) => {
    const seq = ++loadSeq.current;
    const t0 = performance.now();
    repoStore.set({ status: s.repoPath === path ? s.status : "loading", error: null, repoPath: path });
    try {
      let repoPath = path;
      let repo = repoStore.get().repo;
      if (reopen || !repo) {
        // Full reopen re-reads git data and refreshes the server cache.
        repo = await openRepo(path);
        repoPath = repo.path;
      }
      const [history, timeline] = await Promise.all([
        fetchHistory(repoPath, { limit: 300, q, ref }),
        fetchTimeline(repoPath, 90, ref),
      ]);
      if (seq !== loadSeq.current) return; // a newer load superseded this one
      repoStore.set({
        repo,
        repoPath,
        items: history.items,
        total: history.total,
        maxLane: history.max_lane,
        timeline,
        status: "ready",
        lastFetchMs: Math.round(performance.now() - t0),
        nextCursor: history.next_cursor,
        hasMore: history.has_more,
        loadingMore: false,
        activeRef: history.active_ref,
      });
    } catch (e) {
      if (seq !== loadSeq.current) return;
      repoStore.set({ status: "error", error: e instanceof Error ? e.message : String(e), loadingMore: false });
    }
  }, [s.repoPath]);

  // Refresh the branch list + recent repos for the header selectors.
  const refreshMeta = useCallback(async (path: string | null) => {
    if (!path) return;
    const [refs, recents] = await Promise.all([fetchRefs(path), fetchRecentRepos()]);
    const cur = repoStore.get();
    if (cur.repoPath !== path) return; // repo changed while fetching
    repoStore.set({
      branches: [...refs.local_branches, ...refs.remote_branches],
      recentRepos: recents,
    });
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
      });
      if (seq !== loadSeq.current) return; // a full reload superseded this pagination
      repoStore.set({
        items: [...cur.items, ...history.items],
        nextCursor: history.next_cursor,
        hasMore: history.has_more,
        loadingMore: false,
      });
    } catch {
      repoStore.set({ loadingMore: false });
    }
  }, []);

  // Initial load: prefer the repo already open server-side (picker / last
  // session). When nothing is open anywhere, go to /picker instead of
  // guessing a machine-specific default path.
  useEffect(() => {
    (async () => {
      const current = await fetchCurrentRepo().catch(() => null);
      if (!current?.path) {
        window.location.href = "/picker";
        return;
      }
      await Promise.all([load(current.path, ""), refreshMeta(current.path)]);
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced search (100-150 ms per plan §11) — keep the active ref.
  useEffect(() => {
    if (!s.repoPath) return;
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      const cur = repoStore.get();
      void load(cur.repoPath!, cur.query, false, cur.activeRef === "HEAD" ? undefined : cur.activeRef);
    }, 130);
    return () => window.clearTimeout(debounceRef.current);
  }, [s.query]); // eslint-disable-line react-hooks/exhaustive-deps

  // Branch switch from the header selector.
  const handleBranch = useCallback((ref: string) => {
    const cur = repoStore.get();
    repoStore.set({ activeRef: ref, items: [], nextCursor: null, hasMore: false, query: "" });
    resetScrollTop();
    void load(cur.repoPath!, "", false, ref);
  }, [load, resetScrollTop]);

  // Repo switch from the header selector.
  const handleRepo = useCallback((path: string) => {
    repoStore.set({ activeRef: "HEAD", query: "" });
    resetScrollTop();
    void load(path, "", true);
    void refreshMeta(path);
  }, [load, refreshMeta, resetScrollTop]);

  // Keyboard shortcuts (plan §10.1).
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
        const items = repoStore.get().items;
        if (!items.length) return;
        const idx = items.findIndex((c) => c.sha === repoStore.get().selectedSha);
        const next = e.key === "j" ? Math.min(items.length - 1, idx + 1) : Math.max(0, idx - 1);
        const sha = items[idx === -1 ? 0 : next].sha;
        repoStore.set({ selectedSha: sha });
        document.querySelector<HTMLElement>(`.commit-row.selected`)?.scrollIntoView({ block: "nearest" });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Reload on window focus ONLY when WS events arrived while hidden — the
  // websocket already covers the visible case, so unconditional reloads
  // just re-read git on every alt-tab for nothing.
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

  // Live updates: websocket events from the .git watcher (plan §10.5).
  // Events received while the tab is hidden only mark state stale; the
  // focus handler above performs the single catch-up reload.
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
  }, s.repoPath != null);

  const gw = useMemo(() => computeGraphWidth(s.maxLane), [s.maxLane]);
  const items: CommitItem[] = s.items;

  return (
    <div className="app-shell">
      <TopToolbar
        repo={s.repo}
        activeRef={s.activeRef}
        branches={s.branches}
        recentRepos={s.recentRepos}
        query={s.query}
        total={s.total}
        onQuery={(q) => repoStore.set({ query: q })}
        onRefresh={() => {
          const cur = repoStore.get();
          if (cur.repoPath) void load(cur.repoPath, cur.query, false, cur.activeRef === "HEAD" ? undefined : cur.activeRef);
          void refreshMeta(cur.repoPath);
        }}
        onBranch={handleBranch}
        onRepo={handleRepo}
        searchRef={searchRef}
      />
      <MiniTimeline
        data={s.timeline}
        scrollTop={scroll.top}
        scrollHeight={scroll.height}
        clientHeight={scroll.client}
      />
      <div className="main-area">
        <div className="commit-panel">
          {s.status === "loading" && !items.length && (
            <div className="state-block"><div className="spinner" /><span>{t("loading_repo")}</span></div>
          )}
          {s.status === "error" && (
            <div className="state-block error">
              <span className="state-title">{t("failed_open")}</span>
              <span>{s.error}</span>
              <div className="repo-picker">
                <input value={pathInput} onChange={(e) => setPathInput(e.target.value)} placeholder={t("manual_ph")} />
                <button className="toolbar-btn" onClick={() => void load(pathInput, s.query)}>{t("open")}</button>
                <button className="toolbar-btn" onClick={() => { window.location.href = "/picker"; }}>{t("browse_repo")}</button>
              </div>
            </div>
          )}
          {s.status !== "error" && items.length === 0 && s.status !== "loading" && (
            <div className="state-block">
              <span className="state-title">{t("no_commits")}</span>
              <span>{s.query ? t("no_result", { query: s.query }) : t("no_commits_on", { ref: s.activeRef })}</span>
            </div>
          )}
          {items.length > 0 && (
            <VirtualCommitTable
              scrollRef={scrollRef}
              items={items}
              graphWidth={gw}
              remote={s.repo?.remote ?? null}
              hoveredSha={s.hoveredSha}
              selectedSha={s.selectedSha}
              query={s.query}
              hasMore={s.hasMore}
              loadingMore={s.loadingMore}
              onLoadMore={() => void loadMore()}
              onHover={(sha) => repoStore.set({ hoveredSha: sha })}
              onSelect={(sha) => repoStore.set({ selectedSha: sha })}
              onScroll={(e) => {
                const el = e.currentTarget;
                setScroll({ top: el.scrollTop, height: el.scrollHeight, client: el.clientHeight });
              }}
            />
          )}
        </div>
        {s.lastFetchMs != null && (
          <div style={{ textAlign: "right", fontSize: 10.5, color: "var(--text-muted)", padding: "6px 2px 0" }}>
            {t("rows_loaded", { n: items.length, ms: s.lastFetchMs })}
          </div>
        )}
      </div>
    </div>
  );
}
