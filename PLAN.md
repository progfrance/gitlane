# PLAN.md — Visualiseur Git Web (Python) avec rendu "swimlanes" ultra fidèle

> Document autonome pour un agent **non multimodal** (sans accès image).
> 
> Objectif: implémenter une application web-only qui reproduit un rendu de client Git visuel **dense, clair, coloré, professionnel**, avec graphe de commits en swimlanes pastel, mini-timeline en haut, et métadonnées alignées à droite.

---

## 1) Cible produit (résumé exécutable)

Construire un outil web local qui:

- ouvre un dépôt Git local,
- lit son historique,
- calcule un layout de graphe en lanes,
- rend une interface compacte type "table + graphe intégré",
- reste fluide sur gros historiques.

### 1.1 Must-have v1

1. Ouverture d'un repo local.
2. Liste des commits virtualisée (dense).
3. Graphe en swimlanes colorées avec merges/forks lisibles.
4. Badges refs (local branch, remote, tag, HEAD).
5. Colonne droite: date relative, SHA court, status dots.
6. Mini timeline horizontale en haut.
7. Recherche instantanée (message/sha/auteur/ref).
8. Refresh auto quand le repo change.

### 1.2 Hors périmètre v1

- Pas de merge/rebase/reset UI.
- Pas d'intégration PR cloud.
- Pas de conflit editor.

---

## 2) Description visuelle cible (sans image)

Cette section est la référence visuelle à respecter strictement.

### 2.1 Impression générale

- Interface en **thème clair** (pas dark par défaut).
- Fond global légèrement gris-bleu.
- Panneaux blancs avec bordures fines.
- Densité élevée: beaucoup de commits visibles en même temps.
- Design net, orienté productivité, sans effet gadget.

### 2.2 Structure de l'écran

L'écran est organisé en 3 bandes verticales + un bandeau haut:

1. **Toolbar** en haut (environ 48 px).
2. **Mini timeline** juste dessous (environ 56 px, dont 40 px utiles).
3. **Zone principale** occupant le reste:
   - zone gauche pour message/filtres,
   - zone centrale pour graphe lanes,
   - zone droite pour méta (temps/SHA/status).

### 2.3 Densité lignes

- Hauteur de ligne commit: **32 px** par défaut.
- Option confortable: 36 px.
- Padding horizontal cellules: 10 à 12 px.
- Texte compact et tronqué proprement (ellipsis).

### 2.4 Swimlanes

- Multiples lanes colorées pastel visibles simultanément.
- Traits principalement verticaux.
- Courbes douces pour merges/forks (bezier), pas d'angles cassés.
- Nœuds commit centrés sur chaque ligne.
- Couleurs stables lane-to-lane.

### 2.5 Informations dans chaque ligne

- Message commit principal (1 ligne tronquée).
- Badges refs arrondis (pills).
- Avatar auteur (petit cercle).
- Date relative (ex: "3 hours ago").
- SHA court monospace.
- Statuts par petits points colorés.

### 2.6 Mini timeline haut

- Tracé d'activité fin, style sparkline/histogramme doux.
- Couleurs discrètes cohérentes avec lanes.
- Vue globale de l'historique.
- Rectangle viewport pour indiquer la fenêtre visible actuelle.

---

## 3) Design System détaillé

## 3.1 Couleurs (tokens obligatoires)

```css
:root {
  --bg-app: #f6f8fb;
  --bg-panel: #ffffff;
  --bg-row-even: #fbfcfe;
  --bg-row-hover: #eef5ff;
  --bg-row-selected: #e2efff;
  --border-soft: #e6eaf1;

  --text-main: #1f2937;
  --text-secondary: #6b7280;
  --text-muted: #94a3b8;

  --ok: #22c55e;
  --fail: #ef4444;
  --warn: #f59e0b;
  --info: #3b82f6;

  --lane-1: #f79ac0;
  --lane-2: #8dd3ff;
  --lane-3: #9ee6b5;
  --lane-4: #ffd48a;
  --lane-5: #c3b6ff;
  --lane-6: #ffb2a6;
  --lane-7: #94e2d5;
  --lane-8: #b7e48a;
  --lane-9: #f6b0e5;
  --lane-10: #a0c4ff;
  --lane-11: #ffd6a5;
  --lane-12: #caffbf;
}
```

