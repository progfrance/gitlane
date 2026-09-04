/** Reusable labelled dropdown selector (repo / branch pickers in the header).
 *  Full keyboard support: arrows move, Home/End jump, Enter selects,
 *  Escape closes and refocuses the trigger. */
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
  const [focusIdx, setFocusIdx] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const activeValue = value;
  const { t } = useI18n();

  const flat = groups.flatMap((g) => g.items);

  useEffect(() => {
    itemRefs.current = itemRefs.current.slice(0, flat.length);
  });

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open ]);

  // When opened, focus the active option (or the first one).
  useEffect(() => {
    if (!open) return;
    const idx = Math.max(0, flat.findIndex((it) => it.value === activeValue));
    setFocusIdx(idx);
    requestAnimationFrame(() => itemRefs.current[idx]?.focus());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const close = (refocus: boolean) => {
    setOpen(false);
    setFocusIdx(-1);
    if (refocus) buttonRef.current?.focus();
  };

  const choose = (val: string) => {
    setOpen(false);
    setFocusIdx(-1);
    buttonRef.current?.focus();
    onSelect(val);
  };

  const onTriggerKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      if (!open) {
        e.preventDefault();
        setOpen(true);
      }
    }
  };

  const onItemKey = (e: React.KeyboardEvent, idx: number) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = Math.min(flat.length - 1, idx + 1);
      setFocusIdx(next);
      itemRefs.current[next]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const prev = Math.max(0, idx - 1);
      setFocusIdx(prev);
      itemRefs.current[prev]?.focus();
    } else if (e.key === "Home") {
      e.preventDefault();
      setFocusIdx(0);
      itemRefs.current[0]?.focus();
    } else if (e.key === "End") {
      e.preventDefault();
      const last = flat.length - 1;
      setFocusIdx(last);
      itemRefs.current[last]?.focus();
    } else if (e.key === "Escape") {
      e.preventDefault();
      close(true);
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  let cursor = -1;

  return (
    <div className="dropdown-selector" ref={rootRef}>
      <span className="selector-label" id={`sel-label-${label}`}>{label}</span>
      <button
        ref={buttonRef}
        type="button"
        className={`selector-button${open ? " open" : ""}`}
        onClick={() => (open ? close(false) : setOpen(true))}
        onKeyDown={onTriggerKey}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="selector-icon" aria-hidden="true">{icon}</span>
        <span className="selector-value">{value}</span>
        <span className="chevron" aria-hidden="true">▼</span>
      </button>
      {open && (
        <div className="selector-menu" role="listbox" aria-label={label}>
          {groups.map((g, gi) => (
            <div key={g.label ?? gi} role="group" aria-label={g.label}>
              {g.label && <div className="selector-group-label" aria-hidden="true">{g.label}</div>}
              {g.items.map((it) => {
                cursor += 1;
                const idx = cursor;
                return (
                  <button
                    key={it.value}
                    ref={(el) => { itemRefs.current[idx] = el; }}
                    type="button"
                    role="option"
                    tabIndex={idx === focusIdx ? 0 : -1}
                    aria-selected={it.value === activeValue}
                    className={`selector-item${it.value === activeValue ? " active" : ""}`}
                    onClick={() => choose(it.value)}
                    onKeyDown={(e) => onItemKey(e, idx)}
                    onMouseEnter={() => setFocusIdx(idx)}
                  >
                    {it.value === activeValue && <span className="check" aria-hidden="true">✓</span>}
                    <span className="item-label">{it.label}</span>
                    {it.path && <span className="item-path">{it.path}</span>}
                  </button>
                );
              })}
            </div>
          ))}
          {flat.length === 0 && <div className="selector-empty">{t("empty")}</div>}
        </div>
      )}
    </div>
  );
}
