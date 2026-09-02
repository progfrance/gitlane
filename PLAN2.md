# PLAN2.md — GitLane npm-free + change folder

> Vision: run **GitLane with zero build** on the user's computer (Python only via miniforge), and provide a **folder picker** to switch between multiple repos without restarting the server.

---

## 1. Full analysis of the existing project

### 1.1 Repo map

| Zone | Files | LOC | Role |
|---|---:|---:|---|
| `backend/app/main.py` | 1 | 58 | FastAPI entrypoint, CORS + static mount |
| `backend/app/api/` | 4 routes | 293 | REST endpoints + WebSocket |
| `backend/app/services/` | 5 modules | 603 | `git_reader`, `lane_layout`, `cache`, `watcher`, `timeline_builder` |
| `backend/app/models/` | 3 schemas | 107 | Pydantic v2 (commits, graph, repo) |
| `backend/tests/` | 3 files | 376 | Pytest (lane layout + API contract) |
| `backend/requirements.txt` | 1 | 5 | `fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx` |
| `frontend/src/**` | 17 files | 1,294 | React 18 + TS + Canvas 2D (vite) |
| `frontend/dist/**` | 2 files | ~155 KB JS + 6 KB CSS | **Already-compiled static build** |
| `frontend/package.json` + `package-lock.json` | 2 | 530+ | React, Vite, TypeScript, esbuild |
| `frontend/vite.config.ts` | 1 | 18 | Proxy `/repos /history /refs /api /events` to `:8088` |

**Total useful source**: ~1,437 LOC Python + ~1,294 LOC TS/TSX/CSS.

### 1.2 The npm boundary (where the dependency hides)

The entire npm chain comes down to **2 links**:

1. **Build**: `tsc -b && vite build` → produces `frontend/dist/index.html + assets/`.
2. **Dev server**: `vite` (port 5173) with a proxy to FastAPI (port 8088).

**Neither of these is indispensable**:
- The build is already materialized on disk (`frontend/dist/index-BZLGn9vk.js`, `index-D_9L7Hs1.css`).
- The dev server only exists to re-bundle and proxy — the FastAPI backend **already serves** `dist/` as a root mount when it exists (`main.py:57-58`).

### 1.3 API routes useful for the folder change

The "open a repo" mechanism already exists on the backend; we just need to expose its usage in the UI.

| Endpoint | Method | Role | Reusable for "change folder"? |
|---|---|---|---|
| `/repos/open` | POST | `{"path": "..."}` → loads refs, commits, layout, caches them | ✅ core of the feature |
| `/repos/current` | GET | Currently open repo | ✅ to restore state |
| `/repos/list` | **new** | GET | List of recently opened repos (from the cache) | 🆕 "recent" UX |
| `/repos/recent` | **new** | GET | On-disk persistence `~/.gitlane_recent.json` | 🆕 multi-session |
| `/repos/browse` | **new** | GET | `?root=C:\Users` → git folders detected 1 level deep | 🆕 picker |
| `/repos/validate` | **new** | GET | `?path=...` → `{is_git, head, name}` without opening | 🆕 pre-check |

### 1.4 Testing what exists

- `tests/test_lane_layout.py`: 183 LOC, 11 cases (linear, merge, long branch, octopus, multiple roots, geometry).
- `tests/test_api.py`: 126 LOC, 12 cases (open, history, refs, events, layout).
- `conftest.py`: 67 LOC (FastAPI TestClient fixtures).

Everything is **npm-independent** — pytest + httpx are enough. The frontend is never touched by the tests.

### 1.5 Current security (to preserve)

- `routes_repo.open_repo`: `os.path.isabs` + `os.path.isdir` + `git_reader.is_git_repo` before `reload_state` → no shell, no injection.
- `git_reader`: `git` subprocess with fixed argv + 15 s timeout.
- No disk writes on the backend except the RAM cache (`services/cache.py`).

---

## 2. npm-free strategy (zero build, zero dev server)

### 2.1 Starting point

`frontend/dist/` is **already built** on this PC (Vite 5 produced a minified bundle with production React 18 inlined). The bundle:
- has no external source map;
- loads `assets/index-*.js` (155 KB) + `assets/index-*.css` (6 KB) from `/assets/...`;
- talks directly to `/repos`, `/history`, `/refs`, `/events`, `/api` on the same origin.

