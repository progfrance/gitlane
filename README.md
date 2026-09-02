# GitLane

Web Git viewer with a commit graph rendered as pastel **swimlanes** — Python backend (FastAPI), React/TypeScript frontend with virtualized Canvas rendering.

![stack](https://img.shields.io/badge/python-3.13-blue) ![fastapi](https://img.shields.io/badge/fastapi-0.115-green) ![react](https://img.shields.io/badge/react-18-61dafb)

## Features

- Open a local Git repository (path validation, no arbitrary shell execution)
- Commit history as dense 32 px rows with a colored swimlane graph (Canvas, bezier curves for forks/merges)
- Premium nodes: ringed beads, double-ring merges, HEAD as a donut, glow on hover
- Row background tinted by the branch color (pastel swimlane)
- GitHub-style diff stats: green/red `+N −M` + 5 distribution squares
- Typed ref badges with icons: local branch (green), remote (blue), tag (orange), HEAD (accent outline)
- **Built-in repository switching**: `↩ Repo` button / `Ctrl+O`, picker page with persisted recents, folder scan, manual entry
- Instant search (message / SHA / author / ref) with highlighting
- Mini activity timeline (blue area + green/red bars) with viewport synchronized to scrolling
- Virtual scroll (overdraw 8 rows) — smooth on large histories
- Auto-refresh via WebSocket when the repository changes (server-side `.git` poll every 2 s)
- Keyboard shortcuts: `j`/`k` (next/previous commit), `/` (search), `Esc` (clear), `Ctrl+O` (switch repo)

## Launching (no npm — frozen bundle)

**No npm/node required**: the frontend is a pre-compiled static build in `frontend/dist/`,
served by FastAPI. You only need Python ≥ 3.11 (miniforge/conda recommended) and git.

```bash
# Backend (port 8088, also serves the frontend bundle)
cd backend
conda create -n gitlane python=3.13 -y && conda activate gitlane   # or a plain venv
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
```

Open **http://127.0.0.1:8088** — on first launch the `/picker` page is shown
to choose a repository; afterwards the last opened repository reopens automatically.

Offline installation and FAQ: see [INSTALL.md](INSTALL.md).

### Re-bundling the frontend (only if the rendering must change)

The TS/React sources are archived in `frontend/rebuild-bucket/`:

```bash
cd frontend/rebuild-bucket
npm install && npm run build      # regenerates ../dist/ (frozen bundle)
```

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -q
```

- 11 lane-engine tests (plan §8.4 cases: linear, merge, long branch, octopus, multiple roots, geometry)
- 12 API contract tests (open/history/refs/events + layout) + diff stats + HEAD flags
- 20 tests for the new features: persisted recents, browse/validate, picker + redirection

## API

| Endpoint | Description |
|---|---|
| `POST /repos/open` | Opens a repository (`{"path": "..."}`), computes the global layout, logs recents |
| `GET /history?path=&q=&limit=` | Paginated commits + `lane_index`, `node`, `segments`, `additions`, `deletions`, `is_head` |
| `GET /refs?path=` | Local/remote branches/tags + HEAD |
| `GET /timeline?path=&buckets=` | Activity buckets for the sparkline (+ `adds`/`dels` per bucket) |
| `GET /repos/recent` · `POST /repos/recent` | Persisted recents (`~/.gitlane_recent.json`, max 10) |
| `GET /repos/browse?root=&depth=` | Scan of git folders (depth 1-3, ignores symlinks/dotfiles) |
| `GET /repos/validate?path=` | Pre-validation of a path (is_git, name, head) without opening it |
| `GET /picker` | Pure HTML/JS page for repository selection |
| `WS /events` | `repo_updated`, `head_changed`, `new_commit` |

## Architecture

```text
backend/app/
  api/          routes_repo, routes_history, routes_refs, routes_events (WS),
                routes_recent, routes_browse + static/repos.html (picker)
  services/     git_reader (git CLI + numstat), lane_layout, timeline_builder,
                cache, watcher, recent (JSON persistence)
  models/       Pydantic schemas (API contract)
frontend/
  dist/         frozen static bundle (served by FastAPI — no npm at runtime)
  rebuild-bucket/  archived TS/React sources (optional rebuild)
```

## Security / robustness

- Absolute paths only, `toplevel == path` check (no parent repo captured)
- Git subprocesses with a fixed argument list + 15 s timeout, never a shell
- Search: sanitized revision (no injected git option)
- Browse scan: bounded depth (≤ 3), symlinks and dotfiles ignored, git folder = leaf
- Handling of loading / error / empty states with repo-picker on error

## Deployment

- Single origin: `uvicorn app.main:app --port 8088` serves the API + the bundle — no CORS
- Reverse proxy possible (nginx/caddy) in front of uvicorn if needed
- Persistence of recent repositories: `~/.gitlane_recent.json` (survives restarts)
