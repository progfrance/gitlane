/** Mini activity timeline with area fill, green/red bars, and viewport window.
 *  Reference: GitKraken-style sparkline with bicolor diff histogram. */
import { useEffect, useRef } from "react";
import type { TimelineData } from "../api/client";

interface Props {
  data: TimelineData | null;
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

const ACCENT = "#0091ff";
const AREA = "rgba(0,145,255,0.08)";
const GREEN = "#30a46c";
const RED = "#e54d2e";

export default function MiniTimeline({ data, scrollTop, scrollHeight, clientHeight }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = 40;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!data || !data.points.length) return;

    const pts = data.points;
    const maxC = Math.max(1, ...pts.map((p) => p.count));
    const maxAdds = Math.max(1, ...pts.map((p) => p.adds));
    const maxDels = Math.max(1, ...pts.map((p) => p.dels));
    const bw = w / pts.length;
    const mid = h / 2;

    // Layer 1: green/red micro-bars for additions / deletions.
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      // Green bar (additions) — upward from mid.
      if (p.adds > 0) {
        const bh = Math.max(1.5, (p.adds / maxAdds) * (h / 2 - 4));
        ctx.fillStyle = GREEN;
        ctx.globalAlpha = 0.6;
        ctx.beginPath();
        ctx.roundRect(i * bw + 2, mid - bh, Math.max(1, bw * 0.7), bh, 1);
        ctx.fill();
      }
      // Red bar (deletions) — downward from mid.
      if (p.dels > 0) {
        const bh = Math.max(1.5, (p.dels / maxDels) * (h / 2 - 4));
        ctx.fillStyle = RED;
        ctx.globalAlpha = 0.6;
        ctx.beginPath();
        ctx.roundRect(i * bw + 2, mid, Math.max(1, bw * 0.7), bh, 1);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    // Layer 2: area fill under envelope line.
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const v = pts[i].count / maxC;
      const y = mid - v * (h / 2 - 4);
      const x = i * bw + bw / 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    // Close the area path.
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
      const y = mid - v * (h / 2 - 4);
      const x = i * bw + bw / 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = ACCENT;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Layer 4: viewport rectangle.
    if (scrollHeight > clientHeight) {
      const vh = Math.max(10, (clientHeight / scrollHeight) * h);
      const vy = (scrollTop / scrollHeight) * h;
      ctx.fillStyle = "rgba(0, 145, 255, 0.10)";
      ctx.fillRect(0, vy, w, vh);
      ctx.strokeStyle = "rgba(0, 145, 255, 0.55)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(0.75, vy + 0.75, w - 1.5, vh - 1.5);
    }
  }, [data, scrollTop, scrollHeight, clientHeight]);

  return (
    <div className="mini-timeline">
      <canvas ref={canvasRef} />
    </div>
  );
}