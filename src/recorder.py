"""Enregistrement en buffer RAM des frames du point en cours.

Stratégie :
- Chaque frame affichée est encodée en JPEG (qualité ajustable) et stockée
  dans une deque bornée par `max_seconds`. Coût mémoire faible.
- À la fin du point (rotate()), le buffer devient `last`, l'ancien `last` devient `prev`.
- save_last()/save_prev() encode le buffer en mp4 à la volée, à la demande.
Pas d'écriture disque tant que l'utilisateur ne clique pas.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path

import cv2


class PointRecorder:
    def __init__(self, output_dir, fps, max_seconds=25, jpeg_quality=85):
        self.dir = Path(output_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fps = max(float(fps), 1.0)
        self.max_frames = max(int(self.fps * max_seconds), 30)
        self._jpeg_params = [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)]

        self._current = deque(maxlen=self.max_frames)  # JPEG bytes (np.ndarray)
        self._last = None   # list[bytes]
        self._prev = None

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
        if on_done is not None:
            try:
                on_done(out)
            except Exception:
                pass

    def _encode(self, buf, label):
        if not buf:
            return None
        first = cv2.imdecode(buf[0], cv2.IMREAD_COLOR)
        if first is None:
            return None
        h, w = first.shape[:2]

        ts = time.strftime("%Y%m%d-%H%M%S")
        out = self.dir / f"point-{label}-{ts}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out), fourcc, self.fps, (w, h))
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
