# frontend/dist — bundle gelé (npm-free)

Ce dossier contient le **build statique de production** de GitLane (React 18 + Canvas).
Le backend FastAPI le sert directement à la racine (`main.py:57`) — aucun npm requis
au runtime : `python -m uvicorn app.main:app` + navigateur suffisent.

## Re-bundler (uniquement sur une machine avec node ≥ 18)

Les sources de build sont archivées dans `frontend/rebuild-bucket/` :

```bash
cd frontend/rebuild-bucket
npm install
npm run build                 # régénère ../dist/
```

Puis committer le nouveau `dist/` (bundle gelé).

## Contenu servi

| Fichier | Rôle |
|---|---|
| `index.html` | Coquille React (charge les assets ci-dessous) |
| `assets/index-*.js` | Bundle JS minifié (~159 KB) |
| `assets/index-*.css` | Styles du design system (~7 KB) |

> Ne pas modifier les fichiers ici à la main — les changements se font dans
> `rebuild-bucket/src/`, puis `npm run build`.
