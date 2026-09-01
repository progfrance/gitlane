/** Premium Canvas drawing for the lane graph (GitKraken-style glow + pearl nodes). */

import type { CommitItem } from "../api/client";
import { hexToRgba } from "./coords";

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

/** Draw a segment with a soft glow pass under the crisp stroke. */
function drawSegment(ctx: CanvasRenderingContext2D, seg: CommitItem["segments"][number]): void {
  const w = seg.w || 2;

  // Glow pass (wide alpha understroke)
  ctx.save();
  ctx.lineWidth = Math.max(2, w + 3);
  ctx.strokeStyle = hexToRgba(seg.color, 0.22);
  if (seg.type === "curve" && seg.cx1 !== undefined && seg.cy1 !== undefined && seg.cx2 !== undefined && seg.cy2 !== undefined) {
    ctx.beginPath();
    ctx.moveTo(seg.x1, seg.y1);
    ctx.bezierCurveTo(seg.cx1, seg.cy1, seg.cx2, seg.cy2, seg.x2, seg.y2);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.moveTo(seg.x1, seg.y1);
    ctx.lineTo(seg.x2, seg.y2);
    ctx.stroke();
  }

  // Crisp pass
  ctx.lineWidth = w;
  ctx.strokeStyle = seg.color;
  if (seg.type === "curve" && seg.cx1 !== undefined && seg.cy1 !== undefined && seg.cx2 !== undefined && seg.cy2 !== undefined) {
    ctx.beginPath();
    ctx.moveTo(seg.x1, seg.y1);
    ctx.bezierCurveTo(seg.cx1, seg.cy1, seg.cx2, seg.cy2, seg.x2, seg.y2);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.moveTo(seg.x1, seg.y1);
    ctx.lineTo(seg.x2, seg.y2);
    ctx.stroke();
  }
  ctx.restore();
}

/** Draw one row's lane segments + premium node. */
export function drawCommitGraph(
  canvas: HTMLCanvasElement,
  commit: CommitItem,
  width: number,
  rowHeight: number,
  opts: { hovered?: boolean; selected?: boolean } = {}
): void {
  const ctx = setupCanvas(canvas, width, rowHeight);
  if (!ctx) return;

  // Layer 1: lane segments (glow + crisp)
  for (const seg of commit.segments) {
    drawSegment(ctx, seg);
  }

  // Layer 2: premium node
  const node = commit.node;
  if (!node) return;

  const isMerge = commit.parents.length > 1;
  const isHead = commit.is_head;
  const r = node.r || 5.5;
  const x = node.x;
  const y = node.y;
  const color = node.color;

  // --- Outer soft halo (all nodes) ---
  const haloR = isMerge ? r + 5 : r + 4;
  ctx.save();
  ctx.beginPath();
  ctx.arc(x, y, haloR, 0, Math.PI * 2);
  ctx.fillStyle = hexToRgba(color, 0.12);
  ctx.fill();
  ctx.restore();

  // --- Hover/selected glow ---
  if (opts.hovered || opts.selected) {
    ctx.save();
    const grad = ctx.createRadialGradient(x, y, r * 0.5, x, y, r + 8);
    grad.addColorStop(0, hexToRgba(color, 0.35));
    grad.addColorStop(1, hexToRgba(color, 0));
    ctx.beginPath();
    ctx.arc(x, y, r + 8, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    if (opts.selected) {
      ctx.beginPath();
      ctx.arc(x, y, r + 5, 0, Math.PI * 2);
      ctx.strokeStyle = hexToRgba(color, 0.55);
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.restore();
  }

  // --- Merge commit: double ring ---
  if (isMerge) {
    // Outer ring
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, r + 1.5, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.stroke();
    ctx.restore();

    // Inner filled circle
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, r * 0.6, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();
    return;
  }

  // --- HEAD commit: donut ring ---
  if (isHead) {
    ctx.save();
    // Outer accent ring
    ctx.beginPath();
    ctx.arc(x, y, r + 2, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
    // Inner white core
    ctx.beginPath();
    ctx.arc(x, y, r * 0.5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();
    return;
  }

  // --- Normal commit: pearl circle ---
  ctx.save();
  // Main filled circle
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  // White ring
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#ffffff";
  ctx.stroke();
  ctx.restore();
}