/** GitLane app shell: toolbar + mini timeline + commit table (PLAN sections 2 & 4). */
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { fetchHistory, fetchTimeline, openRepo, type CommitItem, type RepoInfo } from "../api/client";
import { repoStore } from "../store/useRepoStore";
import TopToolbar from "../components/TopToolbar";
import MiniTimeline from "../components/MiniTimeline";
import CommitTable from "../components/CommitTable";
import { graphWidth as computeGraphWidth } from "../graph/coords";

const DEFAULT_REPO = "C:/Users/Dell/Desktop/MesProjets/gitlane/gitlane";

function useStore() {
  return useSyncExternalStore(repoStore.subscribe, repoStore.get);
}

export default function App() {
  const s = useStore();
  const [pathInput, setPathInput] = useState(DEFAULT_REPO);
  const [scroll, setScroll] = useState({ top: 0, height: 1, client: 1 });
  const searchRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<number | undefined>(undefined);

  const load = useCallback(async (path: string, q: string) => {
    const t0 = performance.now();
    repoStore.set({ status: s.repoPath === path ? s.status : "loading", error: null, repoPath: path });
    try {
      const repo: RepoInfo = await openRepo(path);
      const [history, timeline] = await Promise.all([
        fetchHistory(path, { limit: 300, q }),
        fetchTimeline(path),
      ]);
      repoStore.set({
        repo,
        items: history.items,
        total: history.total,
        maxLane: history.max_lane,
        timeline,
        status: "ready",
        lastFetchMs: Math.round(performance.now() - t0),
      });
    } catch (e) {
      repoStore.set({ status: "error", error: e instanceof Error ? e.message : String(e) });
    }
  }, [s.repoPath]);

  // Initial load.
  useEffect(() => { void load(DEFAULT_REPO, ""); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced search (100-150 ms per plan §11).
  useEffect(() => {
    if (!s.repoPath) return;
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      void load(s.repoPath!, s.query);
    }, 130);
    return () => window.clearTimeout(debounceRef.current);
  }, [s.query]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keyboard shortcuts (plan §10.1).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const typing = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
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

  // Auto-refresh on window focus (light-weight v1; websocket lands in Phase D).
  useEffect(() => {
    const onFocus = () => { if (s.repoPath) void load(s.repoPath, s.query); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [s.repoPath, s.query, load]);

  const gw = useMemo(() => computeGraphWidth(s.maxLane), [s.maxLane]);
  const items: CommitItem[] = s.items;

  return (
    <div className="app-shell">
      <TopToolbar
        repo={s.repo}
        query={s.query}
        total={s.total}
        onQuery={(q) => repoStore.set({ query: q })}
        onRefresh={() => s.repoPath && void load(s.repoPath, s.query)}
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
            <div className="state-block"><div className="spinner" /><span>Loading repository…</span></div>
          )}
          {s.status === "error" && (
            <div className="state-block error">
              <span className="state-title">Failed to open repository</span>
              <span>{s.error}</span>
              <div className="repo-picker">
                <input value={pathInput} onChange={(e) => setPathInput(e.target.value)} />
                <button className="toolbar-btn" onClick={() => void load(pathInput, s.query)}>Open</button>
              </div>
            </div>
          )}
          {s.status !== "error" && items.length === 0 && s.status !== "loading" && (
            <div className="state-block">
              <span className="state-title">No commits</span>
              <span>{s.query ? `No result for “${s.query}”` : "This repository has no commits on HEAD"}</span>
            </div>
          )}
          {items.length > 0 && (
            <CommitTable
              ref={scrollRef}
              items={items}
              graphWidth={gw}
              hoveredSha={s.hoveredSha}
              selectedSha={s.selectedSha}
              query={s.query}
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
            {items.length} rows · loaded in {s.lastFetchMs} ms
          </div>
        )}
      </div>
    </div>
  );
}
