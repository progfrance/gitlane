/** Typed API client + shared view models (PLAN.md section 7 contract). */

export interface RefBadge {
  type: "local_branch" | "remote_branch" | "tag";
  name: string;
}

export interface SegmentGeom {
  type: "vertical" | "curve";
  x1: number; y1: number; x2: number; y2: number;
  cx1?: number; cy1?: number; cx2?: number; cy2?: number;
  color: string;
  w: number;
}

export interface NodeGeom {
  x: number; y: number; r: number; color: string;
}

export interface CommitItem {
  sha: string;
  short_sha: string;
  message_subject: string;
  author_name: string;
  author_email: string;
  timestamp: number;
  parents: string[];
  refs: RefBadge[];
  lane_index: number;
  node: NodeGeom | null;
  segments: SegmentGeom[];
  additions: number;
  deletions: number;
  is_head: boolean;
}

export interface HistoryEnvelope {
  items: CommitItem[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
  max_lane: number;
  active_ref: string;
}

export interface RepoInfo {
  name: string;
  path: string;
  head: string;
  commit_count: number;
  remote: string | null;
}

export interface RefsResponse {
  head: string;
  head_sha: string | null;
  local_branches: { name: string; kind: string; sha: string }[];
  remote_branches: { name: string; kind: string; sha: string }[];
  tags: { name: string; kind: string; sha: string }[];
}

export interface TimelineData {
  t_min: number | null;
  t_max: number | null;
  points: { t: number; count: number; adds: number; dels: number }[];
}

export interface CommitFile {
  path: string;
  status: "added" | "modified" | "deleted" | "renamed" | "other";
  additions: number;
  deletions: number;
}

export interface CommitDetail {
  sha: string;
  short_sha: string;
  message_subject: string;
  message_body: string;
  author_name: string;
  author_email: string;
  timestamp: number;
  parents: string[];
  refs: RefBadge[];
  additions: number;
  deletions: number;
  files: CommitFile[];
  is_head: boolean;
}

/** True when `e` is a fetch abort — callers swallow it, it is not an error. */
export function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch { /* keep status */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function openRepo(path: string, signal?: AbortSignal): Promise<RepoInfo> {
  const res = await fetch("/repos/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
    signal,
  });
  const body = await jsonOrThrow<{ ok: boolean; repo: RepoInfo }>(res);
  return body.repo;
}

export async function fetchCurrentRepo(signal?: AbortSignal): Promise<RepoInfo | null> {
  const res = await fetch("/repos/current", { signal });
  if (!res.ok) return null;
  const body = await res.json();
  if (!body || !body.path) return null;
  return body as RepoInfo;
}

export async function fetchHistory(
  path: string,
  opts: { limit?: number; q?: string; cursor?: string; ref?: string } = {},
  signal?: AbortSignal,
): Promise<HistoryEnvelope> {
  const params = new URLSearchParams({ path, limit: String(opts.limit ?? 300) });
  if (opts.q) params.set("q", opts.q);
  if (opts.cursor) params.set("cursor", opts.cursor);
  if (opts.ref) params.set("ref", opts.ref);
  const res = await fetch(`/history?${params}`, { signal });
  return jsonOrThrow<HistoryEnvelope>(res);
}

export async function fetchRefs(
  path: string,
  opts: { q?: string; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<RefsResponse> {
  const params = new URLSearchParams({ path });
  if (opts.q) params.set("q", opts.q);
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  if (opts.offset !== undefined) params.set("offset", String(opts.offset));
  const res = await fetch(`/refs?${params}`, { signal });
  return jsonOrThrow<RefsResponse>(res);
}

export async function fetchTimeline(
  path: string,
  buckets = 90,
  ref?: string,
  signal?: AbortSignal,
): Promise<TimelineData> {
  const params = new URLSearchParams({ path, buckets: String(buckets) });
  if (ref) params.set("ref", ref);
  const res = await fetch(`/timeline?${params}`, { signal });
  return jsonOrThrow<TimelineData>(res);
}

export interface RecentRepo {
  path: string;
  name: string;
}

export async function fetchRecentRepos(signal?: AbortSignal): Promise<RecentRepo[]> {
  const res = await fetch("/repos/recent", { signal });
  if (!res.ok) return [];
  const body = await res.json();
  return Array.isArray(body)
    ? body.filter((r): r is RecentRepo => !!r && typeof r.path === "string")
    : [];
}

// Small in-memory cache: keyboard navigation (j/k) re-selects neighbours,
// and going back to a commit must not re-fetch what was just loaded.
const detailCache = new Map<string, CommitDetail>();

export async function fetchCommitDetail(
  path: string,
  sha: string,
  signal?: AbortSignal,
): Promise<CommitDetail> {
  const key = `${path}\n${sha}`;
  const cached = detailCache.get(key);
  if (cached) return cached;
  const params = new URLSearchParams({ path, sha });
  const res = await fetch(`/commit/detail?${params}`, { signal });
  const detail = await jsonOrThrow<CommitDetail>(res);
  if (detailCache.size > 200) detailCache.clear();
  detailCache.set(key, detail);
  return detail;
}
