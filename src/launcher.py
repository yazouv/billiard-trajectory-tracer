"""Menu de lancement CAB Replay (customtkinter).

Renvoie :
    ("video", "C:\\chemin\\vers\\fichier.mp4")
    ("ndi",   "OBS-PC (NDI Source)")
    None                                # utilisateur a fermé / annulé
"""
from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from updater import check_latest
from version import GITHUB_REPO, __version__


def _icon_path():
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    p = base / "assets" / "icon.ico"
    return str(p) if p.exists() else None


def _apply_icon(window):
    p = _icon_path()
    if p:
        try:
            window.iconbitmap(p)
        except Exception:
            pass


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class Launcher(ctk.CTkToplevel):
    def __init__(self, master, default_video=None, ndi_lister=None):
        super().__init__(master)
        self.title("CAB Replay")
        self.geometry("560x460")
        self.minsize(560, 460)
        self.result = None
        self._default_video = default_video
        self._ndi_lister = ndi_lister
        self.protocol("WM_DELETE_WINDOW", self._on_quit)
        _apply_icon(self)
        self._update_info = None  # (tag, url) si update dispo
        self._build_home()
        self.after(50, self._raise)
        self._start_update_check()

    def _raise(self):
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    # ---------- Helpers ----------
    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _header(self, title, subtitle=None):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(pady=(28, 8), padx=24, fill="x")
        ctk.CTkLabel(frame, text=title,
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(frame, text=subtitle,
                         font=ctk.CTkFont(size=13),
                         text_color=("gray60", "gray70")).pack(anchor="w", pady=(2, 0))

    # ---------- Home ----------
    def _build_home(self):
        self._clear()
        self._header("CAB Replay", f"v{__version__} — choisis une source vidéo")

        # Conteneur du bandeau de mise à jour (rempli si dispo)
        self._update_banner = ctk.CTkFrame(self, fg_color="transparent")
        self._update_banner.pack(fill="x", padx=24)
        self._render_update_banner()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(expand=True, fill="both", padx=24, pady=16)

        self._card(content, "Ouvrir un fichier",
                   "Lire une vidéo enregistrée (mp4, mov, avi…).",
                   "Parcourir…", self._on_pick_video).pack(fill="x", pady=(0, 14))

        self._card(content, "Flux NDI",
                   "Se connecter à une source NDI sur le réseau (OBS, caméra…).",
                   "Choisir un flux", self._on_open_ndi).pack(fill="x")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=24, pady=16)
        ctk.CTkButton(footer, text="Quitter", width=120, height=36,
                      fg_color="transparent", border_width=1,
                      command=self._on_quit).pack(side="right")

    def _card(self, parent, title, description, button_text, command):
        card = ctk.CTkFrame(parent, corner_radius=12)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=18)
        ctk.CTkLabel(inner, text=title,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(inner, text=description,
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray70")).pack(anchor="w", pady=(4, 12))
        ctk.CTkButton(inner, text=button_text, height=36,
                      command=command).pack(anchor="w")
        return card

    # ---------- Actions ----------
    def _on_pick_video(self):
        initial = None
        if self._default_video and Path(self._default_video).exists():
            initial = str(Path(self._default_video).parent)
        path = filedialog.askopenfilename(
            parent=self,
            title="Choisir une vidéo",
            initialdir=initial,
            filetypes=[
                ("Vidéos", "*.mp4 *.mov *.avi *.mkv *.m4v"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if path:
            self.result = ("video", path)
            self.destroy()

    def _on_quit(self):
        self.result = None
        self.destroy()

    # ---------- NDI screen ----------
    def _on_open_ndi(self):
        self._build_ndi()

    def _build_ndi(self):
        self._clear()
        self._header("Flux NDI", "Sources détectées sur le réseau")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(expand=True, fill="both", padx=24, pady=8)

        self._ndi_status = ctk.CTkLabel(body, text="Recherche en cours…",
                                        font=ctk.CTkFont(size=13),
                                        text_color=("gray60", "gray70"))
        self._ndi_status.pack(anchor="w", pady=(0, 8))

        self._ndi_list = ctk.CTkScrollableFrame(body, corner_radius=10, height=180)
        self._ndi_list.pack(fill="both", expand=True)

        # Saisie manuelle, utile si la découverte échoue (firewall, mDNS…)
        manual = ctk.CTkFrame(body, fg_color="transparent")
        manual.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(manual, text="Ou saisir manuellement le nom de la source :",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray55", "gray70")).pack(anchor="w")
        row = ctk.CTkFrame(manual, fg_color="transparent")
        row.pack(fill="x", pady=(4, 0))
        self._ndi_manual = ctk.CTkEntry(row, height=32,
                                        placeholder_text="MACHINE (Nom de la source)")
        self._ndi_manual.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Connecter", width=110, height=32,
                      command=self._on_ndi_manual).pack(side="right", padx=(8, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=24, pady=16)
        ctk.CTkButton(footer, text="Retour", width=110, height=36,
                      fg_color="transparent", border_width=1,
                      command=self._build_home).pack(side="left")
        self._ndi_refresh_btn = ctk.CTkButton(
            footer, text="Rafraîchir", width=120, height=36,
            command=self._refresh_ndi)
        self._ndi_refresh_btn.pack(side="right")

        self._refresh_ndi()

    # ---------- Update check ----------
    def _start_update_check(self):
        def worker():
            try:
                self._update_info = check_latest(GITHUB_REPO, __version__)
            except Exception:
                self._update_info = None
        threading.Thread(target=worker, daemon=True).start()
        self.after(800, self._poll_update_check)

    def _poll_update_check(self):
        if not self.winfo_exists():
            return
        if self._update_info is not None:
            self._render_update_banner()
            return
        # Pas encore de réponse : on reteste un peu plus tard
        self.after(800, self._poll_update_check)

    def _render_update_banner(self):
        for w in self._update_banner.winfo_children():
            w.destroy()
        if not self._update_info:
            return
        tag, url = self._update_info
        bar = ctk.CTkFrame(self._update_banner, corner_radius=10,
                           fg_color=("#1e6e3a", "#1e6e3a"))
        bar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(bar, text=f"Nouvelle version disponible : {tag}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#ffffff").pack(side="left", padx=12, pady=8)
        ctk.CTkButton(bar, text="Télécharger", width=110, height=28,
                      fg_color="#ffffff", text_color="#1e6e3a", hover_color="#dddddd",
                      command=lambda: webbrowser.open(url)).pack(side="right", padx=8, pady=6)

    def _on_ndi_manual(self):
        name = self._ndi_manual.get().strip()
        if name:
            self._select_ndi(name)

    def _refresh_ndi(self):
        for w in self._ndi_list.winfo_children():
            w.destroy()
        self._ndi_status.configure(text="Recherche en cours…")
        self._ndi_refresh_btn.configure(state="disabled")
        self._ndi_pending = None  # sera (sources, err) une fois le worker fini

        def worker():
            try:
                if self._ndi_lister is None:
                    result = ([], "cyndilib non disponible")
                else:
                    result = (self._ndi_lister(), None)
            except Exception as e:
                result = ([], str(e))
            self._ndi_pending = result  # affectation atomique : safe inter-thread

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_ndi)

    def _poll_ndi(self):
        if not self.winfo_exists():
            return
        if self._ndi_pending is None:
            self.after(100, self._poll_ndi)
            return
        sources, err = self._ndi_pending
        self._ndi_pending = None
        self._populate_ndi(sources, err)

    def _populate_ndi(self, sources, err):
        if not self.winfo_exists():
            return
        self._ndi_refresh_btn.configure(state="normal")
        if err:
            self._ndi_status.configure(text=f"Erreur : {err}")
            return
        if not sources:
            self._ndi_status.configure(text="Aucune source NDI trouvée.")
            return
        self._ndi_status.configure(text=f"{len(sources)} source(s) détectée(s) :")
        for name in sources:
            ctk.CTkButton(
                self._ndi_list, text=name, height=40, anchor="w",
                command=lambda n=name: self._select_ndi(n),
            ).pack(fill="x", padx=4, pady=4)

    def _select_ndi(self, name):
        self.result = ("ndi", name)
        self.destroy()


def show_launcher(master, default_video=None, ndi_lister=None):
    """Affiche le launcher comme Toplevel de `master` (un CTk caché)."""
    win = Launcher(master, default_video=default_video, ndi_lister=ndi_lister)
    master.wait_window(win)
    return win.result
