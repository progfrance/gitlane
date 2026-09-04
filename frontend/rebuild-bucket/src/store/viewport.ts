/** Scroll-viewport bus: the commit table reports scroll geometry here, and
 *  only MiniTimeline subscribes — scrolling no longer re-renders the app.
 *  Updates are coalesced with rAF so fast scrolls cost one notify/frame.
 */

export interface Viewport {
  top: number;
  height: number;
  client: number;
}

type Listener = () => void;

let current: Viewport = { top: 0, height: 1, client: 1 };
let scheduled = false;
const listeners = new Set<Listener>();

function notify() {
  scheduled = false;
  listeners.forEach((l) => l());
}

export function reportViewport(next: Viewport): void {
  current = next;
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(notify);
}

export function getViewport(): Viewport {
  return current;
}

export function subscribeViewport(l: Listener): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}
