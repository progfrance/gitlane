# PLAN2.md — GitLane npm-free + change folder

> Vision : faire tourner **GitLane en zéro build** sur l'ordinateur de l'utilisateur (Python only via miniforge), et offrir un **sélecteur de dossier** pour basculer entre plusieurs repos sans relancer le serveur.

---

## 1. Analyse complète du projet existant

### 1.1 Cartographie du repo

| Zone | Fichiers | LOC | Rôle |
|---|---:|---:|---|
| `backend/app/main.py` | 1 | 58 | Entrypoint FastAPI, montage CORS + static |
| `backend/app/api/` | 4 routes | 293 | Endpoints REST + WebSocket |
| `backend/app/services/` | 5 modules | 603 | `git_reader`, `lane_layout`, `cache`, `watcher`, `timeline_builder` |
| `backend/app/models/` | 3 schémas | 107 | Pydantic v2 (commits, graph, repo) |
| `backend/tests/` | 3 fichiers | 376 | Pytest (lane layout + contrat API) |
| `backend/requirements.txt` | 1 | 5 | `fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx` |
| `frontend/src/**` | 17 fichiers | 1 294 | React 18 + TS + Canvas 2D (vite) |
| `frontend/dist/**` | 2 fichiers | ~155 KB JS + 6 KB CSS | **Build statique déjà compilé** |
| `frontend/package.json` + `package-lock.json` | 2 | 530+ | React, Vite, TypeScript, esbuild |
| `frontend/vite.config.ts` | 1 | 18 | Proxy `/repos /history /refs /api /events` vers `:8088` |

**Total source utile** : ~1 437 LOC Python + ~1 294 LOC TS/TSX/CSS.

### 1.2 Frontière npm (où se cache la dépendance)

Toute la chaîne npm tient en **2 maillons** :

1. **Build** : `tsc -b && vite build` → produit `frontend/dist/index.html + assets/`.
2. **Dev server** : `vite` (port 5173) avec proxy vers FastAPI (port 8088).

**Aucun de ces deux n'est indispensable** :
- Le build est déjà matérialisé sur disque (`frontend/dist/index-BZLGn9vk.js`, `index-D_9L7Hs1.css`).
- Le dev server ne sert qu'à re-bundler et proxifier — le backend FastAPI **sert déjà** `dist/` en mount racine quand il existe (`main.py:57-58`).

### 1.3 Routes API utiles au changement de folder

Le mécanisme "ouvrir un repo" existe déjà côté backend, il suffit d'en exposer l'usage côté UI.

| Endpoint | Méthode | Rôle | Réutilisable pour "change folder" ? |
|---|---|---|---|
| `/repos/open` | POST | `{"path": "..."}` → charge refs, commits, layout, met en cache | ✅ cœur de la feature |
| `/repos/current` | GET | Repo actuellement ouvert | ✅ pour restaurer l'état |
| `/repos/list` | **nouveau** | GET | Liste des derniers repos ouverts (depuis le cache) | 🆕 UX "récent" |
| `/repos/recent` | **nouveau** | GET | Persistance disque `~/.gitlane_recent.json` | 🆕 multi-session |
| `/repos/browse` | **nouveau** | GET | `?root=C:\Users` → dossiers git détectés 1 niveau | 🆕 picker |
| `/repos/validate` | **nouveau** | GET | `?path=...` → `{is_git, head, name}` sans ouvrir | 🆕 pré-check |

### 1.4 Test de l'existant

- `tests/test_lane_layout.py` : 183 LOC, 11 cas (linéaire, merge, branche longue, octopus, racines multiples, géométrie).
- `tests/test_api.py` : 126 LOC, 12 cas (open, history, refs, events, layout).
- `conftest.py` : 67 LOC (fixtures TestClient FastAPI).

Tout est **indépendant de npm** — pytest + httpx suffisent. Le frontend n'est jamais touché par les tests.

### 1.5 Sécurité actuelle (à préserver)

