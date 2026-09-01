/** 16px author avatar with initials fallback (PLAN.md section 4.5). */

const PALETTE = ["#f79ac0", "#8dd3ff", "#9ee6b5", "#ffd48a", "#c3b6ff", "#ffb2a6", "#94e2d5", "#b7e48a"];

export function avatarColor(email: string): string {
  let h = 0;
  for (let i = 0; i < email.length; i++) h = (h * 31 + email.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export default function Avatar({ name, email }: { name: string; email: string }) {
  const initials = name
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span className="avatar" style={{ background: avatarColor(email) }} title={name}>
      {initials || "?"}
    </span>
  );
}
