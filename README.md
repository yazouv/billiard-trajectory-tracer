# TestIAReplay

Traceur de trajectoires pour **billard français (carambole)** vu du dessus.
À partir d'une vidéo (et à terme d'un flux NDI), le programme détecte les trois
billes (blanche, jaune, rouge) et dessine en overlay leurs trajectoires pendant
chaque point. Les traces s'effacent automatiquement une fois les billes
immobiles depuis quelques secondes.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Lancement

```powershell
python src/main.py                # utilise datas/video.mp4 par défaut
python src/main.py <chemin.mp4>   # autre fichier
```

Au tout premier lancement, une fenêtre s'ouvre sur la première image : trace un
rectangle à l'intérieur des bandes (uniquement le tapis) puis appuie sur
`Entrée`. La zone est sauvegardée dans `config.json` et rechargée
automatiquement aux lancements suivants.

## Contrôles

Pendant la lecture :

| Touche      | Action                                           |
|-------------|--------------------------------------------------|
| `Espace`    | Pause / lecture                                  |
| `R`         | Redéfinir la zone de jeu (utile avant un point)  |
| `C`         | Effacer manuellement les traces                  |
| `S`         | Sauvegarder la config courante                   |
| `Q` / `Échap` | Quitter                                        |

Une fenêtre **Reglages** s'affiche en parallèle avec :

- `Lissage` — taille du noyau de moyenne mobile appliqué au tracé
- `Contours billes` — affiche/masque les cercles autour des billes détectées

## Architecture

```
src/
  capture.py     # Source vidéo (mp4 maintenant, NDI plus tard)
  table.py       # Sélection manuelle du rectangle de la zone de jeu
  detector.py    # Détection HSV des 3 billes + filtres taille/circularité
  tracker.py     # Historique des positions, détection d'arrêt, rendu lissé
  controls.py    # Panneau de réglages (trackbars)
  config.py      # Lecture / écriture de config.json
  main.py        # Boucle principale
```

Voir `CLAUDE.md` pour les détails techniques (seuils, dépendances internes,
hypothèses sur la résolution).
