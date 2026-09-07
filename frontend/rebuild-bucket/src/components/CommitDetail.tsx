/** Commit detail drawer: message body, parents, per-file changes, stats.
 *  Opens when a row is selected; data comes from GET /commit/detail
 *  (cached client-side and server-side). Escape or the close button
 *  dismisses it. Tab/Shift+Tab cycle within the drawer (focus trap). */
import { useEffect, useRef, useState } from "react";
import { fetchCommitDetail, isAbort, type CommitDetail as Detail } from "../api/client";
import { formatRelativeTime, useI18n } from "../i18n";
import Avatar from "./Avatar";
import RefsPills from "./RefsPills";

interface Props {
  repoPath: string | null;
  sha: string | null;
  onClose: () => void;
  onNavigate: (sha: string) => void;
}

function statusClass(status: string): string {
  switch (status) {
    case "added": return "add";
    case "deleted": return "del";
    case "renamed": return "ren";
    default: return "mod";
  }
}

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export default function CommitDetailPanel({ repoPath, sha, onClose, onNavigate }: Props) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const lastFocusRef = useRef<HTMLElement | null>(null);

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

  // Open: capture the previously focused element, focus the first focusable
  // in the drawer. Close: restore focus to the original element so keyboard
  // navigation resumes where it left off.
  useEffect(() => {
    if (!sha) return;
    lastFocusRef.current = (document.activeElement as HTMLElement | null) ?? null;
    const root = drawerRef.current;
    if (root) {
      const first = root.querySelector<HTMLElement>(FOCUSABLE);
      first?.focus();
    }
    return () => {
      lastFocusRef.current?.focus?.();
    };
  }, [sha]);

  // Escape closes; Tab/Shift+Tab cycle inside the drawer (focus trap).
  useEffect(() => {
    if (!sha) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const root = drawerRef.current;
      if (!root) return;
      const focusables = Array.from(
        root.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter((el) => !el.hasAttribute("disabled"));
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [sha, onClose]);

  if (!sha) return null;

  return (
    <>
      <div className="detail-veil" onClick={onClose} aria-hidden="true" />
      <aside
        ref={drawerRef}
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("detail_title")}
      >
      <div className="detail-header">
        <kbd className="detail-shortcut-hint" aria-hidden="true">⏎</kbd>
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
          {(detail.additions > 0 || detail.deletions > 0) && (
            <div className="detail-stats">
              <span className="diff-num add">+{detail.additions}</span>
              <span className="diff-num del">−{detail.deletions}</span>
            </div>
          )}
          <div className="detail-stats">
            <span className="detail-parents">
              {t("detail_parents", { n: detail.parents.length })}
            </span>
          </div>
          {detail.parents.length > 0 && (
            <div className="detail-parent-list mono">
              {detail.parents.map((p) => (
                <button
                  key={p}
                  type="button"
                  className="parent-link mono"
                  onClick={() => onNavigate(p)}
                  title={p}
                >
                  {p.slice(0, 7)}
                </button>
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
    </>
  );
}
