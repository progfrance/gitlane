/** Tiny observable store (React-friendly via useSyncExternalStore). */

export interface RepoState {
  repoPath: string | null;
  repo: { name: string; path: string; head: string; commit_count: number } | null;
  items: import("../api/client").CommitItem[];
  total: number;
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
}

type Listener = () => void;

let state: RepoState = {
  repoPath: null,
  repo: null,
  items: [],
  total: 0,
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
