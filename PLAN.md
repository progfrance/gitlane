# PLAN.md — Web Git Visualizer (Python) with ultra-faithful "swimlanes" rendering

> Standalone document for a **non-multimodal** agent (no image access).
> 
> Objective: implement a web-only application that reproduces a visual Git client rendering that is **dense, clear, colorful, and professional**, with a pastel swimlane commit graph, a mini timeline at the top, and metadata aligned to the right.

---

## 1) Product target (executable summary)

Build a local web tool that:

- opens a local Git repository,
- reads its history,
- computes a lane-based graph layout,
- renders a compact "table + integrated graph" interface,
- stays fluid on large histories.

### 1.1 Must-have v1

1. Opening a local repo.
2. Virtualized (dense) commit list.
3. Colored swimlane graph with readable merges/forks.
4. Ref badges (local branch, remote, tag, HEAD).
5. Right column: relative date, short SHA, status dots.
6. Horizontal mini timeline at the top.
7. Instant search (message/sha/author/ref).
8. Auto refresh when the repo changes.

### 1.2 Out of scope v1

- No merge/rebase/reset UI.
- No cloud PR integration.
- No conflict editor.

---

## 2) Target visual description (without image)

This section is the visual reference to be strictly followed.

### 2.1 General impression

- **Light theme** interface (not dark by default).
- Overall background slightly gray-blue.
- White panels with thin borders.
- High density: many commits visible at the same time.
- Clean, productivity-oriented design, no gimmick effects.

### 2.2 Screen structure

The screen is organized into 3 vertical bands + a top banner:

1. **Toolbar** at the top (about 48 px).
2. **Mini timeline** just below (about 56 px, of which 40 px usable).
3. **Main area** occupying the rest:
   - left zone for message/filters,
   - central zone for the lane graph,
   - right zone for meta (time/SHA/status).

### 2.3 Row density

- Commit row height: **32 px** by default.
- Comfortable option: 36 px.
- Horizontal cell padding: 10 to 12 px.
- Compact text cleanly truncated (ellipsis).

### 2.4 Swimlanes

- Multiple pastel colored lanes visible simultaneously.
- Lines primarily vertical.
- Smooth curves for merges/forks (bezier), no broken angles.
- Commit nodes centered on each row.
- Colors stable lane-to-lane.

### 2.5 Information in each row

- Main commit message (1 truncated line).
- Rounded ref badges (pills).
- Author avatar (small circle).
- Relative date (e.g. "3 hours ago").
- Monospace short SHA.
- Statuses as small colored dots.

### 2.6 Top mini timeline

- Thin activity trace, soft sparkline/histogram style.
- Discreet colors consistent with the lanes.
- Global overview of the history.
- Viewport rectangle indicating the current visible window.

---

## 3) Detailed Design System

## 3.1 Colors (mandatory tokens)

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

## 3.2 Typography

- UI: `Manrope`, fallback `Segoe UI`, sans-serif.
- Tech (SHA): `JetBrains Mono`, fallback `Consolas`, monospace.
- Sizes:
  - toolbar: 12-13 px
  - commit message: 12.5-13 px
  - meta/date: 11-12 px
  - ref badges: 10.5-11 px

## 3.3 Spacing and effects

- 4 px grid: 4/8/12/16.
- Panel radius: 10 px.
- Light panel shadow: `0 1px 2px rgba(16,24,40,.06)`.
- Border: 1 px `--border-soft`.
- No heavy blur.

---

## 4) UI component specification

## 4.1 TopToolbar

Contents from left to right:

1. Repo name + icon.
2. Current branch (pill).
3. Filters / ref scope.
4. Search.
5. Light actions (refresh, settings).

Rules:

- Height 48 px.
- White background.
- Thin border-bottom.
- Compact controls, no bulky buttons.

## 4.2 MiniTimeline

