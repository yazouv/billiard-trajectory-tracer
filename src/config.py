import json
import sys
from pathlib import Path


def _app_root():
    """Racine de l'app : dossier de l'exe en mode frozen, racine repo sinon."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


CONFIG_PATH = _app_root() / "config.json"

DEFAULTS = {
    "table_quad": None,        # [[x,y]*4] (TL,TR,BR,BL) ou None
    "table_rect": None,        # legacy [x, y, w, h], migré au chargement
    "smooth_window": 3,
    "show_balls": False,
    "show_table_rect": False,
    "show_trail_white": True,
    "show_trail_yellow": True,
    "show_trail_red": False,
    "input_mode": "video",     # "video" ou "ndi"
    "captures_dir": "",        # vide → ./captures à côté de l'app
    "captures_keep": 20,       # max de mp4 conservés dans le dossier (rotation FIFO)
    # OBS WebSocket (lecture auto du replay)
    "obs_enabled": False,
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_password": "",
    "obs_scene": "Replay",
    "obs_source": "CABReplayMedia",
}


# Clés systématiquement remises au défaut à chaque démarrage, même si elles
# ont été sauvegardées dans config.json (UX : on veut que l'app s'ouvre
# toujours avec ces options décochées).
FORCE_DEFAULT_KEYS = ("show_table_rect", "show_trail_red")


def load():
    data = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            data.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    for k in FORCE_DEFAULT_KEYS:
        data[k] = DEFAULTS[k]
    return data


def save(updates):
    data = load()
    data.update(updates)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
