# Rebuild-bucket frontend

Sources de build conservées pour régénérer `../dist/` sur une machine qui a npm/node.

## Pourquoi ce dossier existe

Le poste de production (miniforge uniquement) n'a **pas npm** : l'app est servie depuis
`frontend/dist/` (bundle statique gelé, ~165 KB) par le backend FastAPI.

Si un changement du rendu graphique est nécessaire, on rebundle ici :

```bash
cd frontend
npm install
npm run build        # régénère dist/
```

Puis on commite le nouveau `dist/`.

## Contenu

- `src/`            — code source TypeScript/React (~1 300 LOC)
- `index.html`      — point d'entrée Vite
- `package.json`    — dépendances React 18, Vite 5, TypeScript 5
- `package-lock.json` — verrou de versions
- `vite.config.ts`  — proxy dev vers le backend :8088
- `tsconfig.json`   — config TypeScript

## Rappel des commandes utiles

| Commande | Effet |
|---|---|
| `npm run dev` | Dev server Vite (port 5173, proxy vers :8088) |
| `npm run build` | Compile `src/` → `dist/` (production) |
| `npm test` | Aucun test frontend pour l'instant (tests côté pytest/backend) |
