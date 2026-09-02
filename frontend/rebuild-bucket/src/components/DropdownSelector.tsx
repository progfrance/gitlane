/** Reusable labelled dropdown selector (repo / branch pickers in the header). */
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";

export interface DropdownItem {
  value: string;
  label: string;
  path?: string;          // secondary muted text (e.g. repo path)
}

export interface DropdownGroup {
  label?: string;         // optional group heading (e.g. "Remote branches")
  items: DropdownItem[];
}

interface Props {
  label: string;
  icon: React.ReactNode;
  value: string;
  groups: DropdownGroup[];
  onSelect: (value: string) => void;
}

export default function DropdownSelector({ label, icon, value, groups, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const activeValue = value;
  const { t } = useI18n();

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const all = groups.flatMap((g) => g.items);

  return (
    <div className="dropdown-selector" ref={rootRef}>
      <span className="selector-label">{label}</span>
      <button
        type="button"
        className={`selector-button${open ? " open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="selector-icon">{icon}</span>
        <span className="selector-value">{value}</span>
        <span className="chevron">▼</span>
      </button>
      {open && (
        <div className="selector-menu" role="listbox">
          {groups.map((g, gi) => (
            <div key={g.label ?? gi}>
              {g.label && <div className="selector-group-label">{g.label}</div>}
              {g.items.map((it) => (
                <button
                  key={it.value}
                  type="button"
                  role="option"
                  aria-selected={it.value === activeValue}
                  className={`selector-item${it.value === activeValue ? " active" : ""}`}
                  onClick={() => {
                    setOpen(false);
                    onSelect(it.value);
                  }}
                >
                  {it.value === activeValue && <span className="check">✓</span>}
                  <span className="item-label">{it.label}</span>
                  {it.path && <span className="item-path">{it.path}</span>}
                </button>
              ))}
            </div>
          ))}
          {all.length === 0 && <div className="selector-empty">{t("empty")}</div>}
        </div>
      )}
    </div>
  );
}