- Container height 56 px.
- Drawing zone ~40 px centered vertically.
- Activity trace: thin line (1-1.5 px) + small peaks.
- Viewport rectangle: low-alpha fill + light blue outline.
- Scrolling the list must update this viewport.

## 4.3 CommitTable integrated with the graph

Each row visually contains:

1. Lane zone (left/center)
2. Commit message
3. Ref badges
4. Author avatar
5. Relative date
6. Short SHA
7. Status dots

Behaviors:

- hover row: background `--bg-row-hover`, commit node with a light halo.
- selected row: background `--bg-row-selected` + vertical blue accent.
- discreet even/odd alternation.

## 4.4 RefsPills

Styles:

- Border radius 999 px.
- Padding `2px 8px`.
- Border 1 px.
- Font 10.5-11 px, weight 600.

Mapping:

- local branch: very pale green background, dark green text.
- remote branch: pale blue background, dark blue text.
- tag: pale orange background, dark orange text.
- HEAD/current: accent outline + dot.

## 4.5 Avatars

- Diameter 16 px.
- Circle.
- Border `1px #fff`.
- Minimal shadow.
- Initials fallback.

## 4.6 RightMeta

- Relative date: secondary text.
- Short SHA: monospace.
- Status dots:
  - diameter 6 px,
  - gap 4 px,
  - 3 to 5 dots,
  - green/red/gray.

---

## 5) Canvas rendering of the graph (mandatory)

## 5.1 Why Canvas

- Smoother than SVG for large histories.
- Fine control of lines and overlays.

## 5.2 Recommended dimensions

- Lane spacing: 18 to 22 px.
- Lane line width: 2 px.
- Commit node: diameter 8-10 px, center 3 px.

## 5.3 Rendering layers (order)

1. Alternating row backgrounds.
2. Lane segments (vertical + curves).
3. Commit nodes.
4. Hover/selected overlay.
5. Decorations (if needed).

## 5.4 Drawing parameters

- `lineCap = round`
- `lineJoin = round`
- `devicePixelRatio` handling for sharpness.
- Curves via bezier for forks/merges.

---

## 6) Python backend — architecture

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

## 6.2 Role of the services

- `git_reader.py`: extraction of commits/parents/refs/authors.
- `lane_layout.py`: lane assignment + segments.
- `timeline_builder.py`: aggregated data for the mini timeline.
- `cache.py`: LRU cache per repo/query.
- `watcher.py`: `.git` watching + websocket events.

---

## 7) API data model (strict contract)

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

Minimal response item:

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

Returns local branches, remotes, tags, HEAD.

## 7.4 Events

`WS /events`

Events:

- `repo_updated`
- `head_changed`
- `new_commit`

---

## 8) Lane algorithm (detailed)

## 8.1 Objective

Produce a graph that is readable and stable across refresh/pagination.

## 8.2 Steps

1. Load commits in topological order (secondary sort by date).
2. Maintain an `active_lanes` structure.
3. For each commit:
   - if a lane is already reserved: reuse it,
   - otherwise take the leftmost free lane.
4. Draw the vertical segment of the current lane.
5. Primary parent:
   - extend the lane.
6. Secondary parents:
   - create curves toward the parent lane.
7. Release inactive lanes.
8. Persist the lane mapping over the window for stability.

## 8.3 Visual constraints of the layout

- Minimize crossings.
- Avoid lane oscillation from one commit to the next.
- Prioritize continuity of the main branch.

## 8.4 Layout test datasets

- simple linear,
- 1 merge,
- long branch then merge,
- octopus merge,
- multiple roots,
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

## 9.2 Responsibilities

- `GraphCanvas`: rendering of lanes/nodes.
- `CommitTable`: virtualization + scroll synchronization.
- `MiniTimeline`: overview + viewport.
- `store`: selection state, filters, data pages.

---

## 10) Mandatory UX interactions

1. Smooth scroll (list + graph synchronized).
2. Hovering a commit highlights the row + node.
3. Clicking a commit selects the row.
4. Live search with highlighting.
5. Non-intrusive auto-refresh on new commits.

