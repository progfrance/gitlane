/** 16px author avatar with initials fallback (PLAN.md section 4.5). */

const PALETTE = ["#d6409f", "#8e4ec6", "#0091ff", "#00a2c7", "#f5a623", "#30a46c", "#e5484d", "#6e56cf"];

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
