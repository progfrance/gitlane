# GitLane

Visualiseur Git web avec graphe de commits en **swimlanes** pastel — backend Python (FastAPI), frontend React/TypeScript avec rendu Canvas virtualisé.

![stack](https://img.shields.io/badge/python-3.13-blue) ![fastapi](https://img.shields.io/badge/fastapi-0.115-green) ![react](https://img.shields.io/badge/react-18-61dafb)

## Fonctionnalités

- Ouverture d'un dépôt Git local (validation du chemin, sans exécution shell arbitraire)
- Historique des commits en rows denses 32 px avec graphe swimlanes coloré (Canvas, bezier pour forks/merges)
- Badges refs typés : branche locale (vert), remote (bleu), tag (orange), HEAD (contour accent)
- Recherche instantanée (message / SHA / auteur / ref) avec surlignage
- Mini timeline d'activité avec viewport synchronisé au scroll
- Virtual scroll (overdraw 8 rows) — fluide sur gros historiques
- Auto-refresh via WebSocket quand le dépôt change (poll `.git` 2 s côté serveur)
- Raccourcis clavier : `j`/`k` (commit suivant/précédent), `/` (recherche), `Échap` (effacer)

## Lancement (dev)

```bash
# Backend (port 8000, sert aussi le build frontend)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Linux/macOS
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# Frontend (dev server avec proxy, port 5173)
cd frontend
npm install
npm install-scripts approve esbuild   # si npm bloque les postinstall
npm run dev
```

- Mode dev : ouvrir <http://localhost:5173> (proxy API vers 8000)
- Mode production simple : `npm run build` puis <http://127.0.0.1:8000> (FastAPI sert `frontend/dist`)

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -q
```

- 11 tests du moteur de lanes (cas plan §8.4 : linéaire, merge, branche longue, octopus, racines multiples, géométrie)
- 12 tests de contrat API (open/history/refs/events + layout)

## API

| Endpoint | Description |
|---|---|
| `POST /repos/open` | Ouvre un dépôt (`{"path": "..."}`), calcule le layout global |
| `GET /history?path=&q=&limit=` | Commits paginés + `lane_index`, `node`, `segments` |
| `GET /refs?path=` | Branches locales/remotes/tags + HEAD |
| `GET /timeline?path=&buckets=` | Buckets d'activité pour la sparkline |
| `WS /events` | `repo_updated`, `head_changed`, `new_commit` |

## Architecture

```text
backend/app/
  api/          routes_repo, routes_history, routes_refs, routes_events (WS)
  services/     git_reader (CLI git), lane_layout, timeline_builder, cache, watcher
  models/       schémas Pydantic (contrat API)
frontend/src/
  app/          App.tsx (orchestration, raccourcis, auto-refresh)
  components/   TopToolbar, MiniTimeline, VirtualCommitTable, CommitRow, RefsPills, Avatar, RightMeta
  graph/        GraphCanvas, draw.ts, coords.ts (constantes partagées backend/front)
  api/          client.ts (typé), events.ts (websocket)
  store/        useRepoStore.ts
  styles/       tokens.css (design system), app.css
```

## Sécurité / robustesse

- Chemins absolus uniquement, vérification `toplevel == path` (pas de repo parent capté)
- Sous-processus git en liste d'arguments fixe + timeout 15 s, jamais de shell
- Recherche : révision sanitisée (pas d'option git injectée)
- Gestion d'états loading / error / empty avec repo-picker sur erreur

## Déploiement

- `npm run build` (frontend statique) + `uvicorn app.main:app --port 8000` : une seule origine, pas de CORS
- Reverse-proxy possible (nginx/caddy) devant uvicorn si besoin
