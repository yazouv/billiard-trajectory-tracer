from collections import deque

import cv2
import numpy as np

MOTION_PIX_THRESHOLD = 6
MOTION_WINDOW = 10
STILL_HOLD_SECONDS = 1.0
KEEP_AFTER_STILL_SECONDS = 1.5

# Tolérance d'occlusion : on garde la dernière position connue X frames
OCCLUSION_GRACE_FRAMES = 15

MAX_TRAIL_POINTS = 800


class Trajectories:
    """Historique de positions par bille + détection d'arrêt avec tolérance d'occlusion."""

    def __init__(self, fps):
        self.fps = max(fps, 1.0)
        self.points = {}        # color -> list[(x, y)]
        self.recent = {}        # color -> deque (test de mouvement)
        self.last_seen = {}     # color -> frame_idx dernière détection
        self.still_since_frame = None
        self.frame_idx = 0
        self.smooth_window = 3
        # Snapshots des derniers points (pris juste avant un auto-clear)
        self.last_snapshot = None  # dict color -> list[(x, y)]
        self.prev_snapshot = None

    def configure(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def _ensure(self, color):
        if color not in self.points:
            self.points[color] = []
            self.recent[color] = deque(maxlen=MOTION_WINDOW)

    def update(self, detections):
        self.frame_idx += 1
        for color, (x, y, _r) in detections.items():
            self._ensure(color)
            pts = self.points[color]
            if len(pts) >= MAX_TRAIL_POINTS:
                pts.pop(0)
            pts.append((x, y))
            self.recent[color].append((x, y))
            self.last_seen[color] = self.frame_idx

        # Au-delà de la grace, on flush "recent" pour ne pas bloquer le test d'arrêt
        for color, ts in list(self.last_seen.items()):
            if color in detections:
                continue
            if self.frame_idx - ts > OCCLUSION_GRACE_FRAMES:
                self.recent[color].clear()

        cleared = False
        if self._all_still():
            if self.still_since_frame is None:
                self.still_since_frame = self.frame_idx
            else:
                still_for = (self.frame_idx - self.still_since_frame) / self.fps
                if still_for >= STILL_HOLD_SECONDS + KEEP_AFTER_STILL_SECONDS:
                    self._snapshot_before_clear()
                    self.clear()
                    cleared = True
        else:
            self.still_since_frame = None
        return cleared

    def _all_still(self):
        active = [c for c, ts in self.last_seen.items()
                  if self.frame_idx - ts <= OCCLUSION_GRACE_FRAMES]
        if not active:
            return False
        for color in active:
            pts = self.recent[color]
            if len(pts) < MOTION_WINDOW:
                return False
            arr = np.array(pts)
            disp = np.linalg.norm(np.diff(arr, axis=0), axis=1).sum()
            if disp > MOTION_PIX_THRESHOLD:
                return False
        return True

    def _snapshot_before_clear(self):
        snap = {c: list(pts) for c, pts in self.points.items() if pts}
        if snap:
            self.prev_snapshot = self.last_snapshot
            self.last_snapshot = snap

    def clear(self):
        for d in self.points.values():
            d.clear()
        for d in self.recent.values():
            d.clear()
        self.still_since_frame = None

    def draw_snapshot(self, frame, snapshot, colors_bgr, thickness=2):
        """Dessine les polylines d'un snapshot (dict color -> list[(x,y)])."""
        if not snapshot:
            return
        for color, pts in snapshot.items():
            if len(pts) < 2:
                continue
            arr = _smooth(np.array(pts, dtype=np.float32), self.smooth_window)
            arr = arr.astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [arr], False, colors_bgr[color],
                          thickness, cv2.LINE_AA)

    def draw(self, frame, colors_bgr, thickness=2, visible=None):
        for color, pts in self.points.items():
            if visible is not None and not visible.get(color, True):
                continue
            if len(pts) < 2:
                continue
            arr = _smooth(np.array(pts, dtype=np.float32), self.smooth_window)
            arr = arr.astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [arr], False, colors_bgr[color],
                          thickness, cv2.LINE_AA)


def _smooth(points, window):
    n = len(points)
    if n < 3 or window < 3:
        return points
    w = min(int(window), n if n % 2 else n - 1)
    if w % 2 == 0:
        w -= 1
    if w < 3:
        return points
    kernel = np.ones(w, dtype=np.float32) / w
    pad = w // 2
    xs = np.pad(points[:, 0], pad, mode="edge")
    ys = np.pad(points[:, 1], pad, mode="edge")
    sx = np.convolve(xs, kernel, mode="valid")
    sy = np.convolve(ys, kernel, mode="valid")
    return np.stack([sx, sy], axis=1)
