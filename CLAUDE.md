# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Trajectory tracer for **billard français (carambole)** — 3 balls (white, yellow, red) on a blue cloth, top-down view. Two source modes:

- **Video file** (`datas/video.mp4` by default, or any mp4/mov/avi/mkv/m4v).
- **NDI live feed** via cyndilib (Mevo, OBS NDI output, NDI Webcam…).

Architecture is intentionally modular so any other capture source can be plugged in without touching detection / tracking / rendering / UI.

## Run

```powershell
py src/main.py                # ouvre le menu de lancement (customtkinter)
py src/main.py <video.mp4>    # le menu propose ce fichier par défaut
```

Au démarrage, un **menu d'accueil customtkinter** s'ouvre : choix entre *Ouvrir un fichier* (file dialog natif) ou *Flux NDI* (découverte réseau + saisie manuelle). Une fois la source choisie, la fenêtre vidéo OpenCV s'ouvre et un drag de rectangle sur la première frame définit la zone de jeu (Entrée valide). La fenêtre **Réglages** customtkinter s'ouvre en parallèle.

Pendant la lecture (touches valides depuis la fenêtre vidéo *ou* Réglages) :

- **Espace** — pause / lecture
- **M** — rouvre le menu pour changer de source
- **R** — redéfinit la zone de jeu (efface les traces)
- **C** — efface les traces
- **S** — sauvegarde la config courante dans `config.json`
- **Q** / **Échap** — quitter

## Architecture

Pipeline par frame (orchestré par `src/main.py`) :

1. **`capture.VideoSource`** / **`capture.NdiSource`** — interface commune (`read`, `release`, `fps`, `width`, `height`). `VideoSource` wrap `cv2.VideoCapture` ; `NdiSource` utilise cyndilib (`Receiver` + `VideoFrameSync`, format `BGRX_BGRA`). `list_ndi_sources()` fait la découverte via callback + polling. À ce jour, la DLL bundlée par cyndilib doit être remplacée par celle du NDI 6 Runtime système pour découvrir les caméras NDI|HX (Mevo notamment) — voir Notes.
2. **`table.select_table_rect` / `rect_to_mask`** — rectangle utilisateur sur la première frame (cv2.selectROI dans une fenêtre `WINDOW_NORMAL | KEEPRATIO` dimensionnée à 90 % de l'écran) → masque binaire.
3. **`detector.detect_balls(frame, roi_mask)`** — HSV par couleur (`HSV_RANGES`) → morpho → contours filtrés par ROI, rayon (`MIN_RADIUS`/`MAX_RADIUS`) et circularité (`MIN_CIRCULARITY`). Rouge en deux H-ranges.
4. **`tracker.Trajectories`** — deque de positions par bille. Détection d'arrêt sur `MOTION_WINDOW` frames sous `MOTION_PIX_THRESHOLD`. Auto-clear après `STILL_HOLD_SECONDS + KEEP_AFTER_STILL_SECONDS`. `_snapshot_before_clear` mémorise les `last_snapshot` / `prev_snapshot`. Lissage moving-average de largeur `SMOOTH_WINDOW` sur le rendu.
5. **`recorder.PointRecorder`** — buffer RAM tournant : chaque frame affichée est encodée en JPEG (qualité 85) dans une `deque` bornée à 25 s. `rotate()` à chaque fin de point : `current → last → prev`. `save_last()` / `save_prev()` encodent le buffer en mp4 (`mp4v`) dans un **thread daemon** pour ne pas figer la boucle vidéo. Sortie dans `captures/` (chemin configurable via Réglages).

Tous les seuils de réglage vivent en tête de `detector.py` et `tracker.py`. À ajuster là, pas en threadant des paramètres dans les appels.

## UI (customtkinter)

- **`src/launcher.py`** — `Launcher(CTkToplevel)`. Deux pages : `_build_home` (cards Ouvrir fichier / Flux NDI + footer Quitter + bandeau update) et `_build_ndi` (liste scrollable des sources, scan async via `threading.Thread` + sentinel + `after()` polling, champ de saisie manuelle, footer Retour + Rafraîchir). **Important** : dans les `_build_*`, packer le footer (`side="bottom"`) **avant** le `content` (`expand=True, fill="both"`), sinon le content avale l'espace et le footer disparaît.
- **`src/controls.py`** — `Controls(CTkToplevel)`. Pas de `mainloop()` : `refresh()` appelle `update()` à chaque frame, **throttlé à 20 Hz** pour éviter la réentrance tk pendant un redraw cv2 (sinon crash GIL). Fenêtre `resizable(False, False)` pour la même raison. Touches re-bindées (`<Space>`, `<m>`, `<r>`, `<c>`, `<s>`, `<q>`, `<Escape>`) pour fonctionner même quand Réglages a le focus — drainées par `main.py` via `consume_key()`.
- Un **unique `ctk.CTk()` caché** dans `main.py` sert de master à `Launcher` et `Controls`. Créer plusieurs `CTk` provoque des crashs (`invalid command name`, GIL).

## Versioning & releases

- `src/version.py` détient `__version__` (marqué `# x-release-please-version`).
- `src/updater.py` interroge `api.github.com/repos/.../releases/latest` (timeout court, en thread) — le launcher affiche un bandeau "Nouvelle version disponible" si plus récente.
- **release-please** (`.github/workflows/release-please.yml` + `release-please-config.json` + `.release-please-manifest.json`) ouvre/maintient une PR de release sur push `main`. Merger la PR crée le tag `vX.Y.Z` et la release GitHub.
- **`.github/workflows/release.yml`** se déclenche sur tag `v*` : build PyInstaller Windows, zip de `dist/CABReplay/*`, asset uploadé sur la release.

Convention de commits : **conventional commits** (`feat:`, `fix:`, `chore:`…) — release-please en dépend pour décider du bump.

## Build local

```bash
./build.sh        # nettoie, lance pyinstaller (CABReplay.spec), copie datas/ + config.json
```

Le spec collecte les datas customtkinter, les DLLs cyndilib, et embarque `assets/icon.ico` (regénérable via `py tools/make_icon.py`).

## Dépendances

`opencv-python`, `numpy`, `cyndilib`, `customtkinter` (tire `darkdetect`), `Pillow` (uniquement pour `make_icon.py`). `pyinstaller` pour le build. Voir `requirements.txt`.

## Notes pour les évolutions

- Le rectangle ROI est la première défense contre les faux positifs hors-table. Si la détection d'une couleur casse, vérifier d'abord que la bille est dans la ROI avant d'élargir les HSV.
- `Erreurs/` (gitignored) contient des screenshots de faux positifs passés (maillot blanc, bande rouge) — utiles comme cas de régression.
- **cyndilib + NDI|HX (Mevo)** : cyndilib ≤ 0.0.10 bundle un NDI 4/5 qui ne découvre pas les sources NDI|HX en multicast. Remplacer `<site-packages>/cyndilib/wrapper/bin/Processing.NDI.Lib.x64.dll` par celui de `C:\Program Files\NDI\NDI 6 Tools\Runtime\` règle le problème. Le pyinstaller spec embarque la DLL présente au build — donc la version 6 si elle a été swappée avant.
- Le firewall Windows agit **par programme** : autoriser `python.exe` (ou `CABReplay.exe`) en entrée/sortie pour profils Public/Privé/Domaine si la découverte NDI muet.
- Pas de tests, pas de lint config.