### 10.1 Keyboard shortcuts v1

- `j` / `k`: next/previous commit.
- `/`: focus search.
- `enter`: open detail panel (or noop in v1).
- `esc`: clear search.

---

## 11) Performance budget

- Initial `/history` payload (300 commits): < 1.2 MB compressed.
- First meaningful render time: < 2.5 s on an average repo.
- Perceived scroll: 55-60 fps target.
- Frame draw budget: < 8-10 ms.

Optimizations:

- row virtualization,
- segment memoization,
- pagination (300 + prefetch 100),
- backend LRU cache,
- search debounce (100-150 ms).

---

## 12) Tests and QA

## 12.1 Backend

- Unit tests for `lane_layout.py`.
- API contract tests (pydantic).
- JSON snapshots of segments.

## 12.2 Frontend

- Unit tests for formatters.
- Canvas rendering tests (smoke + snapshots).
- Playwright E2E:
  - open repo,
  - scroll,
  - select,
  - search,
  - refresh after a new commit.

## 12.3 Visual (acceptance)

- Compare screenshots against the criteria in sections 2/3.
- Validate density, colors, alignments, readability.

---

## 13) Phase-by-phase execution plan

## Phase A (W1) — Foundations

Deliverables:

- Working FastAPI backend.
- Local repo opening.
- Raw history endpoint.
- Simple frontend list.

Done when:

- text commits are visible without crashes.

## Phase B (W2-W3) — Lane engine

Deliverables:

- lane allocator,
- graph segments,
- enriched history API,
- layout unit tests.

Done when:

- merge/fork cases are correct.

## Phase C (W4-W5) — Visual fidelity

Deliverables:

- complete toolbar/timeline/main layout,
- multi-layer canvas,
- ref pills, avatars, right meta,
- compact pastel theme.

Done when:

- rendering is visually compliant with this spec.

## Phase D (W6) — Interactions + performance

Deliverables:

- virtual scroll sync,
- live search,
- websocket updates,
- draw optimization.

Done when:

- fluidity is satisfactory on a large repo.

## Phase E (W7) — QA/polish

Deliverables:

- loading/error/empty states,
- responsive,
- e2e,
- run/deploy docs.

Done when:

- final checklist validated.

---

## 14) Blocking final checklist (Go/No-Go)

- [ ] Compliant compact light theme.
- [ ] Toolbar + mini timeline present.
- [ ] Pastel swimlanes with readable curves.
- [ ] Dense (32 px) and stable rows.
- [ ] Colored ref pills properly typed.
- [ ] Avatar + date + SHA + status dots visible per row.
- [ ] Instant search usable.
- [ ] Auto refresh without UX breakage.
- [ ] Acceptable performance on large history.
- [ ] Tested code (unit + minimal e2e).

---

## 15) Deployment and execution

## 15.1 Dev

- Backend: `uvicorn app.main:app --reload`
- Frontend: `npm run dev` (or `pnpm`, `bun` depending on choice)

## 15.2 Prod

- Static frontend build + reverse proxy to the API.
- Docker Compose option (api + web).

---

## 16) Security / robustness

- Validate the repo path (no traversal).
- Timeout on the git CLI fallback.
- No arbitrary shell execution from the UI.
- Error handling for corrupted repo / permission denied.

---

## 17) Direct instructions for the implementing agent

1. Strictly follow this visual spec.
2. Prioritize graph readability over ancillary features.
3. Use Canvas + virtualization mandatorily.
4. Produce atomic commits per phase.
5. After each phase, provide:
   - delivered features,
   - screenshots,
   - deviations vs PLAN.md,
   - correction plan.

---

## 18) Final definition of success

The result is validated if a user immediately perceives:

- a dense, professional "swimlanes" Git visualizer,
- a clear reading of branches/merges,
- a compact, pastel, informative rendering,
- and enough fluidity for daily use.
