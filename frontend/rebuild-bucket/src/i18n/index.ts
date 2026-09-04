/** Lightweight i18n: FR/EN dictionaries + an observable locale store.
 *  No external dependency — mirrors the tiny-observable pattern used by the
 *  repo store. The locale persists in localStorage under `gitlane.locale` and
 *  is shared with the static picker page (same origin). */
import { useSyncExternalStore } from "react";

export type Locale = "fr" | "en";

export const STORAGE_KEY = "gitlane.locale";

export const translations: Record<Locale, Record<string, string>> = {
  fr: {
    // App-level states
    loading_repo: "Chargement du dépôt…",
    failed_open: "Impossible d'ouvrir le dépôt",
    no_commits: "Aucun commit",
    no_result: "Aucun résultat pour « {query} »",
    no_commits_on: "Ce dépôt n'a aucun commit sur {ref}",
    rows_loaded: "{n} lignes · chargées en {ms} ms",
    open: "Ouvrir",
    // Toolbar / selectors
    current_repo: "Dépôt actuel",
    current_branch: "Branche actuelle",
    local_branches: "Branches locales",
    remote_branches: "Branches distantes",
    browse_repo: "Parcourir / Ouvrir un autre dépôt…",
    manual_ph: "Chemin absolu d'un dépôt git",
    search_placeholder: "Rechercher commit, sha, auteur…  ( / )",
    refresh: "Rafraîchir",
    commits_count: "{total} commits",
    no_repo: "aucun dépôt",
    change_repo: "Changer de dépôt (Ctrl+O)",
    repo_btn: "↩ Dépôt",
    language: "Langue",
    // Dropdown
    empty: "Aucune entrée",
    // Table footer
    loading_more: "Chargement…",
    scroll_for_more: "↓ Scrollez pour charger la suite",
    end_of_history: "Fin de l'historique",
    // Detail drawer
    timeline_label: "Activité des commits ({n} commits)",
    detail_title: "Détail du commit",
    detail_close: "Fermer le panneau de détail",
    detail_loading: "Chargement du commit…",
    detail_failed: "Impossible de charger le commit",
    detail_parents: "{n} parent(s)",
    detail_files: "{n} fichier(s) modifié(s)",
    detail_no_files: "Aucun fichier (commit de fusion ou vide)",
    // Help overlay
    help_title: "Raccourcis clavier",
    sc_search: "Rechercher un commit",
    sc_next: "Commit suivant",
    sc_prev: "Commit précédent",
    sc_open: "Ouvrir le commit sélectionné",
    sc_clear: "Effacer la recherche / fermer le panneau",
    sc_picker: "Choisir un autre dépôt",
    sc_help: "Afficher cette aide",
    // Relative time
    rt_just_now: "à l'instant",
    rt_minute: "il y a {n} minute",
    rt_minute_p: "il y a {n} minutes",
    rt_hour: "il y a {n} heure",
    rt_hour_p: "il y a {n} heures",
    rt_day: "il y a {n} jour",
    rt_day_p: "il y a {n} jours",
    rt_month: "il y a {n} mois",
    rt_month_p: "il y a {n} mois",
    rt_year: "il y a {n} an",
    rt_year_p: "il y a {n} ans",
  },
  en: {
    loading_repo: "Loading repository…",
    failed_open: "Failed to open repository",
    no_commits: "No commits",
    no_result: "No result for “{query}”",
    no_commits_on: "This repository has no commits on {ref}",
    rows_loaded: "{n} rows · loaded in {ms} ms",
    open: "Open",
    current_repo: "Current Repository",
    current_branch: "Current Branch",
    local_branches: "Local branches",
    remote_branches: "Remote branches",
    browse_repo: "Browse / Open another repo…",
    manual_ph: "Absolute path of a git repository",
    search_placeholder: "Search commit, sha, author…  ( / )",
    refresh: "Refresh",
    commits_count: "{total} commits",
    no_repo: "no repo",
    change_repo: "Change repository (Ctrl+O)",
    repo_btn: "↩ Repo",
    language: "Language",
    empty: "No entries",
    loading_more: "Loading…",
    scroll_for_more: "↓ Scroll to load more",
    end_of_history: "End of history",
    timeline_label: "Commit activity ({n} commits)",
    detail_title: "Commit detail",
    detail_close: "Close detail panel",
    detail_loading: "Loading commit…",
    detail_failed: "Failed to load commit",
    detail_parents: "{n} parent(s)",
    detail_files: "{n} changed file(s)",
    detail_no_files: "No files (merge or empty commit)",
    // Help overlay
    help_title: "Keyboard shortcuts",
    sc_search: "Search a commit",
    sc_next: "Next commit",
    sc_prev: "Previous commit",
    sc_open: "Open selected commit",
    sc_clear: "Clear search / close panel",
    sc_picker: "Pick another repository",
    sc_help: "Show this help",
    rt_just_now: "just now",
    rt_minute: "{n} minute ago",
    rt_minute_p: "{n} minutes ago",
    rt_hour: "{n} hour ago",
    rt_hour_p: "{n} hours ago",
    rt_day: "{n} day ago",
    rt_day_p: "{n} days ago",
    rt_month: "{n} month ago",
    rt_month_p: "{n} months ago",
    rt_year: "{n} year ago",
    rt_year_p: "{n} years ago",
  },
};

function detectLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "fr" || saved === "en") return saved;
  } catch {
    /* localStorage unavailable (private mode) — fall through to detection */
  }
  const nav = typeof navigator !== "undefined" ? navigator.language || "" : "";
  return nav.toLowerCase().startsWith("fr") ? "fr" : "en";
}

let locale: Locale = detectLocale();
const listeners = new Set<() => void>();

export function getLocale(): Locale {
  return locale;
}

export function setLocale(next: Locale): void {
  if (next === locale) return;
  locale = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* non-fatal: the session still switches, just without persistence */
  }
  listeners.forEach((fn) => fn());
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Translate `key` for the active locale, interpolating `{var}` placeholders. */
export function t(key: string, vars?: Record<string, string | number>): string {
  let s = translations[locale][key] ?? translations.en[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.split(`{${k}}`).join(String(v));
    }
  }
  return s;
}

/** React hook: re-renders the caller whenever the locale changes. */
export function useI18n() {
  const current = useSyncExternalStore(subscribe, getLocale, getLocale);
  return { t, locale: current, setLocale };
}

/** Locale-aware relative time from a unix timestamp (seconds). */
export function formatRelativeTime(
  timestamp: number,
  now: number = Math.floor(Date.now() / 1000),
): string {
  const delta = Math.max(0, now - timestamp);
  if (delta < 60) return t("rt_just_now");
  const minutes = Math.floor(delta / 60);
  if (minutes < 60) return rtUnit(minutes, "rt_minute");
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return rtUnit(hours, "rt_hour");
  const days = Math.floor(hours / 24);
  if (days < 31) return rtUnit(days, "rt_day");
  const months = Math.floor(days / 31);
  if (months < 12) return rtUnit(months, "rt_month");
  const years = Math.floor(days / 365);
  return rtUnit(years, "rt_year");
}

function rtUnit(n: number, base: string): string {
  return t(n === 1 ? base : `${base}_p`, { n });
}