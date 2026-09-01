/**
 * Minimal Phase A client: open a repo, list commits as plain rows.
 * Visual fidelity arrives in Phase C per PLAN.md.
 */
import { useCallback, useEffect, useState } from "react";

interface RefBadge {
  type: string;
  name: string;
}

interface CommitItem {
  sha: string;
  short_sha: string;
  message_subject: string;
  author_name: string;
  timestamp: number;
  relative_time: string;
  refs: RefBadge[];
}

interface HistoryEnvelope {
  items: CommitItem[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
}

export default function App() {
  const [repoPath, setRepoPath] = useState("C:/Users/Dell/Desktop/MesProjets/gitlane/gitlane");
  const [repo, setRepo] = useState<{ name: string; head: string; commit_count: number } | null>(null);
  const [history, setHistory] = useState<HistoryEnvelope | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openRepo = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch("/repos/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: repoPath }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "open failed");
      setRepo(data.repo);
      const hres = await fetch(`/history?path=${encodeURIComponent(repoPath)}&limit=300`);
      const hdata = await hres.json();
      if (!hres.ok) throw new Error(hdata.detail ?? "history failed");
      setHistory(hdata);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [repoPath]);

  useEffect(() => {
    void openRepo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ fontFamily: "Segoe UI, sans-serif", padding: 16 }}>
      <h2>GitLane — Phase A</h2>
      <div>
        <input
          style={{ width: 480 }}
          value={repoPath}
          onChange={(e) => setRepoPath(e.target.value)}
          placeholder="C:/absolute/path/to/repo"
        />
        <button onClick={() => void openRepo()}>Open</button>
      </div>
      {error && <p style={{ color: "#ef4444" }}>Error: {error}</p>}
      {repo && (
        <p>
          Repo <b>{repo.name}</b> — head <b>{repo.head}</b> — {repo.commit_count} commits
        </p>
      )}
      {history && (
        <ul style={{ lineHeight: 1.6 }}>
          {history.items.map((c) => (
            <li key={c.sha}>
              <code>{c.short_sha}</code> — {c.message_subject} ({c.author_name}, {c.relative_time})
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
