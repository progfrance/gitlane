/** Mini activity timeline with viewport window (PLAN.md section 4.2). */
import { useEffect, useRef } from "react";
import type { TimelineData } from "../api/client";

interface Props {
  data: TimelineData | null;
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

const LANES = ["#f79ac0", "#8dd3ff", "#9ee6b5", "#c3b6ff"];

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
    const bw = w / pts.length;
    const mid = h / 2;

    // Soft histogram.
    for (let i = 0; i < pts.length; i++) {
      const v = pts[i].count / maxC;
      if (v <= 0) continue;
      const bh = Math.max(1.5, v * (h / 2 - 4));
      ctx.fillStyle = LANES[i % LANES.length];
      ctx.globalAlpha = 0.55;
      ctx.beginPath();
      ctx.roundRect(i * bw + 1, mid - bh, Math.max(1, bw - 2), bh * 2, 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Envelope line.
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const v = pts[i].count / maxC;
      const y = mid - v * (h / 2 - 4);
      const x = i * bw + bw / 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 1;
    ctx.stroke();

    // Viewport rectangle.
    if (scrollHeight > clientHeight) {
      const vh = Math.max(10, (clientHeight / scrollHeight) * h);
      const vy = (scrollTop / scrollHeight) * h;
      ctx.fillStyle = "rgba(59, 130, 246, 0.10)";
      ctx.fillRect(0, vy, w, vh);
      ctx.strokeStyle = "rgba(59, 130, 246, 0.55)";
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
