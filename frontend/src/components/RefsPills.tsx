/** Rounded reference pills — PLAN.md section 4.4 mapping. */
import type { RefBadge } from "../api/client";

export default function RefsPills({ refs }: { refs: RefBadge[] }) {
  if (!refs.length) return null;
  return (
    <span className="refs-wrap">
      {refs.slice(0, 4).map((r, i) => (
        <span key={`${r.type}-${r.name}-${i}`} className={`ref-pill ${pillClass(r)}`}>
          {r.type === "head" && <span className="head-dot" />}
          {r.name}
        </span>
      ))}
      {refs.length > 4 && <span className="ref-pill local">+{refs.length - 4}</span>}
    </span>
  );
}

function pillClass(r: RefBadge): string {
  switch (r.type) {
    case "local_branch": return "local";
    case "remote_branch": return "remote";
    case "tag": return "tag";
    default: return "head";
  }
}
