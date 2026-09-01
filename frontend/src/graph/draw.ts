/** Canvas drawing primitives for the lane graph (PLAN.md section 5). */

import type { CommitItem } from "../api/client";

export function setupCanvas(
  canvas: HTMLCanvasElement,
  width: number,
  height: number
): CanvasRenderingContext2D | null {
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(width));
  const h = Math.max(1, Math.round(height));
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr;
    canvas.height = h * dpr;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  return ctx;
}

function pathSegment(ctx: CanvasRenderingContext2D, seg: CommitItem["segments"][number]): void {
  if (seg.type === "curve" && seg.cx1 !== undefined && seg.cy1 !== undefined && seg.cx2 !== undefined && seg.cy2 !== undefined) {
    ctx.beginPath();
    ctx.moveTo(seg.x1, seg.y1);
    ctx.bezierCurveTo(seg.cx1, seg.cy1, seg.cx2, seg.cy2, seg.x2, seg.y2);
  } else {
    ctx.beginPath();
    ctx.moveTo(seg.x1, seg.y1);
    ctx.lineTo(seg.x2, seg.y2);
  }
}

/** Draw one row's lane segments + node. Rows are 32px tall, y local. */
export function drawCommitGraph(
  canvas: HTMLCanvasElement,
  commit: CommitItem,
  width: number,
  rowHeight: number,
  opts: { hovered?: boolean; selected?: boolean } = {}
): void {
  const ctx = setupCanvas(canvas, width, rowHeight);
  if (!ctx) return;

  // Layer 1: lane segments (pass-throughs first, then the row's own edges).
  for (const seg of commit.segments) {
    ctx.strokeStyle = seg.color;
    ctx.lineWidth = seg.w;
    pathSegment(ctx, seg);
    ctx.stroke();
  }

  // Layer 2: hover halo, then node.
  const node = commit.node;
  if (node) {
    if (opts.hovered || opts.selected) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r + 4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(59, 130, 246, 0.18)";
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
    ctx.fillStyle = node.color;
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
  }
}