## 3.2 Typographie

- UI: `Manrope`, fallback `Segoe UI`, sans-serif.
- Tech (SHA): `JetBrains Mono`, fallback `Consolas`, monospace.
- Tailles:
  - toolbar: 12-13 px
  - message commit: 12.5-13 px
  - méta/date: 11-12 px
  - badges refs: 10.5-11 px

## 3.3 Espacements et effets

- Grille 4 px: 4/8/12/16.
- Radius panneaux: 10 px.
- Ombre légère panneaux: `0 1px 2px rgba(16,24,40,.06)`.
- Bordure: 1 px `--border-soft`.
- Pas de blur lourd.

---

## 4) Spécification composants UI

## 4.1 TopToolbar

Contenu de gauche à droite:

1. Nom repo + icône.
2. Branche courante (pill).
3. Filtres / scope refs.
4. Recherche.
5. Actions légères (refresh, settings).

Règles:

- Hauteur 48 px.
- Fond blanc.
- Border-bottom fine.
- Contrôles compacts, pas de boutons volumineux.

## 4.2 MiniTimeline

- Hauteur conteneur 56 px.
- Zone dessin ~40 px centrée verticalement.
- Tracé activité: ligne fine (1-1.5 px) + petits pics.
- Viewport rectangle: fond alpha faible + contour bleu clair.
- Scroll de la liste doit mettre à jour ce viewport.

## 4.3 CommitTable intégrée au graphe

Chaque row contient visuellement:

1. Zone lanes (gauche/centre)
2. Message commit
3. Badges refs
4. Avatar auteur
5. Date relative
6. SHA court
7. Status dots

Comportements:

- hover row: fond `--bg-row-hover`, nœud commit avec halo léger.
- selected row: fond `--bg-row-selected` + accent vertical bleu.
- alternance discrète pair/impair.

## 4.4 RefsPills

Styles:

- Border radius 999 px.
- Padding `2px 8px`.
- Border 1 px.
- Font 10.5-11 px, weight 600.

Mapping:

- local branch: fond vert très pâle, texte vert foncé.
- remote branch: fond bleu pâle, texte bleu foncé.
- tag: fond orange pâle, texte orange foncé.
- HEAD/current: contour accent + dot.

## 4.5 Avatars

- Diamètre 16 px.
- Cercle.
- Border `1px #fff`.
- Ombre minime.
- Fallback initiales.

## 4.6 RightMeta

- Date relative: texte secondaire.
- SHA court: monospace.
- Status dots:
  - diamètre 6 px,
  - gap 4 px,
  - 3 à 5 points,
  - vert/rouge/gris.

---

## 5) Rendu Canvas du graphe (obligatoire)

## 5.1 Pourquoi Canvas

- Plus fluide que SVG pour grands historiques.
- Contrôle fin des traits et overlays.

## 5.2 Dimensions recommandées

- Ecart lane: 18 à 22 px.
- Width trait lane: 2 px.
- Nœud commit: diamètre 8-10 px, centre 3 px.

## 5.3 Couches de rendu (ordre)

1. Fond rows alternées.
2. Segments lanes (vertical + courbes).
3. Nœuds commits.
4. Hover/selected overlay.
5. Décorations (si besoin).

## 5.4 Paramètres de dessin

- `lineCap = round`
- `lineJoin = round`
- Gestion `devicePixelRatio` pour netteté.
- Courbes via bezier pour forks/merges.

---

## 6) Backend Python — architecture

## 6.1 Modules

```text
backend/
  app/
    api/
      routes_repo.py
      routes_history.py
      routes_refs.py
      routes_events.py
    services/
      git_reader.py
      lane_layout.py
      timeline_builder.py
      cache.py
      watcher.py
    models/
      repo.py
      commit.py
      graph.py
    main.py
  tests/
```

## 6.2 Rôle des services

