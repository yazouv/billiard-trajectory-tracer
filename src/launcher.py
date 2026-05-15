"""Menu de lancement CAB Replay (customtkinter).

Renvoie :
    ("video", "C:\\chemin\\vers\\fichier.mp4")
    ("ndi",   "OBS-PC (NDI Source)")
    None                                # utilisateur a fermé / annulé
"""
from __future__ import annotations

import sys
import tempfile
import threading
import traceback
import webbrowser
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from updater import download, get_latest_release, install_and_relaunch
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
        self.geometry("580x600")
        self.minsize(560, 560)
        self.result = None
        self._default_video = default_video
        self._ndi_lister = ndi_lister
        self.protocol("WM_DELETE_WINDOW", self._on_quit)
        _apply_icon(self)
        self._update_info = None  # dict release info, ou None
        self._update_state = "idle"  # idle | downloading | ready | error
        self._update_progress = 0.0
        self._update_error = None
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
        # Footer packé EN PREMIER avec side=bottom : sinon content (expand=True)
        # avale tout l'espace et le footer disparaît.
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=24, pady=16)
        ctk.CTkButton(footer, text="Quitter", width=120, height=36,
                      fg_color="transparent", border_width=1,
                      command=self._on_quit).pack(side="right")

        self._header("CAB Replay", f"v{__version__} — choisis une source vidéo")

        # Bandeau update (vide tant qu'on n'a pas trouvé de release plus récente)
        self._update_banner = ctk.CTkFrame(self, fg_color="transparent")
        self._update_banner.pack(fill="x", padx=24)
        self._render_update_banner()

        # expand=True + anchor: content occupe l'espace restant, cards en haut
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=8, anchor="n")

        self._card(content, "Ouvrir un fichier",
                   "Lire une vidéo enregistrée (mp4, mov, avi…).",
                   "Parcourir…", self._on_pick_video).pack(fill="x", pady=(0, 14))

        self._card(content, "Flux NDI",
                   "Se connecter à une source NDI sur le réseau (OBS, caméra…).",
                   "Choisir un flux", self._on_open_ndi).pack(fill="x")

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
        # Footer EN PREMIER (side=bottom) pour qu'il reste visible
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=24, pady=16)
        ctk.CTkButton(footer, text="Retour", width=110, height=36,
                      fg_color="transparent", border_width=1,
                      command=self._build_home).pack(side="left")
        self._ndi_refresh_btn = ctk.CTkButton(
            footer, text="Rafraîchir", width=120, height=36,
            command=self._refresh_ndi)
        self._ndi_refresh_btn.pack(side="right")

        self._header("Flux NDI", "Sources détectées sur le réseau")

        # Si cyndilib n'est pas dispo, affiche un message dédié plutôt qu'une stacktrace
        try:
            from capture import cyndilib_available
            ndi_ok = cyndilib_available()
        except Exception:
            ndi_ok = False
        if not ndi_ok:
            body = ctk.CTkFrame(self, fg_color="transparent")
            body.pack(expand=True, fill="both", padx=24, pady=8)
            card = ctk.CTkFrame(body, corner_radius=10)
            card.pack(fill="x", pady=(4, 8))
            ctk.CTkLabel(card, text="NDI indisponible",
                         font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))
            ctk.CTkLabel(
                card,
                text=("La bibliothèque cyndilib n'est pas installée, ou le NDI\n"
                      "Runtime système est manquant.\n\n"
                      "Installe NDI 6 Tools (newtek.com/ndi) puis relance l'app."),
                font=ctk.CTkFont(size=11),
                justify="left",
                text_color=("gray40", "gray80")).pack(anchor="w", padx=14, pady=(0, 12))
            self._ndi_refresh_btn.configure(state="disabled")
            return

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

        self._refresh_ndi()

    # ---------- Update check ----------
    def _start_update_check(self):
        def worker():
            try:
                self._update_info = get_latest_release(GITHUB_REPO, __version__)
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
        self.after(800, self._poll_update_check)

    def _render_update_banner(self):
        for w in self._update_banner.winfo_children():
            w.destroy()
        info = self._update_info
        if not info:
            return

        bar = ctk.CTkFrame(self._update_banner, corner_radius=10,
                           fg_color=("#1e6e3a", "#1e6e3a"))
        bar.pack(fill="x", pady=(0, 8))

        if self._update_state == "idle":
            text = f"Nouvelle version disponible : {info['tag']}"
            ctk.CTkLabel(bar, text=text,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#ffffff").pack(side="left", padx=12, pady=8)
            if info.get("asset_url") and getattr(sys, "frozen", False):
                ctk.CTkButton(bar, text="Installer", width=110, height=28,
                              fg_color="#ffffff", text_color="#1e6e3a",
                              hover_color="#dddddd",
                              command=self._start_install).pack(side="right", padx=8, pady=6)
            else:
                # Pas d'asset ou pas en mode buildé : on garde le bouton Télécharger
                ctk.CTkButton(bar, text="Télécharger", width=110, height=28,
                              fg_color="#ffffff", text_color="#1e6e3a",
                              hover_color="#dddddd",
                              command=lambda: webbrowser.open(info["html_url"])).pack(side="right", padx=8, pady=6)

        elif self._update_state == "downloading":
            ctk.CTkLabel(bar, text=f"Téléchargement {info['tag']}…",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#ffffff").pack(anchor="w", padx=12, pady=(8, 2))
            self._update_pb = ctk.CTkProgressBar(bar, height=10)
            self._update_pb.set(self._update_progress)
            self._update_pb.pack(fill="x", padx=12, pady=(0, 8))

        elif self._update_state == "ready":
            ctk.CTkLabel(bar, text="Mise à jour prête, relance en cours…",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#ffffff").pack(side="left", padx=12, pady=8)

        elif self._update_state == "error":
            ctk.CTkLabel(bar, text=f"Erreur update : {self._update_error}",
                         font=ctk.CTkFont(size=11),
                         text_color="#ffffff").pack(side="left", padx=12, pady=8)
            ctk.CTkButton(bar, text="Réessayer", width=100, height=28,
                          fg_color="#ffffff", text_color="#1e6e3a",
                          command=self._start_install).pack(side="right", padx=8, pady=6)

    def _start_install(self):
        if not self._update_info or not self._update_info.get("asset_url"):
            return
        self._update_state = "downloading"
        self._update_progress = 0.0
        self._render_update_banner()

        info = self._update_info

        def worker():
            try:
                tmp = Path(tempfile.gettempdir()) / f"cabreplay-update-{info['tag']}.zip"
                def on_progress(done, total):
                    self._update_progress = (done / total) if total else 0.0
                download(info["asset_url"], tmp, on_progress=on_progress)
                # UI : passe en état "ready" puis lance l'install
                self._update_state = "ready"
                # install_and_relaunch fait sys.exit, donc on attend un poil
                # pour que le banner se rafraîchisse avant.
                self.after(200, lambda: self._do_install(tmp))
            except Exception as e:
                self._update_error = str(e)[:80]
                self._update_state = "error"
                traceback.print_exc()
        threading.Thread(target=worker, daemon=True).start()

        self.after(150, self._poll_install_progress)

    def _poll_install_progress(self):
        if not self.winfo_exists():
            return
        if self._update_state in ("downloading", "ready"):
            self._render_update_banner()
        if self._update_state == "downloading":
            self.after(150, self._poll_install_progress)
        elif self._update_state == "error":
            self._render_update_banner()

    def _do_install(self, zip_path: Path):
        try:
            install_and_relaunch(zip_path)  # fait sys.exit(0)
        except Exception as e:
            self._update_error = str(e)[:80]
            self._update_state = "error"
            self._render_update_banner()

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
