/** Rounded reference pills with icons — PLAN.md section 4.4 mapping. */
import type { RefBadge } from "../api/client";

function BranchIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
      <path d="M4.5 1A2.5 2.5 0 0 0 2 3.5v9A2.5 2.5 0 0 0 4.5 15h3a.75.75 0 0 0 0-1.5h-3a1 1 0 0 1-1-1v-1.09a2.5 2.5 0 0 0 0-4.82V3.5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v3.09a2.5 2.5 0 0 0 0 4.82V11a.75.75 0 0 0 1.5 0v-.09A2.5 2.5 0 0 0 13.5 8a2.5 2.5 0 0 0-1-2V3.5A2.5 2.5 0 0 0 10 1Zm0 10a1 1 0 1 1 0 2 1 1 0 0 1 0-2Zm7 0a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z" />
    </svg>
  );
}

function TagIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
      <path d="M1 7.775V2.75A1.75 1.75 0 0 1 2.75 1h5.025a1.75 1.75 0 0 1 1.237.513l5.025 5.025a1.75 1.75 0 0 1 0 2.474l-5.025 5.025a1.75 1.75 0 0 1-2.474 0L1.513 9.012A1.75 1.75 0 0 1 1 7.775Zm1.75-.025a.25.25 0 0 0-.25.25v5.025c0 .138.112.25.25.25h5.025a.25.25 0 0 0 .176-.073l5.025-5.025a.25.25 0 0 0 0-.353L7.176 2.573A.25.25 0 0 0 7 2.5H2.75a.25.25 0 0 0-.25.25v5.025ZM6 5a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z" />
    </svg>
  );
}

function RemoteIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
      <path d="M7.5 1.5a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V3.06L9.28 6.78a.75.75 0 0 1-1.06-1.06l3.72-3.72H8.25a.75.75 0 0 1-.75-.75Zm-2 3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V5.06L6.78 10.28a.75.75 0 0 1-1.06 0L2.78 7.25a.75.75 0 0 1 .69-1.27.75.75 0 0 1 .37.22L5.5 8.44l2.72-2.72H6.5a.75.75 0 0 1-.75-.75v-.22Z" />
    </svg>
  );
}

export default function RefsPills({ refs }: { refs: RefBadge[] }) {
  if (!refs.length) return null;
  return (
    <span className="refs-wrap">
      {refs.slice(0, 4).map((r, i) => (
        <span key={`${r.type}-${r.name}-${i}`} className={`ref-pill ${pillClass(r)}`}>
          {r.type === "head" && <span className="head-dot" />}
          {r.type === "local_branch" && <BranchIcon />}
          {r.type === "remote_branch" && <RemoteIcon />}
          {r.type === "tag" && <TagIcon />}
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