/** Tiny observable store (React-friendly via useSyncExternalStore).
 *
 * `useStore(selector)` subscribes to a slice only: a hover change
 * re-renders the two rows involved, not the whole app. Selectors must
 * return stable references for unchanged slices (primitives or the same
 * object identity) to avoid extra renders.
 */
import { useSyncExternalStore } from "react";

export interface RepoState {
  repoPath: string | null;
  repo: { name: string; path: string; head: string; commit_count: number; remote: string | null } | null;
  items: import("../api/client").CommitItem[];
  total: number;
  /** Of `total`: actual search hits (the rest are parent-context rows). */
  matchedTotal: number;
  maxLane: number;
  timeline: import("../api/client").TimelineData | null;
  status: "idle" | "loading" | "ready" | "error";
  error: string | null;
  query: string;
  hoveredSha: string | null;
  selectedSha: string | null;
  lastFetchMs: number | null;
  nextCursor: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  activeRef: string;
  branches: { name: string; kind: string; sha: string }[];
  recentRepos: { path: string; name: string }[];
}

type Listener = () => void;

let state: RepoState = {
  repoPath: null,
  repo: null,
  items: [],
  total: 0,
  matchedTotal: 0,
  maxLane: 0,
  timeline: null,
  status: "idle",
  error: null,
  query: "",
  hoveredSha: null,
  selectedSha: null,
  lastFetchMs: null,
  nextCursor: null,
  hasMore: false,
  loadingMore: false,
  activeRef: "HEAD",
  branches: [],
  recentRepos: [],
};

const listeners = new Set<Listener>();

export const repoStore = {
  get(): RepoState {
    return state;
  },
  set(patch: Partial<RepoState>) {
    state = { ...state, ...patch };
    listeners.forEach((l) => l());
  },
  subscribe(l: Listener): () => void {
    listeners.add(l);
    return () => listeners.delete(l);
  },
};

/** Subscribe to a slice of the store — re-renders only when it changes. */
export function useStore<T>(selector: (s: RepoState) => T): T {
  return useSyncExternalStore(
    repoStore.subscribe,
    () => selector(repoStore.get()),
    () => selector(repoStore.get()),
  );
}
