/** URL ↔ store sync via the hash fragment.
 *
 * Format: `#/r/<base64url(path)>/b/<base64url(ref)>`.
 * The hash (not the path) is used so the static `index.html` (served by
 * the backend) does not need any rewrites, and deep links survive F5.
 *
 * `path` is base64url-encoded because Windows paths contain `:` and `\`
 * which conflict with the slash separator.
 */
import { repoStore } from "./useRepoStore";

let suppressWrite = false;

function encode(s: string): string {
  return btoa(unescape(encodeURIComponent(s)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function decode(s: string): string | null {
  try {
    const pad = s.length % 4 ? 4 - (s.length % 4) : 0;
    const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat(pad);
    return decodeURIComponent(escape(atob(b64)));
  } catch {
    return null;
  }
}

export interface HashState {
  path: string | null;
  ref: string | null;
}

export function readHash(): HashState {
  const h = window.location.hash.replace(/^#/, "");
  if (!h.startsWith("/r/")) return { path: null, ref: null };
  const rest = h.slice(3);
  const sep = rest.indexOf("/b/");
  if (sep < 0) {
    return { path: decode(rest), ref: null };
  }
  return {
    path: decode(rest.slice(0, sep)),
    ref: decode(rest.slice(sep + 3)),
  };
}

export function writeHash(state: { path: string | null; ref: string | null }): void {
  if (suppressWrite) return;
  if (!state.path) {
    if (window.location.hash) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    return;
  }
  const next =
    "#/r/" +
    encode(state.path) +
    (state.ref && state.ref !== "HEAD" ? "/b/" + encode(state.ref) : "");
  if (next !== window.location.hash) {
    history.replaceState(null, "", next);
  }
}

export function startUrlSync(): () => void {
  // Write initial hash from current store state.
  const cur = repoStore.get();
  if (cur.repoPath) {
    suppressWrite = true;
    writeHash({ path: cur.repoPath, ref: cur.activeRef });
    suppressWrite = false;
  }

  // Mirror store changes → hash.
  const offStore = repoStore.subscribe(() => {
    const c = repoStore.get();
    writeHash({ path: c.repoPath, ref: c.activeRef });
  });

  // Mirror hash changes (back/forward) → store.
  const onHash = () => {
    const h = readHash();
    if (!h.path) return;
    suppressWrite = true;
    const c = repoStore.get();
    if (h.path !== c.repoPath) {
      repoStore.set({ repoPath: h.path });
    }
    if (h.ref && h.ref !== c.activeRef) {
      repoStore.set({ activeRef: h.ref });
    }
    suppressWrite = false;
  };
  window.addEventListener("hashchange", onHash);

  return () => {
    offStore();
    window.removeEventListener("hashchange", onHash);
  };
}
