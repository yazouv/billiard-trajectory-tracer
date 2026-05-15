"""Vérification de mise à jour : interroge l'API GitHub Releases."""
from __future__ import annotations

import json
import urllib.request


def _version_tuple(v: str):
    parts = []
    for p in v.lstrip("v").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)


def check_latest(repo: str, current_version: str, timeout: float = 2.5):
    """Renvoie (tag, html_url) si une release plus récente existe, sinon None."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json",
                      "User-Agent": "CABReplay-updater"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except Exception:
        return None
    tag = (data.get("tag_name") or "").strip()
    html_url = (data.get("html_url") or "").strip()
    if not tag:
        return None
    if _version_tuple(tag) > _version_tuple(current_version):
        return (tag, html_url)
    return None
