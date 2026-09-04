/** Commit detail drawer: message body, parents, per-file changes, stats.
 *  Opens when a row is selected; data comes from GET /commit/detail
 *  (cached client-side). Escape or the close button dismisses it. */
import { useEffect, useState } from "react";
import { fetchCommitDetail, isAbort, type CommitDetail as Detail } from "../api/client";
import { formatRelativeTime, useI18n } from "../i18n";
import Avatar from "./Avatar";
import RefsPills from "./RefsPills";

interface Props {
  repoPath: string | null;
  sha: string | null;
  onClose: () => void;
}

function statusClass(status: string): string {
  switch (status) {
    case "added": return "add";
    case "deleted": return "del";
    case "renamed": return "ren";
    default: return "mod";
  }
}

export default function CommitDetailPanel({ repoPath, sha, onClose }: Props) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!repoPath || !sha) {
      setDetail(null);
      setError(null);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    fetchCommitDetail(repoPath, sha, ctrl.signal)
      .then((d) => {
        if (!ctrl.signal.aborted) {
          setDetail(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (isAbort(e) || ctrl.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [repoPath, sha]);

  useEffect(() => {
    if (!sha) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [sha, onClose]);

  if (!sha) return null;

  return (
    <aside className="detail-drawer" role="dialog" aria-modal="false" aria-label={t("detail_title")}>
      <div className="detail-header">
        <span className="detail-sha mono">{sha.slice(0, 7)}</span>
        <button type="button" className="toolbar-btn" onClick={onClose} aria-label={t("detail_close")}>
          ✕
        </button>
      </div>
      {loading && (
        <div className="state-block"><div className="spinner" /><span>{t("detail_loading")}</span></div>
      )}
      {error && !loading && (
        <div className="state-block error">
          <span className="state-title">{t("detail_failed")}</span>
          <span>{error}</span>
        </div>
      )}
      {detail && !loading && (
        <div className="detail-body">
          <div className="detail-subject">{detail.message_subject}</div>
          {detail.message_body && <pre className="detail-message">{detail.message_body}</pre>}
          <div className="detail-meta">
            <Avatar name={detail.author_name} email={detail.author_email} />
            <span>{detail.author_name}</span>
            <span className="commit-date">{formatRelativeTime(detail.timestamp)}</span>
          </div>
          {detail.refs.length > 0 && <RefsPills refs={detail.refs} />}
          <div className="detail-stats">
            <span className="diff-num add">+{detail.additions}</span>
            <span className="diff-num del">−{detail.deletions}</span>
            <span className="detail-parents">
              {t("detail_parents", { n: detail.parents.length })}
            </span>
          </div>
          {detail.parents.length > 0 && (
            <div className="detail-parent-list mono">
              {detail.parents.map((p) => (
                <span key={p} className="commit-sha">{p.slice(0, 7)}</span>
              ))}
            </div>
          )}
          <div className="detail-files-label">
            {t("detail_files", { n: detail.files.length })}
          </div>
          <ul className="detail-files">
            {detail.files.map((f) => (
              <li key={f.path} className="detail-file">
                <span className={`file-status ${statusClass(f.status)}`} title={f.status}>
                  {f.status.slice(0, 1).toUpperCase()}
                </span>
                <span className="file-path mono">{f.path}</span>
                {(f.additions > 0 || f.deletions > 0) && (
                  <span className="file-stat">
                    <span className="diff-num add">+{f.additions}</span>
                    <span className="diff-num del">−{f.deletions}</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
          {detail.files.length === 0 && (
            <div className="detail-empty">{t("detail_no_files")}</div>
          )}
        </div>
      )}
    </aside>
  );
}
