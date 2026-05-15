"""Fenêtre de rendu vidéo basée sur tkinter + Pillow.

Remplace cv2.imshow pour éviter les conflits d'event loop avec tk sur Windows
(crash GIL au drag/resize) et pour qu'OBS puisse capturer la fenêtre.
"""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk


class VideoView(ctk.CTkToplevel):
    def __init__(self, master, title="CAB Replay", initial_size=(1280, 720)):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{initial_size[0]}x{initial_size[1]}")
        self.minsize(640, 360)
        self.configure(fg_color="#000000")
        self._label = tk.Label(self, bg="#000000",
                               borderwidth=0, highlightthickness=0)
        self._label.pack(fill="both", expand=True)
        self._photo = None  # garde la référence vivante (sinon GC efface l'image)
        self._quit_requested = False
        self._key_queue = []

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        for k in ("space", "m", "M", "r", "R", "c", "C", "s", "S",
                  "q", "Q", "Escape"):
            event_str = f"<{k}>" if len(k) > 1 else f"<KeyPress-{k}>"
            self.bind(event_str, self._on_key)
        # Active le focus pour recevoir les touches
        try:
            self.focus_force()
        except Exception:
            pass

    # ---------- Event handling ----------
    def _on_close(self):
        self._quit_requested = True

    def _on_key(self, event):
        keysym = event.keysym
        mapping = {"space": ord(" "), "Escape": 27}
        if keysym in mapping:
            self._key_queue.append(mapping[keysym])
        elif len(keysym) == 1:
            self._key_queue.append(ord(keysym.lower()))

    def quit_requested(self):
        return self._quit_requested

    def consume_key(self):
        return self._key_queue.pop(0) if self._key_queue else None

    # ---------- Render ----------
    def show_frame(self, bgr):
        if bgr is None:
            return
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)

        # Resize en conservant l'aspect ratio si la fenêtre a une autre taille
        lw = self._label.winfo_width()
        lh = self._label.winfo_height()
        if lw > 1 and lh > 1 and (lw != w or lh != h):
            ratio = min(lw / w, lh / h)
            new_w = max(1, int(w * ratio))
            new_h = max(1, int(h * ratio))
            img = img.resize((new_w, new_h), Image.BILINEAR)

        self._photo = ImageTk.PhotoImage(img)
        self._label.configure(image=self._photo)
