/** 16px author avatar with initials fallback (PLAN.md section 4.5). */

import { LANE_COLORS } from "../graph/coords";

export function avatarColor(email: string): string {
  // FNV-1a 32-bit: more even distribution than djb2 across short/medium
  // email strings, so two-letter local parts rarely collide on the same
  // lane color.
  let h = 0x811c9dc5;
  for (let i = 0; i < email.length; i++) {
    h ^= email.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return LANE_COLORS[h % LANE_COLORS.length];
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export default function Avatar({ name, email }: { name: string; email: string }) {
  const ini = initials(name);
  return (
    <span className="avatar" style={{ background: avatarColor(email) }} title={name}>
      {ini || "?"}
    </span>
  );
}
