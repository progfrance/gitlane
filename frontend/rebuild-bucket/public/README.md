# frontend/dist — bundle gelé (npm-free)

Ce dossier contient le **build statique de production** de GitLane (React 18 + Canvas).
Le backend FastAPI le sert directement à la racine (`main.py`) — aucun npm requis
au runtime : `python -m uvicorn app.main:app` + navigateur suffisent.

> Le bouton « Dépôt » et le raccourci Ctrl+O vivent désormais dans le bundle
> React lui-même (`TopToolbar` + raccourcis `App`). L'ancien patch runtime
> `backend/app/api/static/gitlane-patches.js` est un no-op conservé pour les
> vieux bundles en cache — `index.html` ne le charge plus.

## Re-bundler (uniquement sur une machine avec node ≥ 18)

Les sources de build sont archivées dans `frontend/rebuild-bucket/` :

```bash
cd frontend/rebuild-bucket
npm install
npm run build                 # régénère ../dist/ (outDir configuré)
```

Puis committer le nouveau `dist/` (bundle gelé).

## Contenu servi

| Fichier | Rôle |
|---|---|
| `index.html` | Coquille React |
| `assets/index-*.js` | Bundle JS minifié (~175 KB) |
| `assets/index-*.css` | Styles du design system (~12 KB) |
