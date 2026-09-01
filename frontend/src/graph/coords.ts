/** Shared geometry constants — must mirror backend lane_layout.py. */

export const ROW_HEIGHT = 32;
export const NODE_Y = 16;
export const LANE_GAP = 20;
export const NODE_R = 4.5;
export const FIRST_LANE_X = 24;

export function graphWidth(maxLane: number): number {
  return Math.max(120, Math.ceil(FIRST_LANE_X + (maxLane + 1) * LANE_GAP + 12));
}
