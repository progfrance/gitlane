/** Typed API client + shared view models (PLAN.md section 7 contract). */

export interface RefBadge {
  type: "local_branch" | "remote_branch" | "tag" | "head";
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
  author_avatar_url: string | null;
  timestamp: number;
  relative_time: string;
  parents: string[];
  refs: RefBadge[];
  lane_index: number;
  node: NodeGeom | null;
  segments: SegmentGeom[];
  status_checks: string[];
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
}

export interface RepoInfo {
  name: string;
  path: string;
  head: string;
  commit_count: number;
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

export async function openRepo(path: string): Promise<RepoInfo> {
  const res = await fetch("/repos/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  const body = await jsonOrThrow<{ ok: boolean; repo: RepoInfo }>(res);
  return body.repo;
}

export async function fetchCurrentRepo(): Promise<RepoInfo | null> {
  const res = await fetch("/repos/current");
  if (!res.ok) return null;
  const body = await res.json();
  if (!body || !body.path) return null;
  return body as RepoInfo;
}

export async function fetchHistory(
  path: string,
  opts: { limit?: number; q?: string; cursor?: string } = {}
): Promise<HistoryEnvelope> {
  const params = new URLSearchParams({ path, limit: String(opts.limit ?? 300) });
  if (opts.q) params.set("q", opts.q);
  if (opts.cursor) params.set("cursor", opts.cursor);
  const res = await fetch(`/history?${params}`);
  return jsonOrThrow<HistoryEnvelope>(res);
}

export async function fetchRefs(path: string): Promise<RefsResponse> {
  const res = await fetch(`/refs?path=${encodeURIComponent(path)}`);
  return jsonOrThrow<RefsResponse>(res);
}

export async function fetchTimeline(path: string, buckets = 90): Promise<TimelineData> {
  const res = await fetch(`/timeline?path=${encodeURIComponent(path)}&buckets=${buckets}`);
  return jsonOrThrow<TimelineData>(res);
}
