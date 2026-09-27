/** Cross-repo tag search: slide-in panel on the right edge. */
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTagHits, type TagHit, type TagsFindResponse } from "../api/tags";
import { formatRelativeTime, useI18n } from "../i18n";

const ROOT_STORAGE_KEY = "gitlane.tagsRoot";

interface Props {
  open: boolean;
  defaultRoot: string;
  onClose: () => void;
  onOpen: (repoPath: string, tagName: string) => void;
}

export default function TagsPanel({ open, defaultRoot, onClose, onOpen }: Props) {
  const { t } = useI18n();
  const [root, setRoot] = useState("");
  const [tag, setTag] = useState("");
  const [depth, setDepth] = useState(2);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [result, setResult] = useState<TagsFindResponse | null>(null);
  const [error, setError] = useState<string>("");
  const tagInputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Initialise inputs from localStorage / current repo when the panel opens.
  useEffect(() => {
    if (!open) return;
    let saved = "";
    try { saved = localStorage.getItem(ROOT_STORAGE_KEY) ?? ""; } catch { /* private mode */ }
    setRoot(saved || defaultRoot);
    setTag("");
    setStatus("idle");
    setResult(null);
    setError("");
    // Focus the tag input once the panel has rendered.
    const id = window.setTimeout(() => tagInputRef.current?.focus(), 50);
    return () => window.clearTimeout(id);
  }, [open, defaultRoot]);

  // Persist the chosen root as the user edits it (best-effort, no spam).
  useEffect(() => {
    if (!open || !root) return;
    try { localStorage.setItem(ROOT_STORAGE_KEY, root); } catch { /* ignore */ }
  }, [open, root]);

  // Esc closes (only when the panel itself has focus — inputs handle Esc
  // natively to clear themselves, which is the more useful behaviour).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const active = document.activeElement;
      if (active && (active.tagName === "INPUT" || active.tagName === "SELECT")) return;
      e.stopPropagation();
      onClose();
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [open, onClose]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const run = useCallback(async () => {
    if (!root.trim() || !tag.trim()) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStatus("loading");
    setError("");
    try {
      const data = await fetchTagHits(root.trim(), tag.trim(), depth, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setResult(data);
      setStatus("done");
    } catch (e) {
      if (ctrl.signal.aborted) return;
      setStatus("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [root, tag, depth]);

  const onSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    run();
  }, [run]);

  if (!open) return null;

  return (
    <aside
      className="tags-panel"
      role="dialog"
      aria-modal="false"
      aria-label={t("tags_panel_title")}
    >
      <header className="tags-panel-header">
        <span className="tags-panel-title">{t("tags_panel_title")}</span>
        <button
          type="button"
          className="toolbar-btn"
          onClick={onClose}
          aria-label={t("tags_panel_close")}
          title={t("tags_panel_close")}
        >
          ✕
        </button>
      </header>
      <form className="tags-panel-form" onSubmit={onSubmit}>
        <label className="tags-panel-field">
          <span>{t("tags_panel_root")}</span>
          <input
            type="text"
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            placeholder={defaultRoot}
            spellCheck={false}
            autoComplete="off"
          />
        </label>
        <label className="tags-panel-field">
          <span>{t("tags_panel_tag")}</span>
          <input
            ref={tagInputRef}
            type="text"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            placeholder="v1.2.0"
            spellCheck={false}
            autoComplete="off"
          />
        </label>
        <label className="tags-panel-field tags-panel-depth">
          <span>{t("tags_panel_depth")}</span>
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
        <button
          type="submit"
          className="tags-panel-submit"
          disabled={status === "loading" || !root.trim() || !tag.trim()}
        >
          {t("tags_panel_search")}
        </button>
      </form>

      <div className="tags-panel-results" aria-live="polite">
        {status === "loading" && (
          <div className="tags-panel-loading">{t("tags_panel_loading")}</div>
        )}
        {status === "error" && (
          <div className="tags-panel-error">{t("tags_panel_failed")}: {error}</div>
        )}
        {status === "done" && result && (
          <>
            {result.truncated && (
              <div className="tags-panel-banner">
                {t("tags_panel_truncated", { n: result.scanned })}
              </div>
            )}
            {result.items.length === 0 ? (
              <div className="tags-panel-empty">{t("tags_panel_empty")}</div>
            ) : (
              <ul className="tag-hit-list">
                {result.items.map((hit) => (
                  <TagHitRow key={hit.repo_path} hit={hit} onOpen={onOpen} />
                ))}
              </ul>
            )}
            {result.missing.length > 0 && (
              <div className="tags-panel-missing">
                {t("tags_panel_missing", { n: result.missing.length })}
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function TagHitRow({ hit, onOpen }: { hit: TagHit; onOpen: (path: string, tag: string) => void }) {
  const { t } = useI18n();
  const shortSha = hit.sha.slice(0, 7);
  const age = hit.age_seconds > 0 ? formatRelativeTime(hit.age_seconds) : "";
  return (
    <li>
      <button
        type="button"
        className="tag-hit-row"
        onClick={() => onOpen(hit.repo_path, hit.tag_name)}
        title={t("tags_panel_open")}
      >
        <div className="tag-hit-head">
          <span className="tag-hit-name">{hit.repo_name}</span>
          <span className="ref-pill tag">
            {TagIcon} {hit.tag_name}@{shortSha}
          </span>
        </div>
        <div className="tag-hit-path">{hit.repo_path}</div>
        {age && <div className="tag-hit-age">{age}</div>}
      </button>
    </li>
  );
}

const TagIcon = (
  <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
    <path d="M2.5 7.5a3.5 3.5 0 0 1 7 0V11a3 3 0 0 1-3 3H4a1 1 0 1 1 0-2h2.5a1 1 0 1 0 0-2H4a3 3 0 0 1-3-3v-.5ZM9.5 6h-7v-2h7V1.5l4.5 4.5-4.5 4.5V6Z" />
  </svg>
);