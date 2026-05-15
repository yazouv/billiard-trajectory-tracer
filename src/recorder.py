"""Enregistrement en buffer RAM des frames du point en cours.

Stratégie :
- Chaque frame affichée est encodée en JPEG (qualité ajustable) et stockée
  dans une deque bornée par `max_seconds`. Coût mémoire faible.
- À la fin du point (rotate()), le buffer devient `last`, l'ancien `last` devient `prev`.
- save_last()/save_prev() encode le buffer en mp4 à la volée, à la demande.
Pas d'écriture disque tant que l'utilisateur ne clique pas.
"""
from __future__ import annotations

import shutil
import threading
import time
from collections import deque
from pathlib import Path

import cv2


class PointRecorder:
    def __init__(self, output_dir, fps, max_seconds=30,
                 output_max_seconds=10, jpeg_quality=85):
        self.dir = Path(output_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fps = max(float(fps), 1.0)
        self.max_frames = max(int(self.fps * max_seconds), 30)
        # Durée max du clip exporté. Si la séquence dure plus, le fps de sortie
        # est augmenté pour accélérer la vidéo et tenir dans cette enveloppe.
        self.output_max_seconds = float(output_max_seconds)
        self._jpeg_params = [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)]

        self._current = deque(maxlen=self.max_frames)  # JPEG bytes (np.ndarray)
        self._last = None   # list[bytes]
        self._prev = None
        # Dernier mp4 effectivement écrit sur disque (pour promotion en highlight)
        self._last_saved_path = None
        self._last_saved_lock = threading.Lock()
        self._last_rotate_ts = None  # monotonic du dernier rotate effectif

    def write(self, frame):
        if frame is None:
            return
        ok, buf = cv2.imencode(".jpg", frame, self._jpeg_params)
        if ok:
            self._current.append(buf)

    def rotate(self):
        """Fin de point : current → last → prev."""
        min_frames = max(int(self.fps * 0.4), 4)
        if len(self._current) < min_frames:
            self._current.clear()
            return
        self._prev = self._last
        self._last = list(self._current)
        self._current.clear()
        self._last_rotate_ts = time.monotonic()

    def save_last(self, on_done=None):
        return self._spawn_save(self._last, "last", on_done)

    def save_prev(self, on_done=None):
        return self._spawn_save(self._prev, "prev", on_done)

    def _spawn_save(self, buf, label, on_done):
        """Lance l'encodage mp4 dans un thread. Renvoie True si un job est lancé."""
        if not buf:
            return False
        # Copie de la liste de buffers (les bytes JPEG sont immuables, partage OK)
        snapshot = list(buf)
        threading.Thread(
            target=self._encode_worker,
            args=(snapshot, label, on_done),
            daemon=True,
        ).start()
        return True

    def _encode_worker(self, buf, label, on_done):
        try:
            out = self._encode(buf, label)
        except Exception as e:
            out = None
            print(f"Erreur sauvegarde {label}: {e}")
        if out is not None:
            with self._last_saved_lock:
                self._last_saved_path = out
        if on_done is not None:
            try:
                on_done(out)
            except Exception:
                pass

    def state(self):
        """Snapshot léger pour l'UI : durée en cours, dispo last/prev, âge du dernier rotate."""
        cur_secs = len(self._current) / self.fps if self._current else 0.0
        rotate_age = (time.monotonic() - self._last_rotate_ts
                      if self._last_rotate_ts is not None else None)
        return {
            "current_seconds": cur_secs,
            "has_last": self._last is not None,
            "has_prev": self._prev is not None,
            "rotate_age": rotate_age,
        }

    @property
    def last_saved_path(self):
        with self._last_saved_lock:
            return self._last_saved_path

    def prune(self, keep):
        """Garde les `keep` derniers mp4 du dossier de captures, supprime le reste.
        Le sous-dossier 'highlights' est ignoré."""
        try:
            keep = int(keep)
        except (TypeError, ValueError):
            return
        if keep <= 0:
            return
        try:
            files = [p for p in self.dir.glob("*.mp4") if p.is_file()]
        except OSError:
            return
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[keep:]:
            try:
                old.unlink()
                print(f"Capture rotée : {old.name}")
            except OSError as e:
                print(f"Impossible de supprimer {old.name} : {e}")

    def promote_last_to_highlights(self):
        """Promeut le dernier mp4 sauvé vers <dir>/highlights/.
        Tente un move; si OBS (ou autre) tient le fichier, fallback en copy +
        suppression best-effort. Renvoie le nouveau Path ou None."""
        with self._last_saved_lock:
            src = self._last_saved_path
        if src is None or not Path(src).exists():
            return None
        hl_dir = self.dir / "highlights"
        try:
            hl_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Création highlights/ impossible : {e}")
            return None
        src_p = Path(src)
        dst = hl_dir / src_p.name
        # 1) tentative de move (le plus propre)
        try:
            src_p.replace(dst)
        except OSError:
            # 2) fallback : copie + suppression best-effort (OBS tient un read-lock).
            try:
                shutil.copy2(src_p, dst)
            except OSError as e:
                print(f"Promotion en highlight impossible : {e}")
                return None
            try:
                src_p.unlink()
            except OSError:
                # Pas grave : le fichier sera potentiellement supprimé par la
                # rotation ultérieurement. Le highlight, lui, est en place.
                print(f"Highlight copié, original encore verrouillé : {src_p.name}")
        with self._last_saved_lock:
            self._last_saved_path = dst
        return dst

    def _encode(self, buf, label):
        if not buf:
            return None
        first = cv2.imdecode(buf[0], cv2.IMREAD_COLOR)
        if first is None:
            return None
        h, w = first.shape[:2]

        # FPS de sortie : si le clip natif dépasse la limite, on accélère.
        nominal_dur = len(buf) / self.fps
        if self.output_max_seconds > 0 and nominal_dur > self.output_max_seconds:
            out_fps = len(buf) / self.output_max_seconds
            print(f"Replay {label}: {nominal_dur:.1f}s -> "
                  f"{self.output_max_seconds:.0f}s (x{nominal_dur / self.output_max_seconds:.2f}).")
        else:
            out_fps = self.fps

        ts = time.strftime("%Y%m%d-%H%M%S")
        out = self.dir / f"point-{label}-{ts}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out), fourcc, out_fps, (w, h))
        if not writer.isOpened():
            return None
        try:
            writer.write(first)
            for jpg in buf[1:]:
                img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
                if img is not None:
                    writer.write(img)
        finally:
            writer.release()
        return out

    def close(self):
        self._current.clear()
        self._last = None
        self._prev = None