- `git_reader.py`: extraction commits/parents/refs/auteurs.
- `lane_layout.py`: attribution lanes + segments.
- `timeline_builder.py`: données agrégées mini timeline.
- `cache.py`: cache LRU par repo/query.
- `watcher.py`: surveillance `.git` + events websocket.

---

## 7) Modèle de données API (contrat strict)

## 7.1 Open repo

`POST /repos/open`

Request:

```json
{ "path": "C:/absolute/path/to/repo" }
```

Response:

```json
{
  "ok": true,
  "repo": {
    "name": "my-repo",
    "path": "C:/absolute/path/to/repo",
    "head": "main"
  }
}
```

## 7.2 History

`GET /history?cursor=&limit=&q=&ref=`

Response item minimal:

```json
{
  "sha": "abcdef1234567890",
  "short_sha": "abcdef1",
  "message_subject": "fix: improve lane paint",
  "author_name": "Alice",
  "author_email": "alice@example.com",
  "author_avatar_url": null,
  "timestamp": 1720000000,
  "relative_time": "3 hours ago",
  "parents": ["123...", "456..."],
  "refs": [
    { "type": "local_branch", "name": "main" },
    { "type": "remote_branch", "name": "origin/main" }
  ],
  "lane_index": 2,
  "node": {
    "x": 124,
    "y": 16,
    "r": 4.5,
    "color": "#8dd3ff"
  },
  "segments": [
    {
      "type": "vertical",
      "x1": 124,
      "y1": 0,
      "x2": 124,
      "y2": 32,
      "color": "#8dd3ff",
      "w": 2
    }
  ],
  "status_checks": ["success", "success", "failed"]
}
```

Envelope:

```json
{
  "items": ["..."],
  "next_cursor": "opaque_cursor",
  "has_more": true
}
```

## 7.3 Refs

`GET /refs`

Retourne branches locales, remotes, tags, HEAD.

## 7.4 Events

`WS /events`

Events:

- `repo_updated`
- `head_changed`
- `new_commit`

---

## 8) Algorithme lanes (détaillé)

## 8.1 Objectif

Produire un graphe lisible et stable entre refresh/pagination.

## 8.2 Étapes

1. Charger commits en ordre topologique (secondairement par date).
2. Maintenir structure `active_lanes`.
3. Pour chaque commit:
   - si lane déjà réservée: réutiliser,
   - sinon prendre la lane libre la plus à gauche.
4. Dessiner segment vertical lane courante.
5. Parent principal:
   - prolonger lane.
6. Parents secondaires:
   - créer courbes vers lane parent.
7. Libérer lanes inactives.
8. Persister mapping lane sur fenêtre pour stabilité.

## 8.3 Contraintes visuelles du layout

- Minimiser croisements.
- Eviter oscillation lane d'un commit à l'autre.
- Prioriser continuité de la branche principale.

## 8.4 Jeux de tests layout

- linéaire simple,
- 1 merge,
- branche longue puis merge,
- octopus merge,
- racine multiple,
- dense refs.

---

## 9) Frontend — architecture

## 9.1 Structure

```text
frontend/
  src/
    app/
      App.tsx
      layout/
    components/
      TopToolbar.tsx
      MiniTimeline.tsx
      CommitTable.tsx
      CommitRow.tsx
      RefsPills.tsx
      RightMeta.tsx
    graph/
      GraphCanvas.tsx
      draw.ts
      coords.ts
    store/
      useRepoStore.ts
    api/
      client.ts
    styles/
      tokens.css
      app.css
```

## 9.2 Responsabilités

- `GraphCanvas`: rendu lanes/nœuds.
- `CommitTable`: virtualisation + synchronisation scroll.
- `MiniTimeline`: overview + viewport.
- `store`: état sélection, filtres, data pages.

---

## 10) UX interactions obligatoires

1. Scroll fluide (liste + graphe synchronisés).
2. Hover commit met en évidence row + nœud.
3. Click commit sélectionne row.
4. Recherche en direct avec highlight.
5. Auto-refresh non intrusif sur nouveaux commits.

### 10.1 Raccourcis clavier v1

