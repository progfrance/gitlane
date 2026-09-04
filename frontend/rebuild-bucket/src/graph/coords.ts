/** Shared geometry constants — must mirror backend lane_layout.py. */

/** Lane palette — same 12 colors as backend `lane_layout.LANE_COLORS`. */
export const LANE_COLORS = [
  "#d6409f", "#8e4ec6", "#0091ff", "#00a2c7", "#f5a623", "#30a46c",
  "#e5484d", "#6e56cf", "#12b5cb", "#e2b714", "#3eb8b3", "#7ee787",
];

export const ROW_HEIGHT = 32;
export const NODE_Y = 16;
export const LANE_GAP = 20;
export const NODE_R = 6.5;
export const FIRST_LANE_X = 24;

export function graphWidth(maxLane: number): number {
  return Math.max(120, Math.ceil(FIRST_LANE_X + (maxLane + 1) * LANE_GAP + 12));
}

/** Convert hex color to rgba string with alpha. */
export function hexToRgba(hex: string, alpha = 1): string {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!m) return hex;
  return `rgba(${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)},${alpha})`;
}

/** Darken a hex color by a factor (0 = unchanged, 1 = black). */
export function darken(hex: string, factor = 0.3): string {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!m) return hex;
  const f = Math.max(0, Math.min(1, factor));
  const c = (v: string) => Math.round(parseInt(v, 16) * (1 - f));
  return `rgb(${c(m[1])},${c(m[2])},${c(m[3])})`;
}
