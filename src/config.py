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
    "table_rect": None,        # [x, y, w, h] ou None
    "smooth_window": 3,
    "show_balls": False,
    "show_table_rect": False,
    "show_trail_white": True,
    "show_trail_yellow": True,
    "show_trail_red": False,
    "input_mode": "video",     # "video" ou "ndi"
    "captures_dir": "",        # vide → ./captures à côté de l'app
}


def load():
    data = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            data.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save(updates):
    data = load()
    data.update(updates)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
