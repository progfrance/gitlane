/** Mini activity timeline with area fill, fine green/red bars, and viewport window.
 *  Reference: GitKraken-style sparkline with bicolor diff histogram.
 *  Subscribes to the scroll-viewport bus directly: scrolling never
 *  re-renders the app, only this canvas. */
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { TimelineData } from "../api/client";
import { getViewport, subscribeViewport } from "../store/viewport";
import { useI18n } from "../i18n";

interface Props {
  data: TimelineData | null;
}

const ACCENT = "#0091ff";
const AREA = "rgba(0,145,255,0.08)";
const GREEN = "#30a46c";
const RED = "#e54d2e";

export default function MiniTimeline({ data }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewport = useSyncExternalStore(subscribeViewport, getViewport, getViewport);
  const { t } = useI18n();
  // Force a redraw on container resize (window resize, sidebar toggle, ...).
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (r) setSize({ w: r.width, h: r.height });
    });
    ro.observe(canvas);
    const r = canvas.getBoundingClientRect();
    setSize({ w: r.width, h: r.height });
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = size.w || canvas.clientWidth;
    const h = 40;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!data || !data.points.length) {
      // Explicit blank — when data goes null the canvas must drop the
      // previous timeline (e.g. after switching repos).
      return;
    }

    const pts = data.points;
    const maxC = Math.max(1, ...pts.map((p) => p.count));
    const maxAdds = Math.max(1, ...pts.map((p) => p.adds));
    const maxDels = Math.max(1, ...pts.map((p) => p.dels));
    const bw = w / pts.length;
    const mid = h / 2;
    const barW = Math.max(1, Math.min(3, bw * 0.45)); // fine sticks, grid-aligned
    const maxBarH = h / 2 - 9; // keep bars short so the envelope reads above

    // Layer 1: fine green/red sticks (additions up, deletions down from mid).
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      const cx = i * bw + bw / 2;
      if (p.adds > 0) {
        const bh = Math.max(1.5, (p.adds / maxAdds) * maxBarH);
        ctx.fillStyle = GREEN;
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        ctx.roundRect(cx - barW / 2, mid - bh, barW, bh, 1);
        ctx.fill();
      }
      if (p.dels > 0) {
        const bh = Math.max(1.5, (p.dels / maxDels) * maxBarH);
        ctx.fillStyle = RED;
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        ctx.roundRect(cx - barW / 2, mid, barW, bh, 1);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    // Layer 2: area fill under envelope line.
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const v = pts[i].count / maxC;
      const y = mid - v * maxBarH;
      const x = i * bw + bw / 2;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    const lastX = (pts.length - 1) * bw + bw / 2;
    ctx.lineTo(lastX, mid);
    ctx.lineTo(bw / 2, mid);
    ctx.closePath();
    ctx.fillStyle = AREA;
    ctx.fill();

    // Layer 3: envelope line.
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const v = pts[i].count / maxC;
      const y = mid - v * maxBarH;
      const x = i * bw + bw / 2;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = ACCENT;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Layer 4: selection band (viewport) with subtle hatch + gradient fill.
    const { top: scrollTop, height: scrollHeight, client: clientHeight } = viewport;
    if (scrollHeight > clientHeight) {
      const vh = Math.max(10, (clientHeight / scrollHeight) * h);
      const vy = (scrollTop / scrollHeight) * h;
      const grad = ctx.createLinearGradient(0, vy, 0, vy + vh);
      grad.addColorStop(0, "rgba(0,145,255,0.16)");
      grad.addColorStop(1, "rgba(0,145,255,0.05)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, vy, w, vh);
      ctx.strokeStyle = "rgba(0,145,255,0.55)";
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, vy + 0.5, w - 1, vh - 1);
      // Hatch the selected interval (reference look).
      ctx.save();
      ctx.strokeStyle = "rgba(0,145,255,0.30)";
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      for (let yy = vy + 3; yy < vy + vh - 3; yy += 6) {
        ctx.beginPath();
        ctx.moveTo(0, yy);
        ctx.lineTo(w, yy);
        ctx.stroke();
      }
      ctx.restore();
    }
  }, [data, viewport, size.w, size.h]);

  const total = data?.points.reduce((n, p) => n + p.count, 0) ?? 0;
  return (
    <div className="mini-timeline">
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={t("timeline_label", { n: total })}
      />
    </div>
  );
}
