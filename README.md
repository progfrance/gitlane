# GitLane

Visualiseur Git web avec graphe de commits en **swimlanes** pastel — backend Python (FastAPI), frontend React/TypeScript avec rendu Canvas virtualisé.

![stack](https://img.shields.io/badge/python-3.13-blue) ![fastapi](https://img.shields.io/badge/fastapi-0.115-green) ![react](https://img.shields.io/badge/react-18-61dafb)

## Fonctionnalités

- Ouverture d'un dépôt Git local (validation du chemin, sans exécution shell arbitraire)
- Historique des commits en rows denses 32 px avec graphe swimlanes coloré (Canvas, bezier pour forks/merges)
- Nœuds premium : perles cerclées, merge en double anneau, HEAD en donut, glow au survol
- Fond de ligne teinté par la couleur de la branche (swimlane pastel)
- Diff stats GitHub-style : `+N −M` vert/rouge + 5 carrés de répartition
- Badges refs typés avec icônes : branche locale (vert), remote (bleu), tag (orange), HEAD (contour accent)
- **Changement de dépôt intégré** : bouton `↩ Repo` / `Ctrl+O`, page picker avec récents persistés, scan de dossiers, saisie manuelle
- Recherche instantanée (message / SHA / auteur / ref) avec surlignage
- Mini timeline d'activité (aire bleue + barres vertes/rouges) avec viewport synchronisé au scroll
- Virtual scroll (overdraw 8 rows) — fluide sur gros historiques
- Auto-refresh via WebSocket quand le dépôt change (poll `.git` 2 s côté serveur)
- Raccourcis clavier : `j`/`k` (commit suivant/précédent), `/` (recherche), `Échap` (effacer), `Ctrl+O` (changer de repo)

## Lancement (sans npm — bundle gelé)

**Aucun npm/node requis** : le frontend est un build statique pré-compilé dans `frontend/dist/`,
servi par FastAPI. Il faut seulement Python ≥ 3.11 (miniforge/conda recommandé) et git.

```bash
# Backend (port 8088, sert aussi le bundle frontend)
cd backend
conda create -n gitlane python=3.13 -y && conda activate gitlane   # ou venv classique
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
```

Ouvrir **http://127.0.0.1:8088** — au premier lancement la page `/picker` s'affiche
pour choisir un dépôt ; ensuite le dernier dépôt ouvert se rouvre automatiquement.

Installation hors-ligne et FAQ : voir [INSTALL.md](INSTALL.md).

### Re-bundler le frontend (uniquement si le rendu doit changer)

Les sources TS/React sont archivées dans `frontend/rebuild-bucket/` :

```bash
cd frontend/rebuild-bucket
npm install && npm run build      # régénère ../dist/ (bundle gelé)
```

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -q
```

- 11 tests du moteur de lanes (cas plan §8.4 : linéaire, merge, branche longue, octopus, racines multiples, géométrie)
- 12 tests de contrat API (open/history/refs/events + layout) + diff stats + flags HEAD
- 20 tests des nouvelles fonctionnalités : récents persistés, browse/validate, picker + redirection

## API

| Endpoint | Description |
|---|---|
| `POST /repos/open` | Ouvre un dépôt (`{"path": "..."}`), calcule le layout global, log les récents |
| `GET /history?path=&q=&limit=` | Commits paginés + `lane_index`, `node`, `segments`, `additions`, `deletions`, `is_head` |
| `GET /refs?path=` | Branches locales/remotes/tags + HEAD |
| `GET /timeline?path=&buckets=` | Buckets d'activité pour la sparkline (+ `adds`/`dels` par bucket) |
| `GET /repos/recent` · `POST /repos/recent` | Récents persistés (`~/.gitlane_recent.json`, max 10) |
| `GET /repos/browse?root=&depth=` | Scan de dossiers git (profondeur 1-3, ignore symlinks/dotfiles) |
| `GET /repos/validate?path=` | Pré-validation d'un chemin (is_git, name, head) sans ouvrir |
| `GET /picker` | Page HTML/JS pur de sélection de dépôt |
| `WS /events` | `repo_updated`, `head_changed`, `new_commit` |

## Architecture

```text
backend/app/
  api/          routes_repo, routes_history, routes_refs, routes_events (WS),
                routes_recent, routes_browse + static/repos.html (picker)
  services/     git_reader (CLI git + numstat), lane_layout, timeline_builder,
                cache, watcher, recent (persistance JSON)
  models/       schémas Pydantic (contrat API)
frontend/
  dist/         bundle statique gelé (servi par FastAPI — pas de npm au runtime)
  rebuild-bucket/  sources TS/React archivées (re-build optionnel)
```

## Sécurité / robustesse

- Chemins absolus uniquement, vérification `toplevel == path` (pas de repo parent capté)
- Sous-processus git en liste d'arguments fixe + timeout 15 s, jamais de shell
- Recherche : révision sanitisée (pas d'option git injectée)
- Scan browse : profondeur bornée (≤ 3), symlinks et dotfiles ignorés, dossier git = feuille
- Gestion d'états loading / error / empty avec repo-picker sur erreur

## Déploiement

- Une seule origine : `uvicorn app.main:app --port 8088` sert l'API + le bundle — pas de CORS
- Reverse-proxy possible (nginx/caddy) devant uvicorn si besoin
- Persistance des derniers repos : `~/.gitlane_recent.json` (survit aux redémarrages)
