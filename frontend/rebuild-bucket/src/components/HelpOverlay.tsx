/** Keyboard shortcut help (`?` to open, Escape to close). */
import { useEffect } from "react";
import { useI18n } from "../i18n";

interface Props {
  open: boolean;
  onClose: () => void;
}

interface Shortcut {
  keys: string;
  descKey: string;
}

const SHORTCUTS: Shortcut[] = [
  { keys: "/", descKey: "sc_search" },
  { keys: "j", descKey: "sc_next" },
  { keys: "k", descKey: "sc_prev" },
  { keys: "Enter", descKey: "sc_open" },
  { keys: "Esc", descKey: "sc_clear" },
  { keys: "Ctrl+O", descKey: "sc_picker" },
  { keys: "?", descKey: "sc_help" },
];

export default function HelpOverlay({ open, onClose }: Props) {
  const { t } = useI18n();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="help-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t("help_title")}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="help-card">
        <div className="help-header">
          <span className="help-title">{t("help_title")}</span>
          <button type="button" className="toolbar-btn" onClick={onClose} aria-label={t("detail_close")}>✕</button>
        </div>
        <table className="help-table">
          <tbody>
            {SHORTCUTS.map((s) => (
              <tr key={s.keys}>
                <td><kbd>{s.keys}</kbd></td>
                <td>{t(s.descKey)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
