/** WebSocket client: listens for repo change events and triggers refresh. */
import { useEffect, useRef } from "react";

export type RepoEvent =
  | { type: "repo_updated"; path: string }
  | { type: "head_changed"; path: string; head: string }
  | { type: "new_commit"; path: string; count: number };

export function useRepoEvents(onEvent: (ev: RepoEvent) => void, enabled: boolean) {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!enabled) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    let ws: WebSocket | null = null;
    let closed = false;
    let retry = 0;

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(`${proto}://${window.location.host}/events`);
      ws.onmessage = (m) => {
        try {
          handler.current(JSON.parse(m.data));
        } catch { /* ignore malformed */ }
      };
      ws.onopen = () => { retry = 0; };
      ws.onclose = () => {
        if (!closed) {
          retry += 1;
          setTimeout(connect, Math.min(5000, 500 * retry));
        }
      };
    };
    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [enabled]);
}
