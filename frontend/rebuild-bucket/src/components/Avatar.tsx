/** 16px author avatar with initials fallback (PLAN.md section 4.5). */

import { LANE_COLORS } from "../graph/coords";

export function avatarColor(email: string): string {
  let h = 0;
  for (let i = 0; i < email.length; i++) h = (h * 31 + email.charCodeAt(i)) >>> 0;
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
