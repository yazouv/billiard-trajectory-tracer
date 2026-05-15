"""Vérification de mise à jour + installation auto via l'API GitHub Releases.

Flow auto-install (mode frozen / exe uniquement) :
1. get_latest_release() lit /releases/latest, sélectionne l'asset .zip.
2. download(url, dest, on_progress) télécharge le zip en stream.
3. install_and_relaunch(zip_path) : extrait dans %TEMP%, écrit un .bat qui
   attend que l'exe soit libéré, recopie les fichiers, relance, puis exit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def _version_tuple(v: str):
    parts = []
    for p in v.lstrip("v").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)


def _api_call(url: str, timeout: float = 5.0):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "CABReplay-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def check_latest(repo: str, current_version: str, timeout: float = 2.5):
    """Renvoie (tag, html_url) si version plus récente, sinon None."""
    try:
        data = _api_call(
            f"https://api.github.com/repos/{repo}/releases/latest", timeout)
    except Exception:
        return None
    tag = (data.get("tag_name") or "").strip()
    html_url = (data.get("html_url") or "").strip()
    if not tag or _version_tuple(tag) <= _version_tuple(current_version):
        return None
    return (tag, html_url)


def get_latest_release(repo: str, current_version: str, timeout: float = 5.0):
    """Variante riche : renvoie un dict avec asset_url (premier .zip), ou None."""
    try:
        data = _api_call(
            f"https://api.github.com/repos/{repo}/releases/latest", timeout)
    except Exception:
        return None
    tag = (data.get("tag_name") or "").strip()
    if not tag or _version_tuple(tag) <= _version_tuple(current_version):
        return None
    asset_url = None
    asset_size = 0
    for a in data.get("assets", []):
        name = a.get("name", "")
        if name.lower().endswith(".zip"):
            asset_url = a.get("browser_download_url")
            asset_size = a.get("size", 0)
            break
    return {
        "tag": tag,
        "html_url": data.get("html_url", ""),
        "asset_url": asset_url,
        "asset_size": asset_size,
    }


def download(url: str, dest_path: Path, on_progress=None, chunk_size: int = 64 * 1024):
    """Télécharge `url` vers `dest_path`. on_progress(done, total) appelée régulièrement."""
    req = urllib.request.Request(url, headers={"User-Agent": "CABReplay-updater"})
    with urllib.request.urlopen(req, timeout=15) as r:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = r.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress:
                    try:
                        on_progress(done, total)
                    except Exception:
                        pass
    return dest_path


def install_and_relaunch(zip_path: Path, exe_name: str = "CABReplay.exe"):
    """Extrait le zip dans un staging, lance un .bat qui :
      - attend que l'exe courant soit terminé,
      - recopie les fichiers extraits sur le dossier d'installation,
      - relance l'exe,
      - se supprime.
    Puis exit le process Python courant.
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError("install_and_relaunch n'est utilisable qu'en mode buildé.")
    if sys.platform != "win32":
        raise RuntimeError("Auto-install supporté uniquement sur Windows.")

    install_dir = Path(sys.executable).resolve().parent
    pid = os.getpid()

    stage = Path(tempfile.gettempdir()) / f"cabreplay-update-{pid}"
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(stage)

    # Si le zip contient un sous-dossier unique (ex: CABReplay/), on prend son contenu
    children = list(stage.iterdir())
    if len(children) == 1 and children[0].is_dir():
        stage = children[0]

    bat = Path(tempfile.gettempdir()) / f"cabreplay-update-{pid}.bat"
    bat_content = (
        "@echo off\r\n"
        "setlocal\r\n"
        f"set TARGET={install_dir}\r\n"
        f"set STAGE={stage}\r\n"
        f"set EXE={install_dir / exe_name}\r\n"
        ":waitloop\r\n"
        f'tasklist /FI "PID eq {pid}" 2>NUL | findstr "{pid}" >NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "    ping -n 2 127.0.0.1 >NUL\r\n"
        "    goto waitloop\r\n"
        ")\r\n"
        'xcopy /S /E /Y /I "%STAGE%\\*" "%TARGET%\\" >NUL\r\n'
        'start "" "%EXE%"\r\n'
        f'rmdir /s /q "{stage.parent / stage.name}" >NUL 2>&1\r\n'
        'del "%~f0"\r\n'
    )
    bat.write_text(bat_content, encoding="utf-8")

    # Lance le bat détaché, sans fenêtre console
    DETACHED_PROCESS = 0x00000008
    CREATE_NO_WINDOW = 0x08000000
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    sys.exit(0)