- `routes_repo.open_repo` : `os.path.isabs` + `os.path.isdir` + `git_reader.is_git_repo` avant `reload_state` → pas de shell, pas d'injection.
- `git_reader` : sous-processus `git` en argv fixe + timeout 15 s.
- Pas d'écriture disque côté backend hormis le cache en RAM (`services/cache.py`).

---

## 2. Stratégie npm-free (zéro build, zéro dev server)

### 2.1 Constat de départ

`frontend/dist/` est **déjà construit** sur ce PC (Vite 5 a produit un bundle minifié avec React 18 production inliné). Le bundle :
- n'a pas de source map externe ;
- charge `assets/index-*.js` (155 KB) + `assets/index-*.css` (6 KB) depuis `/assets/...` ;
- parle directement à `/repos`, `/history`, `/refs`, `/events`, `/api` sur le même origin.

Conséquence : **on peut supprimer tout `frontend/src/`, `node_modules/`, `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `tsconfig.tsbuildinfo`** sans casser le rendu, à condition de garder `frontend/dist/index.html` + `frontend/dist/assets/*`.

### 2.2 Option retenue : "frozen dist"

- **Garder** : `frontend/dist/` (artefact de build versionné, ~165 KB).
- **Supprimer** : `frontend/src/`, `frontend/node_modules/`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.tsbuildinfo`, `frontend/index.html` (le `index.html` racine est remplacé par celui de `dist/` au runtime).
- **Ajouter** : `frontend/dist/.gitkeep` au besoin + une note dans le README : "Pour re-builder le bundle, ouvrir un poste avec node ≥ 18 et lancer `npm run build` une fois."

### 2.3 Pourquoi pas réécrire le frontend en HTML/JS pur ?

- 1 294 LOC de TS/TSX, dont `GraphCanvas` (Canvas 2D avec bezier, virtual scroll, mini-timeline synchronisée) — pas trivial à réécrire à la main sans framework.
- Le bundle compilé est 155 KB minifié (≈ 50 KB gzippé) — dérisoire.
- Refactor = risque de régression élevé, gain réel faible.
- L'utilisateur a dit "je n'ai pas npm" pas "je veux un frontend différent". Préservons ce qui marche.

### 2.4 Ce qui reste sur la machine cible

```
gitlane/
├── backend/                # Python only
│   ├── app/                # FastAPI
│   ├── tests/              # pytest
│   ├── requirements.txt
│   └── .venv/              # créé à l'install
├── frontend/
│   └── dist/               # bundle statique pré-compilé (gelé)
├── PLAN.md                 # archive
├── PLAN2.md                # ce document
├── README.md               # à mettre à jour
└── .gitignore
```

**Total hors `.venv/`** : ~ 0,5 Mo. **Aucun exécutable node nécessaire** pour utiliser l'app.

### 2.5 Procédure d'install (miniforge, offline-friendly)

```bash
# 1. Créer l'env (une seule fois)
cd gitlane/backend
conda create -n gitlane python=3.13 -y
conda activate gitlane

# 2. Installer les deps (pip marche dans un env conda)
pip install -r requirements.txt

# 3. Lancer
python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
# → ouvrir http://127.0.0.1:8088
```

Si l'ordinateur cible est **strictement offline**, on peut :
- faire `pip download -r requirements.txt -d wheels/` sur un poste avec réseau ;
- copier le dossier `wheels/` ;
- `pip install --no-index --find-links=wheels/ -r requirements.txt`.

---

## 3. Feature "Change folder" — design

### 3.1 Principe

`POST /repos/open` existe déjà : il prend un chemin absolu, vérifie, charge, met en cache. Le frontend actuel **expose déjà** un input texte pour saisir ce chemin. Manque :
1. un **dialog de sélection** natif (parcourir l'arborescence locale sans ressaisir le chemin à la main) ;
2. un **historique persistant** des derniers repos ouverts ;
3. un **détecteur automatique** des dossiers git à proximité ;
4. un **raccourci** pour basculer sans recharger la page.

### 3.2 Côté backend (4 nouveaux endpoints, ~80 LOC)

#### `GET /repos/recent`
- Lit `~/.gitlane_recent.json` (max 10 entrées, dédupliquées, plus récent en tête).
- Retourne `[{"path": "...", "name": "...", "last_open": "ISO"}]`.
- 200 si absent (liste vide, ne pas 404).

#### `POST /repos/recent`
- Body `{"path": "..."}`.
- Pousse en tête, dédoublonne, tronque à 10, écrit le JSON.
- Idempotent.

#### `GET /repos/browse?root=<abs>&depth=<1-3>`
- `root` : chemin absolu de départ (ex. `C:\Users\Dell`).
- `depth` : 1 par défaut, max 3 (évite de scanner tout le disque).
- Parcourt les sous-dossiers, teste `is_git_repo(path)` à chaque niveau.
- Retourne `[{"path": "...", "name": "...", "head": "..."}]`.
- ⚠ Garde-fous : **pas d'erreur si root inexistant** (renvoie `[]`) ; `depth` borné à 3 ; pas de suivi des symlinks.

#### `GET /repos/validate?path=<abs>`
- Réutilise `git_reader.is_git_repo` + `git_reader.repo_name` + `git_reader.read_refs` (juste le `head`).
- Retourne `{is_git: bool, name: str|null, head: str|null}`.
- Sert à pré-valider avant l'ouverture, sans toucher au cache.

#### Fichier de stockage
- Chemin : `os.path.expanduser("~/.gitlane_recent.json")` — portable Win/Linux/macOS.
- Format : JSON, schéma libre, versionné `"v": 1` pour évoluer.

### 3.3 Côté frontend (modification du bundle dist gelé)

Le bundle est **gelé** par principe (cf. §2.2). Pour ajouter la feature sans rebuild :

**Option A — pré-bundler les modifs sur un poste avec node** :
- Modifier `frontend/src/app/App.tsx` + `TopToolbar.tsx` sur un poste qui a node.
- `npm run build` → nouveau `dist/`.
- Commiter le nouveau `dist/`.
- C'est l'option la plus propre ; on rebundle une fois et c'est figé.

**Option B — injection runtime via un script externe** (n'altère pas le bundle) :
- Ajouter un `<script src="/static/gitlane-patches.js">` chargé **après** le bundle React.
- Ce script :
  - monkey-patch `fetch('/repos/open', {body: '{"path": "..."}'})` pour, en cas de succès, `POST /repos/recent` en parallèle ;
  - injecte un bouton "Recent ▾" dans la `TopToolbar` via le DOM (event delegation, pas de re-render React) ;
  - ouvre un `<dialog>` natif HTML5 listant les `repos/recent` et un champ texte browseable.
- Conserve la version du bundle, ajoute ~3 KB de JS vanille.
- **Recommandé** si on veut éviter de toucher à la chaîne React.

**Option C — page d'accueil dédiée `/repos.html`** :
- FastAPI sert une page statique HTML+JS pure (pas de React) à `/repos.html`.
- Cette page appelle les nouveaux endpoints et, sur sélection, navigue vers `/` avec le repo ouvert.
- Sépare clairement "switcher" de "visualiser".
- Le bundle React reste intouché.

**Recommandation : C** (séparation claire, aucun patch sur le bundle gelé, code Python de la page d'accueil ~150 LOC, JS pur ~80 LOC).

### 3.4 Workflow utilisateur cible

1. L'utilisateur ouvre `http://127.0.0.1:8088/`.
2. Si aucun repo n'est ouvert → FastAPI redirige vers `/repos.html` (page picker).
3. La page picker affiche :
   - **Récents** (jusqu'à 10) cliquables.
   - **Browse** : input "Dossier racine" (par défaut `~`), bouton "Scanner" → liste git-dossiers trouvés.
   - **Manuel** : input chemin absolu + bouton "Ouvrir".
4. Sur sélection → `POST /repos/open` → succès → `window.location = '/'`.
5. Sur l'app principale, la `TopToolbar` garde un bouton "↩ Changer de repo" qui renvoie à `/repos.html`.

### 3.5 Persistance et cycle de vie

- `~/.gitlane_recent.json` survit aux redémarrages du serveur.
- Le cache `RepoState` en RAM est perdu au restart (volontaire — sinon état stale). Le `repos/current` après restart pointe vers le **dernier repo ouvert** si on l'a persisté (option : écrire `last_repo` dans le même JSON).
- L'auto-refresh WebSocket continue à fonctionner : le watcher (`services/watcher.py`) poll le `.git` du repo courant toutes les 2 s, et `routes_events.manager` broadcaste aux clients connectés.

---

## 4. Plan d'exécution

### Phase 0 — préparation (1 h)
- [ ] Vérifier qu'aucun build n'est cassé en montant `frontend/dist/` et en servant `GET /` (déjà fait : 200 OK).
- [ ] Recenser les chemins absolus que les tests utilisent pour ne pas casser la CI (cf. `tests/conftest.py:67`).

### Phase 1 — figeage npm (30 min)
- [ ] Commiter `frontend/dist/` (git LFS ou simple, ~165 KB — acceptable).
- [ ] Supprimer `frontend/src/`, `node_modules/`, `package*.json`, `vite.config.ts`, `tsconfig.json`, `tsconfig.tsbuildinfo`, `index.html` (racine frontend).
- [ ] Mettre à jour `.gitignore` : ignorer `backend/.venv`, `**/__pycache__`, `**/.pytest_cache`, `frontend/dist/assets/*.map` (s'il y en a).
- [ ] Ajouter `frontend/dist/README.md` expliquant comment re-bundler.

### Phase 2 — backend change-folder (2-3 h)
- [ ] Créer `backend/app/services/recent.py` (lecture/écriture JSON, max 10, déduplication).
- [ ] Ajouter `routes_recent.py` (`GET /repos/recent`, `POST /repos/recent`).
- [ ] Ajouter `routes_browse.py` (`GET /repos/browse?root=&depth=`, `GET /repos/validate`).
- [ ] Étendre `routes_repo.open_repo` pour appeler `recent.add(path)` après succès (1 ligne).
- [ ] Étendre `routes_repo.current_repo` pour relire `last_repo` au démarrage (option).
- [ ] Tests : `tests/test_recent.py` (CRUD JSON), `tests/test_browse.py` (dossier fixture).
- [ ] CORS : vérifier que `/repos/recent`, `/repos/browse`, `/repos/validate` passent (ils sont sous `/repos/*` qui est déjà couvert).

### Phase 3 — page picker frontend (1-2 h)
- [ ] Créer `backend/app/api/static/repos.html` (HTML5 + JS pur, ~80 LOC JS).
- [ ] Le backend monte ce dossier à `/static/repos/` via `app.mount` (avant le mount racine pour ne pas être masqué par `dist/index.html`).
- [ ] Route dédiée `GET /picker` → renvoie `repos.html` (plus parlant que `/repos.html`).
- [ ] Sur `/` : si `cache.all_paths()` est vide et `repos/recent` est vide → redirection `HTTP 307` vers `/picker`. Sinon → sert `dist/index.html`.
- [ ] Tests : `tests/test_picker.py` (redirection conditionnelle, contenu HTML).

### Phase 4 — UX polish (1 h)
- [ ] Bouton "↩ Changer de repo" dans la `TopToolbar` → lien vers `/picker`. **Implémentation** : modifier `frontend/src/app/App.tsx` (1 ligne), re-bundler sur un poste avec node, re-commiter `dist/`. OU utiliser un script d'injection runtime (option B §3.3) si on veut zéro rebuild.
- [ ] Gestion d'erreurs : chemin invalide → message clair, pas de stack trace.
- [ ] Indicateur "Scanning…" sur le browse (dossiers lents).
- [ ] Raccourci clavier `Ctrl+O` (ou `Cmd+O`) qui ouvre `/picker` (JS pur, ~10 LOC).

### Phase 4bis — rendu graphique premium (✅ implémentée 2026-09-01)
> Baseline visuelle : capture de référence analysée par Gemini (client Git macOS natif — vitejs/vite, thème clair, swimlanes pastel, diff stat GitHub-style).

**Backend** (contrat API étendu, rétrocompatible — champs optionnels) :
- [x] `git_reader._read_diff_stats` : `git log --numstat` → `additions` / `deletions` par commit (appelé via `read_commits(..., with_stats=True)`).
- [x] `CommitItem` : nouveaux champs `additions`, `deletions`, `is_head`.
- [x] `lane_layout.LANE_COLORS` : palette 12 teintes saturées de la référence (magenta `#d6409f`, violet `#8e4ec6`, bleu `#0091ff`, cyan `#00a2c7`, ambre `#f5a623`, vert `#30a46c`, rouge `#e5484d`…).
- [x] `NODE_R` 4.5 → 5.5 (nœuds plus lisibles).
- [x] `timeline_builder` : `adds` / `dels` agrégés par bucket → sparkline bicolore.

**Frontend** (src/ + rebundle dist/) :
- [x] `draw.ts` : lignes 2 passes (glow alpha large puis trait net), nœuds "perle" (cercle plein + anneau blanc 2px + halo doux), merge = double anneau, HEAD = donut ring, hover = dégradé radial + anneau de sélection.
- [x] `CommitRow` : fond de ligne teinté par la couleur de lane (`rgba(…, 0.10)` — swimlane pastel de la référence), zebra conservé en fallback.
- [x] `RightMeta` : diff stat GitHub-style `+N −M` vert/rouge + 5 carrés proportionnels.
- [x] `MiniTimeline` : aire bleue sous l'enveloppe + micro-barres vertes (adds) / rouges (dels) + viewport.
- [x] `tokens.css` : police système (`-apple-system…`), bordures `#e5e5ea`, palette accents mise à jour.
- [x] `RefsPills` : icônes SVG (branche / remote / tag) + couleurs pills raffinées.
- [x] Fix `DEFAULT_REPO` → `C:/Users/Dell/Desktop/MesProjets/gitlane` (l'ancien chemin `…/gitlane/gitlane` n'existe plus après le déplacement).
- [x] Rebuild `dist/` (`index-Bj8ypHyz.js` + `index-CINZ1HwX.css`) ; bundle regénéré.

**Vérifications** : `pytest` 23/23 verts, `npm run build` OK, API vérifiée (`+18 -1`, `is_head`, `r=5.5`, timeline `adds/dels`), assets servis 200.

### Phase 5 — install offline + doc (1 h)
- [ ] Rédiger `INSTALL.md` (procédure conda + pip download offline).
- [ ] Mettre à jour `README.md` : nouvelles commandes, retrait des sections npm, lien vers `PLAN2.md`.
- [ ] Vérifier `pip download -r requirements.txt -d wheels/` fonctionne.
- [ ] Script `install_offline.sh` / `install_offline.bat` qui :
    1. crée l'env conda,
    2. installe depuis `wheels/`,
    3. (optionnel) crée un raccourci bureau.

### Phase 6 — vérifications (30 min)
- [ ] `pytest -q` → 11 + 12 + ~6 nouveaux tests = vert.
- [ ] Lancer `uvicorn`, ouvrir `http://127.0.0.1:8088/` → picker → sélection → graphe rendu.
- [ ] Changer de repo en cours de session → refresh → nouveau graphe.
- [ ] Tuer / relancer uvicorn → derniers repos toujours dans `/repos/recent`.

---

## 5. Métriques & risques

### 5.1 Métriques de succès
- Aucun `node`, `npm`, `npx` dans les commandes d'utilisation.
- `python -m uvicorn ...` + navigateur = app complète.
- Changement de repo en < 3 clics (récent) ou < 5 (browse).
- Persistance des récents après redémarrage du serveur.
- `pip download` + install offline = OK sur Windows sans réseau.

### 5.2 Risques connus
| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| `frontend/dist/` se révèle incomplet / bugué en runtime | Faible (déjà vérifié : 200 OK) | Élevé | Garder `package.json` + `package-lock.json` **hors repo** mais dans un bucket de rebuild doc ; tester le `GET /` à chaque livraison |
| Scan `browse` trop lent sur gros volumes | Moyen | Moyen | `depth=1` par défaut, max=3, ne pas suivre symlinks, ne scanner que `.git/HEAD` (cheap) |
| Conflit de cache entre repos | Faible | Moyen | Clé de cache = path normalisé ; pas de TTL global (chaque `open_repo` écrase) |
| `~/.gitlane_recent.json` non writable | Faible | Faible | Try/except, log warning, continuer sans persistance |
| `tsc` indisponible pour re-bundler en cas de patch UI | Moyen | Faible | Minimiser les patches via option B (injection runtime) ou C (page séparée) — déjà dans le plan |
| Tests existants cassent par changement d'API | Faible | Moyen | Étendre `routes_repo`, ne **rien renommer** ; `open_repo` garde sa signature |

### 5.3 Hors scope (explicite)
- Re-bundler le frontend **automatiquement** sans node (impossible sans altérer le bundle ou réécrire en JS pur — coût > valeur).
- Remplacer React par un framework plus léger (idem — bundle gelé, pas de raison).
- Auth multi-utilisateurs, partage réseau du cache (le projet est mono-utilisateur local).
- Synchronisation entre plusieurs PC (le `repos/recent.json` est par machine, c'est voulu).

---

## 6. Annexes

### 6.1 Inventaire des fichiers à supprimer (Phase 1)
```
frontend/src/                          (~1 294 LOC)
frontend/node_modules/                 (~150 Mo)
frontend/package.json
frontend/package-lock.json
frontend/vite.config.ts
frontend/tsconfig.json
frontend/tsconfig.tsbuildinfo
frontend/index.html                    (remplacé par dist/index.html)
```

### 6.2 Inventaire des fichiers à créer
```
backend/app/services/recent.py         (~60 LOC)
backend/app/api/routes_recent.py       (~40 LOC)
backend/app/api/routes_browse.py       (~80 LOC)
backend/app/api/static/repos.html      (~120 LOC : 40 HTML + 80 JS)
backend/tests/test_recent.py           (~50 LOC)
backend/tests/test_browse.py           (~50 LOC)
backend/tests/test_picker.py           (~40 LOC)
INSTALL.md                             (doc)
frontend/dist/README.md                (procédure de re-bundle)
```

### 6.3 Schéma JSON `~/.gitlane_recent.json`
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

### 6.4 Wireframe ASCII du picker (`/picker`)
```
┌──────────────────────────────────────────────────────────┐
│ GitLane — choisir un dépôt                               │
├──────────────────────────────────────────────────────────┤
│ Récents                                                  │
│   • gitlane        C:\Users\Dell\...\gitlane    [Ouvrir] │
│   • vintedge       C:\Users\Dell\...\vintedge   [Ouvrir] │
├──────────────────────────────────────────────────────────┤
│ Browse                                                   │
│   Racine : [C:\Users\Dell\Desktop\MesProjets    ] [Scan] │
│   Profondeur : [1 ▾]                                     │
│   ┌──────────────────────────────────────────────────┐   │
│   │ ✓ dpds-analysis    C:\...\dpds-analysis  [Ouvrir] │   │
│   │ ✓ gitlane          C:\...\gitlane        [Ouvrir] │   │
│   │ ✓ gilda-analysis   C:\...\gilda-analysis [Ouvrir] │   │
│   └──────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────┤
│ Manuel                                                   │
│   Chemin absolu : [_____________________________] [Ouvrir]│
│   ⚠ Doit être un dépôt git (sous-dossier `.git` présent)  │
└──────────────────────────────────────────────────────────┘
```

### 6.5 Ordre de lecture recommandé
1. `backend/app/main.py` (montage static + WS reject)
2. `backend/app/api/routes_repo.py` (`open_repo` = cœur du change folder)
3. `backend/app/services/cache.py` (cache RAM par path)
4. `backend/app/services/watcher.py` (auto-refresh WS)
5. `backend/app/services/lane_layout.py` (le moteur de dessin côté backend)
6. `frontend/dist/index.html` + bundle (le gel)
