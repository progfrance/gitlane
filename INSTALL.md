# Installation de GitLane (sans npm)

GitLane fonctionne **sans Node.js/npm** : le frontend est un bundle statique
déjà compilé (`frontend/dist/`), servi directement par le backend FastAPI.
Il suffit d'un Python ≥ 3.11 (via **miniforge/conda** recommandé) et de `git`.

## 1. Créer l'environnement Python

```bash
conda create -n gitlane python=3.13 -y
conda activate gitlane
```

Ou avec un venv classique :

```bash
cd gitlane/backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# source .venv/bin/pip install -r requirements.txt  # Linux/macOS
```

## 2. Installer les dépendances

```bash
cd gitlane/backend
pip install -r requirements.txt
```

### Cas offline (ordinateur sans accès internet)

Sur une machine **avec** internet, pré-télécharger les wheels :

```bash
cd gitlane/backend
pip download -r requirements.txt -d wheels/
```

Copier le dossier `wheels/` sur la machine cible, puis :

```bash
pip install --no-index --find-links=wheels/ -r requirements.txt
```

Le script `install_offline.bat` (Windows) ou `install_offline.sh`
(Linux/macOS) fait tout ça automatiquement.

## 3. Lancer

```bash
cd gitlane/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Ouvrir **http://127.0.0.1:8000** :
- au premier lancement (aucun repo connu) → page **/picker** pour choisir un dépôt ;
- ensuite → le dernier dépôt ouvert se rouvre automatiquement.

## 4. Changer de dépôt

Trois façons :
- bouton **↩ Repo** dans la barre d'outils (ou raccourci **Ctrl+O**) → `/picker` ;
- onglets **Récents** (10 derniers, persistés dans `~/.gitlane_recent.json`) ;
- **Parcourir** un dossier racine (scan `.git`, profondeur 1-3) ou chemin manuel.

## 5. Tests

```bash
cd gitlane/backend
.venv/Scripts/python -m pytest tests/ -q
```

## FAQ

**Je veux modifier le rendu frontend (couleurs, graphe…)**
→ Les sources sont archivées dans `frontend/rebuild-bucket/`. Sur un poste avec
node ≥ 18 : `cd frontend/rebuild-bucket && npm install && npm run build`, puis
commiter le nouveau `frontend/dist/`.

**Le scan "Parcourir" est lent sur mon disque**
→ Réduire la profondeur à 1 (valeur par défaut). Le scan ignore les dossiers
cachés et ne suit pas les symlinks.

**Où sont mes derniers repos ?**
→ `~/.gitlane_recent.json` (10 entrées max, dédupliquées par chemin normalisé).