Consequence: **we can delete all of `frontend/src/`, `node_modules/`, `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `tsconfig.tsbuildinfo`** without breaking rendering, provided we keep `frontend/dist/index.html` + `frontend/dist/assets/*`.

### 2.2 Chosen option: "frozen dist"

- **Keep**: `frontend/dist/` (versioned build artifact, ~165 KB).
- **Delete**: `frontend/src/`, `frontend/node_modules/`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.tsbuildinfo`, `frontend/index.html` (the root `index.html` is replaced at runtime by the one from `dist/`).
- **Add**: `frontend/dist/.gitkeep` if needed + a note in the README: "To rebuild the bundle, use a machine with node ≥ 18 and run `npm run build` once."

### 2.3 Why not rewrite the frontend in plain HTML/JS?

- 1,294 LOC of TS/TSX, including `GraphCanvas` (Canvas 2D with bezier curves, virtual scroll, synchronized mini-timeline) — not trivial to rewrite by hand without a framework.
- The compiled bundle is 155 KB minified (≈ 50 KB gzipped) — negligible.
- Refactor = high regression risk, low real gain.
- The user said "I don't have npm", not "I want a different frontend". Let's preserve what works.

### 2.4 What remains on the target machine

```
gitlane/
├── backend/                # Python only
│   ├── app/                # FastAPI
│   ├── tests/              # pytest
│   ├── requirements.txt
│   └── .venv/              # created at install
├── frontend/
│   └── dist/               # pre-compiled static bundle (frozen)
├── PLAN.md                 # archive
├── PLAN2.md                # this document
├── README.md               # to be updated
└── .gitignore
```

**Total excluding `.venv/`**: ~0.5 MB. **No node executable required** to use the app.

### 2.5 Install procedure (miniforge, offline-friendly)

```bash
# 1. Create the env (one time only)
cd gitlane/backend
conda create -n gitlane python=3.13 -y
conda activate gitlane

# 2. Install the deps (pip works in a conda env)
pip install -r requirements.txt

# 3. Launch
python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
# → open http://127.0.0.1:8088
```

If the target computer is **strictly offline**, you can:
- run `pip download -r requirements.txt -d wheels/` on a machine with network access;
- copy the `wheels/` folder;
- `pip install --no-index --find-links=wheels/ -r requirements.txt`.

---

## 3. "Change folder" feature — design

### 3.1 Principle

`POST /repos/open` already exists: it takes an absolute path, validates, loads, and caches. The current frontend **already exposes** a text input to enter this path. Missing:
1. a native **selection dialog** (browse the local tree without retyping the path by hand);
2. a **persistent history** of recently opened repos;
3. an **automatic detector** of nearby git folders;
4. a **shortcut** to switch without reloading the page.

### 3.2 Backend side (4 new endpoints, ~80 LOC)

#### `GET /repos/recent`
- Reads `~/.gitlane_recent.json` (max 10 entries, deduplicated, most recent first).
- Returns `[{"path": "...", "name": "...", "last_open": "ISO"}]`.
- 200 if absent (empty list, do not 404).

#### `POST /repos/recent`
- Body `{"path": "..."}`.
- Pushes to the top, dedupes, truncates to 10, writes the JSON.
- Idempotent.

#### `GET /repos/browse?root=<abs>&depth=<1-3>`
- `root`: starting absolute path (e.g. `C:\Users\Dell`).
- `depth`: 1 by default, max 3 (avoids scanning the whole disk).
- Walks subfolders, testing `is_git_repo(path)` at each level.
- Returns `[{"path": "...", "name": "...", "head": "..."}]`.
- ⚠ Guard rails: **no error if root doesn't exist** (returns `[]`); `depth` capped at 3; no symlink following.

#### `GET /repos/validate?path=<abs>`
- Reuses `git_reader.is_git_repo` + `git_reader.repo_name` + `git_reader.read_refs` (just the `head`).
- Returns `{is_git: bool, name: str|null, head: str|null}`.
- Used to pre-validate before opening, without touching the cache.

#### Storage file
- Path: `os.path.expanduser("~/.gitlane_recent.json")` — portable across Win/Linux/macOS.
- Format: JSON, free schema, versioned with `"v": 1` to evolve.

### 3.3 Frontend side (modifying the frozen dist bundle)

The bundle is **frozen** by principle (see §2.2). To add the feature without a rebuild:

**Option A — pre-bundle the changes on a machine with node**:
- Edit `frontend/src/app/App.tsx` + `TopToolbar.tsx` on a machine that has node.
- `npm run build` → new `dist/`.
- Commit the new `dist/`.
- This is the cleanest option; you rebundle once and it's set.

**Option B — runtime injection via an external script** (doesn't alter the bundle):
- Add a `<script src="/static/gitlane-patches.js">` loaded **after** the React bundle.
- This script:
  - monkey-patches `fetch('/repos/open', {body: '{"path": "..."}'})` so that, on success, it `POST`s to `/repos/recent` in parallel;
  - injects a "Recent ▾" button into the `TopToolbar` via the DOM (event delegation, no React re-render);
  - opens a native HTML5 `<dialog>` listing `repos/recent` and a browsable text field.
- Keeps the bundle version, adds ~3 KB of vanilla JS.
- **Recommended** if you want to avoid touching the React toolchain.

**Option C — dedicated landing page `/repos.html`**:
- FastAPI serves a pure static HTML+JS page (no React) at `/repos.html`.
- This page calls the new endpoints and, on selection, navigates to `/` with the repo open.
- Clearly separates "switching" from "viewing".
- The React bundle stays untouched.

**Recommendation: C** (clear separation, no patch on the frozen bundle, landing page Python code ~150 LOC, pure JS ~80 LOC).

### 3.4 Target user workflow

1. The user opens `http://127.0.0.1:8088/`.
2. If no repo is open → FastAPI redirects to `/repos.html` (picker page).
3. The picker page shows:
   - **Recent** (up to 10) clickable.
   - **Browse**: "Root folder" input (default `~`), "Scan" button → list of git folders found.
   - **Manual**: absolute path input + "Open" button.
4. On selection → `POST /repos/open` → success → `window.location = '/'`.
5. In the main app, the `TopToolbar` keeps a "↩ Change repo" button that returns to `/repos.html`.

### 3.5 Persistence and lifecycle

- `~/.gitlane_recent.json` survives server restarts.
- The `RepoState` RAM cache is lost on restart (intentional — otherwise stale state). After a restart, `repos/current` points to the **last opened repo** if it was persisted (option: write `last_repo` in the same JSON).
- The WebSocket auto-refresh keeps working: the watcher (`services/watcher.py`) polls the current repo's `.git` every 2 s, and `routes_events.manager` broadcasts to connected clients.

---

## 4. Execution plan

### Phase 0 — preparation (1 h)
- [ ] Verify no build is broken by mounting `frontend/dist/` and serving `GET /` (already done: 200 OK).
- [ ] Inventory the absolute paths used by the tests so as not to break CI (see `tests/conftest.py:67`).

### Phase 1 — npm freeze (30 min)
- [ ] Commit `frontend/dist/` (git LFS or plain, ~165 KB — acceptable).
- [ ] Delete `frontend/src/`, `node_modules/`, `package*.json`, `vite.config.ts`, `tsconfig.json`, `tsconfig.tsbuildinfo`, `index.html` (frontend root).
- [ ] Update `.gitignore`: ignore `backend/.venv`, `**/__pycache__`, `**/.pytest_cache`, `frontend/dist/assets/*.map` (if any exist).
- [ ] Add `frontend/dist/README.md` explaining how to rebundle.

### Phase 2 — backend change-folder (2-3 h)
- [ ] Create `backend/app/services/recent.py` (JSON read/write, max 10, deduplication).
- [ ] Add `routes_recent.py` (`GET /repos/recent`, `POST /repos/recent`).
- [ ] Add `routes_browse.py` (`GET /repos/browse?root=&depth=`, `GET /repos/validate`).
- [ ] Extend `routes_repo.open_repo` to call `recent.add(path)` after success (1 line).
- [ ] Extend `routes_repo.current_repo` to re-read `last_repo` at startup (optional).
- [ ] Tests: `tests/test_recent.py` (JSON CRUD), `tests/test_browse.py` (fixture folder).
- [ ] CORS: verify that `/repos/recent`, `/repos/browse`, `/repos/validate` pass through (they are under `/repos/*` which is already covered).

### Phase 3 — frontend picker page (1-2 h)
- [ ] Create `backend/app/api/static/repos.html` (HTML5 + pure JS, ~80 LOC JS).
- [ ] The backend mounts this folder at `/static/repos/` via `app.mount` (before the root mount so it isn't shadowed by `dist/index.html`).
- [ ] Dedicated route `GET /picker` → returns `repos.html` (more descriptive than `/repos.html`).
- [ ] On `/`: if `cache.all_paths()` is empty and `repos/recent` is empty → `HTTP 307` redirect to `/picker`. Otherwise → serve `dist/index.html`.
- [ ] Tests: `tests/test_picker.py` (conditional redirect, HTML content).

### Phase 4 — UX polish (1 h)
- [ ] "↩ Change repo" button in the `TopToolbar` → link to `/picker`. **Implementation**: edit `frontend/src/app/App.tsx` (1 line), rebundle on a machine with node, re-commit `dist/`. OR use a runtime injection script (option B §3.3) if you want zero rebuild.
- [ ] Error handling: invalid path → clear message, no stack trace.
- [ ] "Scanning…" indicator on browse (slow folders).
- [ ] Keyboard shortcut `Ctrl+O` (or `Cmd+O`) that opens `/picker` (pure JS, ~10 LOC).

### Phase 4bis — premium graph rendering (✅ implemented 2026-09-01)
> Visual baseline: reference screenshot analyzed by Gemini (native macOS Git client — vitejs/vite, light theme, pastel swimlanes, GitHub-style diff stat).

**Backend** (extended API contract, backward compatible — optional fields):
- [x] `git_reader._read_diff_stats`: `git log --numstat` → `additions` / `deletions` per commit (called via `read_commits(..., with_stats=True)`).
- [x] `CommitItem`: new fields `additions`, `deletions`, `is_head`.
- [x] `lane_layout.LANE_COLORS`: 12-color saturated palette from the reference (magenta `#d6409f`, purple `#8e4ec6`, blue `#0091ff`, cyan `#00a2c7`, amber `#f5a623`, green `#30a46c`, red `#e5484d`…).
- [x] `NODE_R` 4.5 → 5.5 (more readable nodes).
- [x] `timeline_builder`: `adds` / `dels` aggregated per bucket → two-color sparkline.

**Frontend** (src/ + rebundle dist/):
- [x] `draw.ts`: two-pass lines (wide alpha glow then crisp stroke), "pearl" nodes (filled circle + 2px white ring + soft halo), merge = double ring, HEAD = donut ring, hover = radial gradient + selection ring.
- [x] `CommitRow`: row background tinted by lane color (`rgba(…, 0.10)` — the reference's pastel swimlane), zebra kept as fallback.
- [x] `RightMeta`: GitHub-style diff stat `+N −M` green/red + 5 proportional squares.
- [x] `MiniTimeline`: blue area under the envelope + green micro-bars (adds) / red (dels) + viewport.
- [x] `tokens.css`: system font (`-apple-system…`), borders `#e5e5ea`, updated accent palette.
- [x] `RefsPills`: SVG icons (branch / remote / tag) + refined pill colors.
- [x] Fix `DEFAULT_REPO` → `C:/Users/Dell/Desktop/MesProjets/gitlane` (the old path `…/gitlane/gitlane` no longer exists after the move).
- [x] Rebuild `dist/` (`index-Bj8ypHyz.js` + `index-CINZ1HwX.css`); bundle regenerated.

**Verifications**: `pytest` 23/23 green, `npm run build` OK, API verified (`+18 -1`, `is_head`, `r=5.5`, timeline `adds/dels`), assets served 200.

### Phase 5 — offline install + docs (1 h)
- [ ] Write `INSTALL.md` (conda procedure + offline pip download).
- [ ] Update `README.md`: new commands, removal of npm sections, link to `PLAN2.md`.
- [ ] Verify `pip download -r requirements.txt -d wheels/` works.
- [ ] `install_offline.sh` / `install_offline.bat` script that:
    1. creates the conda env,
    2. installs from `wheels/`,
    3. (optional) creates a desktop shortcut.

### Phase 6 — verifications (30 min)
- [ ] `pytest -q` → 11 + 12 + ~6 new tests = green.
- [ ] Launch `uvicorn`, open `http://127.0.0.1:8088/` → picker → selection → graph rendered.
- [ ] Change repo mid-session → refresh → new graph.
- [ ] Kill / restart uvicorn → recent repos still in `/repos/recent`.

---

## 5. Metrics & risks

### 5.1 Success metrics
- No `node`, `npm`, `npx` in the usage commands.
- `python -m uvicorn ...` + browser = full app.
- Repo switch in < 3 clicks (recent) or < 5 (browse).
- Recent repos persist after server restart.
- `pip download` + offline install = OK on Windows without network.

### 5.2 Known risks
| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| `frontend/dist/` turns out incomplete / buggy at runtime | Low (already verified: 200 OK) | High | Keep `package.json` + `package-lock.json` **outside the repo** but in a rebuild-doc bucket; test `GET /` on every delivery |
| `browse` scan too slow on large volumes | Medium | Medium | `depth=1` by default, max=3, don't follow symlinks, only scan `.git/HEAD` (cheap) |
| Cache conflict between repos | Low | Medium | Cache key = normalized path; no global TTL (each `open_repo` overwrites) |
| `~/.gitlane_recent.json` not writable | Low | Low | Try/except, log warning, continue without persistence |
| `tsc` unavailable to rebundle for a UI patch | Medium | Low | Minimize patches via option B (runtime injection) or C (separate page) — already in the plan |
| Existing tests break due to API changes | Low | Medium | Extend `routes_repo`, rename **nothing**; `open_repo` keeps its signature |

### 5.3 Out of scope (explicit)
- Rebundling the frontend **automatically** without node (impossible without altering the bundle or rewriting in pure JS — cost > value).
- Replacing React with a lighter framework (same — frozen bundle, no reason).
- Multi-user auth, network sharing of the cache (the project is single-user local).
- Sync between multiple PCs (`repos/recent.json` is per machine, by design).

---

## 6. Appendices

### 6.1 Files to delete (Phase 1)
```
frontend/src/                          (~1,294 LOC)
frontend/node_modules/                 (~150 MB)
frontend/package.json
frontend/package-lock.json
frontend/vite.config.ts
frontend/tsconfig.json
frontend/tsconfig.tsbuildinfo
frontend/index.html                    (replaced by dist/index.html)
```

### 6.2 Files to create
```
backend/app/services/recent.py         (~60 LOC)
backend/app/api/routes_recent.py       (~40 LOC)
backend/app/api/routes_browse.py       (~80 LOC)
backend/app/api/static/repos.html      (~120 LOC: 40 HTML + 80 JS)
backend/tests/test_recent.py           (~50 LOC)
backend/tests/test_browse.py           (~50 LOC)
backend/tests/test_picker.py           (~40 LOC)
INSTALL.md                             (doc)
frontend/dist/README.md                (rebundle procedure)
```

### 6.3 JSON schema `~/.gitlane_recent.json`
```json
{
  "v": 1,
  "last_repo": "C:\\Users\\Dell\\Desktop\\MesProjets\\gitlane",
  "items": [
    {"path": "C:\\Users\\Dell\\Desktop\\MesProjets\\gitlane", "name": "gitlane", "last_open": "2026-09-01T10:30:00Z"},
    {"path": "C:\\Users\\Dell\\Desktop\\MesProjets\\vintedge",  "name": "vintedge", "last_open": "2026-08-31T18:42:11Z"}
  ]
}
```

### 6.4 ASCII wireframe of the picker (`/picker`)
```
┌──────────────────────────────────────────────────────────┐
│ GitLane — choose a repository                            │
├──────────────────────────────────────────────────────────┤
│ Recent                                                   │
│   • gitlane        C:\Users\Dell\...\gitlane      [Open] │
│   • vintedge       C:\Users\Dell\...\vintedge     [Open] │
├──────────────────────────────────────────────────────────┤
│ Browse                                                   │
│   Root : [C:\Users\Dell\Desktop\MesProjets      ] [Scan] │
│   Depth : [1 ▾]                                          │
│   ┌──────────────────────────────────────────────────┐   │
│   │ ✓ dpds-analysis    C:\...\dpds-analysis  [Open]  │   │
│   │ ✓ gitlane          C:\...\gitlane        [Open]  │   │
│   │ ✓ gilda-analysis   C:\...\gilda-analysis [Open]  │   │
│   └──────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────┤
│ Manual                                                   │
│   Absolute path : [_____________________________] [Open] │
│   ⚠ Must be a git repository (`.git` subfolder present)  │
└──────────────────────────────────────────────────────────┘
```

### 6.5 Recommended reading order
1. `backend/app/main.py` (static mount + WS reject)
2. `backend/app/api/routes_repo.py` (`open_repo` = core of the change folder)
3. `backend/app/services/cache.py` (RAM cache per path)
4. `backend/app/services/watcher.py` (WS auto-refresh)
5. `backend/app/services/lane_layout.py` (the drawing engine on the backend side)
6. `frontend/dist/index.html` + bundle (the freeze)
