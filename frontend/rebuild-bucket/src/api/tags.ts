/** Client for the cross-repo tag search endpoint. */

export interface TagHit {
  repo_name: string;
  repo_path: string;
  tag_name: string;
  sha: string;
  age_seconds: number;
}

export interface TagsFindResponse {
  root: string;
  tag: string;
  scanned: number;
  truncated: boolean;
  items: TagHit[];
  missing: string[];
}

export async function fetchTagHits(
  root: string,
  tag: string,
  depth = 2,
  signal?: AbortSignal,
): Promise<TagsFindResponse> {
  const params = new URLSearchParams({ root, tag, depth: String(depth) });
  const res = await fetch(`/tags/find?${params}`, { signal });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch { /* keep status */ }
    throw new Error(detail);
  }
  return res.json() as Promise<TagsFindResponse>;
}