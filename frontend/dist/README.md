# frontend/dist — bundle gelé (npm-free)

Ce dossier contient le **build statique de production** de GitLane (React 18 + Canvas).
Le backend FastAPI le sert directement à la racine (`main.py`) — aucun npm requis
au runtime : `python -m uvicorn app.main:app` + navigateur suffisent.

> `index.html` charge en plus `/static/gitlane-patches.js` (bouton "↩ Repo" + Ctrl+O,
> injection runtime sans re-build). Ce tag est ré-appliqué manuellement après chaque
> `npm run build` — voir `backend/app/api/static/gitlane-patches.js`.

## Re-bundler (uniquement sur une machine avec node ≥ 18)

Les sources de build sont archivées dans `frontend/rebuild-bucket/` :

```bash
cd frontend/rebuild-bucket
npm install
npm run build                 # régénère ../dist/ (outDir configuré)
```

Puis committer le nouveau `dist/` (bundle gelé) **et** ré-injecter le tag
`<script src="/static/gitlane-patches.js">` dans `dist/index.html`.

## Contenu servi

| Fichier | Rôle |
|---|---|
| `index.html` | Coquille React + tag patches |
| `assets/index-*.js` | Bundle JS minifié (~159 KB) |
| `assets/index-*.css` | Styles du design system (~7 KB) |
