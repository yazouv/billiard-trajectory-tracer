import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULTS = {
    "table_rect": None,        # [x, y, w, h] ou None
    "smooth_window": 3,
    "show_balls": False,
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