- `j` / `k`: commit suivant/précédent.
- `/`: focus recherche.
- `enter`: ouvrir panneau détail (ou noop v1).
- `esc`: clear recherche.

---

## 11) Performance budget

- Payload initial `/history` (300 commits): < 1.2 MB compressé.
- Temps premier rendu utile: < 2.5 s repo moyen.
- Scroll perçu: 55-60 fps cible.
- Budget draw frame: < 8-10 ms.

Optimisations:

- virtualisation rows,
- mémoïsation des segments,
- découpage en pages (300 + prefetch 100),
- cache backend LRU,
- debounce recherche (100-150 ms).

---

## 12) Tests et QA

## 12.1 Backend

- Unit tests `lane_layout.py`.
- Contract tests API (pydantic).
- Snapshot JSON segments.

## 12.2 Frontend

- Unit tests formatters.
- Tests de rendu canvas (smoke + snapshots).
- E2E Playwright:
  - open repo,
  - scroll,
  - select,
  - search,
  - refresh après nouveau commit.

## 12.3 Visuel (acceptation)

- Comparer captures aux critères section 2/3.
- Valider densité, couleurs, alignements, lisibilité.

---

## 13) Plan d'exécution par phases

## Phase A (S1) — Fondations

Livrables:

- Backend FastAPI opérationnel.
- Ouverture repo local.
- Endpoint history brut.
- Front list simple.

Done si:

- on voit commits texte sans crash.

## Phase B (S2-S3) — Moteur lanes

Livrables:

- lane allocator,
- segments graph,
- API history enrichie,
- tests unitaires layout.

Done si:

- cas merges/forks corrects.

## Phase C (S4-S5) — Fidélité visuelle

Livrables:

- layout complet toolbar/timeline/main,
- canvas multicouches,
- refs pills, avatars, right meta,
- thème pastel compact.

Done si:

- rendu visuellement conforme à cette spec.

## Phase D (S6) — Interactions + perf

Livrables:

- virtual scroll sync,
- recherche live,
- websocket updates,
- optimisation draw.

Done si:

- fluidité satisfaisante gros repo.

## Phase E (S7) — QA/polish

Livrables:

- états loading/error/empty,
- responsive,
- e2e,
- docs run/deploy.

Done si:

- checklist finale validée.

---

## 14) Checklist finale bloquante (Go/No-Go)

- [ ] Thème clair compact conforme.
- [ ] Toolbar + mini timeline présents.
- [ ] Swimlanes pastel courbes lisibles.
- [ ] Rows denses (32 px) et stables.
- [ ] Refs pills colorées bien typées.
- [ ] Avatar + date + SHA + status dots visibles par ligne.
- [ ] Recherche instantanée utilisable.
- [ ] Refresh auto sans rupture d'UX.
- [ ] Performance acceptable sur gros historique.
- [ ] Code testé (unit + e2e minimal).

---

## 15) Déploiement et exécution

## 15.1 Dev

- Backend: `uvicorn app.main:app --reload`
- Frontend: `npm run dev` (ou `pnpm`, `bun` selon choix)

## 15.2 Prod

- Build frontend statique + reverse proxy vers API.
- Option Docker Compose (api + web).

---

## 16) Sécurité / robustesse

- Valider chemin repo (pas traversal).
- Timeout sur fallback CLI git.
- Pas d'exécution shell arbitraire depuis UI.
- Gestion erreurs repo corrompu / permission refusée.

---

## 17) Consignes directes pour l'agent implémenteur

1. Respecter strictement cette spec visuelle.
2. Prioriser lisibilité du graphe avant features annexes.
3. Utiliser Canvas + virtualisation obligatoirement.
4. Produire commits atomiques par phase.
5. Après chaque phase, fournir:
   - fonctionnalités livrées,
   - captures,
   - écarts vs PLAN.md,
   - plan de correction.

---

## 18) Définition de réussite finale

Le résultat est validé si un utilisateur perçoit immédiatement:

- un visualiseur Git "swimlanes" dense et pro,
- une lecture claire des branches/merges,
- un rendu compact, pastel, informatif,
- et une fluidité suffisante pour usage quotidien.
