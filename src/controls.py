"""Fenêtre Réglages (customtkinter), pilotée à la main via update() depuis la boucle OpenCV."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk


def _icon_path():
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    p = base / "assets" / "icon.ico"
    return str(p) if p.exists() else None


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# Pastilles de couleur affichées à côté des switches de trajectoire
_BALL_DOTS = {
    "white":  "#ffffff",
    "yellow": "#ffd000",
    "red":    "#ff3a3a",
}


class Controls(ctk.CTkToplevel):
    """Fenêtre de réglages. Vit à côté de la fenêtre OpenCV ; refresh() = update()."""

    def __init__(self, master, initial):
        super().__init__(master)
        self.title("Réglages — CAB Replay")
        self.geometry("880x720")
        self.minsize(780, 560)
        # Non-resizable : le resize tkinter pendant la boucle cv2 cause des
        # crashs GIL. Le contenu est de toute facon dans un scrollable frame.
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        p = _icon_path()
        if p:
            try:
                self.iconbitmap(p)
            except Exception:
                pass
        self._save_pending = False
        self._quit_pending = False  # croix Reglages cliquée
        self._save_last_pending = False
        self._save_prev_pending = False
        self._obs_stop_pending = False
        self._promote_pending = False
        self._key_queue = []  # touches récupérées via tkinter, drainées par main.py
        self._last_update_ts = 0.0
        self.var_captures_dir = ctk.StringVar(value=str(initial.get("captures_dir", "")))
        self.var_captures_keep = ctk.StringVar(value=str(int(initial.get("captures_keep", 20))))

        # OBS
        self.var_obs_enabled  = ctk.BooleanVar(value=bool(initial.get("obs_enabled", False)))
        self.var_obs_host     = ctk.StringVar(value=str(initial.get("obs_host", "localhost")))
        self.var_obs_port     = ctk.StringVar(value=str(initial.get("obs_port", 4455)))
        self.var_obs_password = ctk.StringVar(value=str(initial.get("obs_password", "")))
        self.var_obs_scene    = ctk.StringVar(value=str(initial.get("obs_scene", "Replay")))
        self.var_obs_source   = ctk.StringVar(value=str(initial.get("obs_source", "CABReplayMedia")))
        self._obs_test_cb = None  # main.py injectera un callback

        # Lecture (slider + play/pause)
        self._paused = False
        self._seek_request = None        # frame_idx à demander à main.py
        self._slider_programmatic = False
        self._playback_total = 0
        self._playback_position = 0
        self._playback_fps = 30.0
        self._playback_seekable = False
        # Bind les raccourcis app pour qu'ils marchent même si Reglages a le focus
        for key in ("space", "m", "M", "r", "R", "c", "C", "s", "S",
                    "q", "Q", "Escape"):
            self.bind(f"<{key}>" if len(key) > 1 else f"<KeyPress-{key}>",
                      self._on_key)

        # Variables tk
        self.var_smooth        = ctk.IntVar(value=int(initial.get("smooth_window", 3)))
        self.var_show_balls    = ctk.BooleanVar(value=bool(initial.get("show_balls", False)))
        self.var_show_rect     = ctk.BooleanVar(value=bool(initial.get("show_table_rect", True)))
        self.var_trail_white   = ctk.BooleanVar(value=bool(initial.get("show_trail_white", True)))
        self.var_trail_yellow  = ctk.BooleanVar(value=bool(initial.get("show_trail_yellow", True)))
        self.var_trail_red     = ctk.BooleanVar(value=bool(initial.get("show_trail_red", True)))

        self._build_ui()
        self.update()

    # ---------- UI ----------
    def _build_ui(self):
        # Header fixe en haut + footer (bouton Save) en bas + 2 colonnes au milieu
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 8))
        ctk.CTkLabel(header, text="Réglages",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=18, pady=12)
        ctk.CTkButton(footer, text="Sauvegarder la config", height=38,
                      command=self._on_save_clicked).pack(fill="x")

        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        left = ctk.CTkScrollableFrame(
            cols, fg_color="transparent", label_text="Paramètres",
            label_font=ctk.CTkFont(size=14, weight="bold"))
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        right = ctk.CTkScrollableFrame(
            cols, fg_color="transparent", label_text="Replays",
            label_font=ctk.CTkFont(size=14, weight="bold"))
        right.pack(side="left", fill="both", expand=True, padx=(4, 0))

        self._build_left_column(left)
        self._build_right_column(right)

    def _build_left_column(self, outer):
        # Section Lecture (slider + play/pause), masquée si la source ne supporte pas
        self._playback_section = self._section(outer, "Lecture")
        self._build_playback_ui(self._playback_section)
        self._playback_section.pack_forget()

        # Section Affichage
        aff = self._section(outer, "Affichage")
        self._switch(aff, "Rectangle de la table", self.var_show_rect)
        self._switch(aff, "Contours des billes", self.var_show_balls)

        # Section Trajectoires
        traj = self._section(outer, "Trajectoires")
        self._switch(traj, "Bille blanche", self.var_trail_white, dot=_BALL_DOTS["white"])
        self._switch(traj, "Bille jaune",   self.var_trail_yellow, dot=_BALL_DOTS["yellow"])
        self._switch(traj, "Bille rouge",   self.var_trail_red,    dot=_BALL_DOTS["red"])

        # Section Lissage
        lis = self._section(outer, "Lissage")
        row = ctk.CTkFrame(lis, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(6, 4))
        ctk.CTkLabel(row, text="Fenêtre",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self._smooth_label = ctk.CTkLabel(
            row, text=str(self.var_smooth.get()),
            font=ctk.CTkFont(size=13, weight="bold"))
        self._smooth_label.pack(side="right")
        slider = ctk.CTkSlider(
            lis, from_=1, to=31, number_of_steps=30,
            variable=self.var_smooth, command=self._on_smooth_change,
        )
        slider.pack(fill="x", padx=14, pady=(0, 12))

        # Section raccourcis
        shortcuts = ctk.CTkFrame(outer, corner_radius=10)
        shortcuts.pack(fill="x", pady=(4, 12))
        ctk.CTkLabel(shortcuts, text="Raccourcis (fenêtre vidéo)",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))
        for line in [
            "ESPACE — pause / lecture",
            "M — menu (changer de source)",
            "R — redéfinir la zone",
            "C — effacer les traces",
            "Q / Échap — quitter",
        ]:
            ctk.CTkLabel(shortcuts, text=line,
                         font=ctk.CTkFont(size=11),
                         text_color=("gray45", "gray75")).pack(anchor="w", padx=14)
        ctk.CTkLabel(shortcuts, text="").pack(pady=2)

    def _build_right_column(self, outer):
        # Bandeau d'état live (point en cours / clipable / idle)
        self._status_card = ctk.CTkFrame(outer, corner_radius=10,
                                         fg_color=("gray85", "gray20"))
        self._status_card.pack(fill="x", pady=(0, 10))
        self._status_dot = ctk.CTkLabel(
            self._status_card, text="●", font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("gray45", "gray60"))
        self._status_dot.pack(side="left", padx=(14, 8), pady=10)
        self._status_text = ctk.CTkLabel(
            self._status_card, text="En attente d'un point…",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("gray25", "gray85"), anchor="w")
        self._status_text.pack(side="left", fill="x", expand=True, pady=10)
        self._status_subtext = ctk.CTkLabel(
            self._status_card, text="", font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray60"))
        self._status_subtext.pack(side="right", padx=(8, 14), pady=10)

        # Section captures de point
        cap = self._section(outer, "Captures du point")
        ctk.CTkLabel(cap,
                     text="Exporte le point (vidéo + traces dessinées) en MP4.",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray70")).pack(anchor="w", padx=14)
        btns = ctk.CTkFrame(cap, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(8, 8))
        self._btn_save_last = ctk.CTkButton(
            btns, text="Dernier point", height=32,
            command=self._on_save_last,
            border_width=2)
        self._btn_save_last.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._btn_save_prev = ctk.CTkButton(
            btns, text="Avant-dernier", height=32,
            command=self._on_save_prev,
            border_width=2)
        self._btn_save_prev.pack(side="left", expand=True, fill="x", padx=(6, 0))
        # Couleurs mémorisées pour le toggle dispo/indispo
        self._btn_default_fg = self._btn_save_last.cget("fg_color")

        # Bouton "Couper le replay" : affiché seulement quand OBS est sur la scène Replay
        self._obs_stop_row = ctk.CTkFrame(cap, fg_color="transparent")
        # Pas de pack ici : géré par set_on_replay_scene()
        ctk.CTkButton(self._obs_stop_row,
                      text="⏹  Couper le replay en cours", height=30,
                      fg_color=("#b03a3a", "#a33"),
                      hover_color=("#8a2a2a", "#822"),
                      command=self._on_obs_stop).pack(fill="x")
        self._obs_stop_visible = False

        # Bouton highlight
        ctk.CTkButton(cap, text="★  Garder le dernier en highlight", height=30,
                      fg_color=("#b58a00", "#caa83a"),
                      hover_color=("#8c6b00", "#a18225"),
                      text_color=("white", "black"),
                      command=self._on_promote).pack(fill="x", padx=14, pady=(0, 8))
        self._promote_status_label = ctk.CTkLabel(
            cap, text="", font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray70"), anchor="w", justify="left",
            wraplength=370)
        self._promote_status_label.pack(fill="x", padx=14, pady=(0, 8))

        # Rotation auto
        row = ctk.CTkFrame(cap, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(2, 8))
        ctk.CTkLabel(row, text="Garder les N derniers :", width=170, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkEntry(row, textvariable=self.var_captures_keep,
                     width=70, height=28).pack(side="left")

        # Dossier des replays
        ctk.CTkLabel(cap, text="Dossier de sortie :",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray45", "gray70")).pack(anchor="w", padx=14, pady=(4, 0))
        row = ctk.CTkFrame(cap, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(4, 12))
        self._dir_label = ctk.CTkLabel(
            row, textvariable=self.var_captures_dir,
            font=ctk.CTkFont(size=11), anchor="w",
            text_color=("gray30", "gray85"))
        self._dir_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Changer…", width=90, height=28,
                      command=self._on_pick_dir).pack(side="right", padx=(8, 0))

        # Section OBS
        obs = self._section(outer, "OBS (lecture auto du replay)")
        self._switch(obs, "Activer la lecture auto dans OBS", self.var_obs_enabled)
        self._labeled_entry(obs, "Hôte", self.var_obs_host)
        self._labeled_entry(obs, "Port", self.var_obs_port)
        self._labeled_entry(obs, "Mot de passe", self.var_obs_password, show="*")
        self._labeled_entry(obs, "Scène", self.var_obs_scene)
        self._labeled_entry(obs, "Source média", self.var_obs_source)
        row = ctk.CTkFrame(obs, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(4, 4))
        ctk.CTkButton(row, text="Tester la connexion", height=30,
                      command=self._on_obs_test).pack(side="left", expand=True, fill="x")
        self._obs_status_label = ctk.CTkLabel(
            obs, text="", font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray70"), anchor="w", justify="left",
            wraplength=370)
        self._obs_status_label.pack(fill="x", padx=14, pady=(2, 10))

    def _build_playback_ui(self, parent):
        # Ligne 1 : bouton play/pause + label MM:SS / MM:SS
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(6, 4))
        self._play_btn = ctk.CTkButton(
            row, text="⏸  Pause", width=110, height=32,
            command=self._on_toggle_play)
        self._play_btn.pack(side="left")
        self._time_label = ctk.CTkLabel(
            row, text="00:00 / 00:00",
            font=ctk.CTkFont(size=12, weight="bold"))
        self._time_label.pack(side="right")

        # Ligne 2 : slider de position
        self._slider_var = ctk.DoubleVar(value=0.0)
        self._position_slider = ctk.CTkSlider(
            parent, from_=0, to=1, number_of_steps=1000,
            variable=self._slider_var,
            command=self._on_slider_move,
        )
        self._position_slider.pack(fill="x", padx=14, pady=(2, 12))

    def _section(self, parent, title):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card, text=title,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("gray40", "gray80")).pack(anchor="w", padx=14, pady=(10, 4))
        return card

    def _labeled_entry(self, parent, label, var, show=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(row, text=label, width=110, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        kwargs = {"textvariable": var, "height": 28}
        if show:
            kwargs["show"] = show
        ctk.CTkEntry(row, **kwargs).pack(side="left", expand=True, fill="x")

    def _switch(self, parent, label, var, dot=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        if dot:
            d = ctk.CTkFrame(row, width=12, height=12, corner_radius=6, fg_color=dot)
            d.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkSwitch(row, text="", variable=var,
                      onvalue=True, offvalue=False).pack(side="right")

    # ---------- Callbacks ----------
    def _on_smooth_change(self, value):
        self._smooth_label.configure(text=str(int(float(value))))

    def _on_save_clicked(self):
        self._save_pending = True

    def _on_obs_stop(self):
        self._obs_stop_pending = True

    def set_replay_state(self, st):
        """Met à jour bandeau d'état + couleurs des boutons Dernier/Avant-dernier.
        st = dict {current_seconds, has_last, has_prev, rotate_age}."""
        if not hasattr(self, "_status_text"):
            return
        cur_s = float(st.get("current_seconds") or 0.0)
        has_last = bool(st.get("has_last"))
        has_prev = bool(st.get("has_prev"))
        rotate_age = st.get("rotate_age")
        flash = rotate_age is not None and rotate_age < 2.5

        # Bandeau
        if flash:
            dot_col = ("#1e7d2e", "#7be08a")
            text = "✓ Nouveau point capturé"
            sub = f"{rotate_age:.1f}s"
        elif cur_s > 0.05:
            dot_col = ("#c24a00", "#ff9c5a")
            text = "● Point en cours"
            sub = f"{cur_s:.1f}s"
        elif has_last:
            dot_col = ("#1e7d2e", "#7be08a")
            text = "Prêt à clipper"
            sub = ""
        else:
            dot_col = ("gray45", "gray60")
            text = "En attente d'un point…"
            sub = ""
        try:
            self._status_dot.configure(text_color=dot_col)
            self._status_text.configure(text=text)
            self._status_subtext.configure(text=sub)
            # Tinte la card en mode flash
            if flash:
                self._status_card.configure(fg_color=("#d5f0d5", "#1b3a22"))
            else:
                self._status_card.configure(fg_color=("gray85", "gray20"))
        except Exception:
            pass

        # Boutons : bordure verte quand clipable, grisés sinon
        self._style_save_button(self._btn_save_last, has_last)
        self._style_save_button(self._btn_save_prev, has_prev)

    def _style_save_button(self, btn, available):
        try:
            if available:
                btn.configure(state="normal",
                              fg_color=self._btn_default_fg,
                              border_color=("#1e7d2e", "#7be08a"),
                              text_color=("white", "white"))
            else:
                btn.configure(state="disabled",
                              fg_color=("gray70", "gray30"),
                              border_color=("gray70", "gray30"),
                              text_color=("gray45", "gray55"))
        except Exception:
            pass

    def set_on_replay_scene(self, on_scene):
        """Affiche/cache le bouton 'Couper le replay' selon que OBS est sur la scène Replay."""
        if not hasattr(self, "_obs_stop_row"):
            return
        on_scene = bool(on_scene)
        if on_scene == self._obs_stop_visible:
            return
        if on_scene:
            self._obs_stop_row.pack(fill="x", padx=14, pady=(0, 8))
        else:
            self._obs_stop_row.pack_forget()
        self._obs_stop_visible = on_scene

    def _on_promote(self):
        self._promote_pending = True

    def consume_promote(self):
        if self._promote_pending:
            self._promote_pending = False
            return True
        return False

    def set_promote_status(self, text, ok=True, auto_clear_ms=4000):
        if not hasattr(self, "_promote_status_label"):
            return
        color = ("#1e7d2e", "#7be08a") if ok else ("#a01919", "#ff6b6b")
        self._promote_status_label.configure(text=text, text_color=color)
        # Token pour annuler un clear précédent si on clique à nouveau entre-temps
        token = self._promote_status_token = (self._promote_status_token + 1
                                              if hasattr(self, "_promote_status_token")
                                              else 1)
        if auto_clear_ms and auto_clear_ms > 0:
            def _clear():
                if getattr(self, "_promote_status_token", None) == token:
                    try:
                        self._promote_status_label.configure(text="")
                    except Exception:
                        pass
            try:
                self.after(int(auto_clear_ms), _clear)
            except Exception:
                pass

    def captures_keep(self):
        try:
            return max(1, int(str(self.var_captures_keep.get()).strip() or "20"))
        except ValueError:
            return 20

    def consume_obs_stop(self):
        if self._obs_stop_pending:
            self._obs_stop_pending = False
            return True
        return False

    def _on_obs_test(self):
        if self._obs_test_cb is None:
            self._set_obs_status("Aucun callback enregistré.", ok=False)
            return
        self._set_obs_status("Connexion en cours…", ok=None)
        self._obs_test_cb(self.obs_settings())

    def set_obs_test_callback(self, cb):
        """cb(settings_dict) -> appelé quand l'utilisateur clique Tester."""
        self._obs_test_cb = cb

    def _set_obs_status(self, text, ok=True):
        color = ("#1e7d2e", "#7be08a") if ok is True else \
                ("#a01919", "#ff6b6b") if ok is False else \
                ("gray45", "gray70")
        self._obs_status_label.configure(text=text, text_color=color)

    def set_obs_test_result(self, ok, message):
        prefix = "✓ " if ok else "✗ "
        self._set_obs_status(prefix + message, ok=ok)

    def _on_save_last(self):
        self._save_last_pending = True

    def _on_save_prev(self):
        self._save_prev_pending = True

    def _on_toggle_play(self):
        self._paused = not self._paused
        self._refresh_play_button()

    def _refresh_play_button(self):
        if not hasattr(self, "_play_btn"):
            return
        if self._paused:
            self._play_btn.configure(text="▶  Lecture")
        else:
            self._play_btn.configure(text="⏸  Pause")

    def _on_slider_move(self, value):
        # Si on a mis le slider à jour nous-même (suivi de lecture), on ignore
        if self._slider_programmatic:
            return
        self._seek_request = int(float(value))

    # --- API exposée à main.py ---
    def is_paused(self):
        return self._paused

    def toggle_pause(self):
        self._on_toggle_play()

    def set_paused(self, value):
        self._paused = bool(value)
        self._refresh_play_button()

    def consume_seek(self):
        r = self._seek_request
        self._seek_request = None
        return r

    def set_playback_info(self, position, total, fps, seekable):
        """Appelé par main.py à chaque frame pour mettre à jour le slider/time."""
        self._playback_fps = max(float(fps), 1.0)
        self._playback_seekable = bool(seekable) and total > 0

        if self._playback_seekable:
            # Affiche la section si pas encore
            if not self._playback_section.winfo_ismapped():
                # Reaffiche au-dessus de tout, donc on doit la repack en debut.
                # CTkScrollableFrame ne supporte pas insert ; on la pack avant tout
                # le reste. Comme l'UI est figée après _build_ui, on accepte
                # qu'elle apparaisse à la fin.
                self._playback_section.pack(fill="x", pady=(0, 10), before=None)
            self._playback_total = int(total)
            self._playback_position = int(position)
            # Slider 0..total-1, échelle adaptée
            try:
                if abs(self._position_slider.cget("to") - max(1, total - 1)) > 0.5:
                    self._position_slider.configure(
                        to=max(1, total - 1),
                        number_of_steps=min(1000, max(1, total - 1)),
                    )
            except Exception:
                pass
            # Mise à jour de la position sans déclencher le callback
            self._slider_programmatic = True
            try:
                self._slider_var.set(self._playback_position)
            finally:
                self._slider_programmatic = False
            # Time label
            cur = self._fmt_time(self._playback_position / self._playback_fps)
            tot = self._fmt_time(self._playback_total / self._playback_fps)
            self._time_label.configure(text=f"{cur} / {tot}")
        else:
            if self._playback_section.winfo_ismapped():
                self._playback_section.pack_forget()

    @staticmethod
    def _fmt_time(seconds):
        s = int(max(0, seconds))
        return f"{s // 60:02d}:{s % 60:02d}"

    def _on_pick_dir(self):
        current = self.var_captures_dir.get() or None
        chosen = filedialog.askdirectory(
            parent=self, title="Choisir le dossier des replays",
            initialdir=current if current and Path(current).exists() else None,
        )
        if chosen:
            self.var_captures_dir.set(chosen)

    def _on_close_attempt(self):
        # Croix cliquée : signale au main loop de quitter proprement
        self._quit_pending = True

    def _on_key(self, event):
        # Mappe vers les codes que main.py attend (mêmes que cv2.waitKey)
        keysym = event.keysym
        mapping = {
            "space": ord(" "),
            "Escape": 27,
        }
        if keysym in mapping:
            self._key_queue.append(mapping[keysym])
        elif len(keysym) == 1:
            # On force minuscule pour matcher ord('r'), ord('m'), etc.
            self._key_queue.append(ord(keysym.lower()))

    # ---------- API utilisée par main.py ----------
    def refresh(self):
        # Limite la fréquence d'update() : éviter la réentrance pendant un
        # redraw OpenCV et réduire le risque de crash GIL pendant les events tk.
        now = time.monotonic()
        if now - self._last_update_ts < 0.1:
            return
        self._last_update_ts = now
        try:
            self.update_idletasks()
            self.update()
        except Exception:
            pass

    def smooth_window(self):
        return max(1, int(self.var_smooth.get()))

    def show_balls(self):
        return bool(self.var_show_balls.get())

    def show_table_rect(self):
        return bool(self.var_show_rect.get())

    def visible_trails(self):
        return {
            "white":  bool(self.var_trail_white.get()),
            "yellow": bool(self.var_trail_yellow.get()),
            "red":    bool(self.var_trail_red.get()),
        }

    def captures_dir(self):
        return self.var_captures_dir.get().strip()

    def obs_settings(self):
        try:
            port = int(str(self.var_obs_port.get()).strip() or "4455")
        except ValueError:
            port = 4455
        return {
            "enabled": bool(self.var_obs_enabled.get()),
            "host": self.var_obs_host.get().strip() or "localhost",
            "port": port,
            "password": self.var_obs_password.get(),
            "scene": self.var_obs_scene.get().strip() or "Replay",
            "source": self.var_obs_source.get().strip() or "CABReplayMedia",
        }

    def snapshot(self):
        trails = self.visible_trails()
        return {
            "smooth_window": self.smooth_window(),
            "show_balls": self.show_balls(),
            "show_table_rect": self.show_table_rect(),
            "show_trail_white": trails["white"],
            "show_trail_yellow": trails["yellow"],
            "show_trail_red": trails["red"],
            "captures_dir": self.captures_dir(),
            "captures_keep": self.captures_keep(),
            "obs_enabled": bool(self.var_obs_enabled.get()),
            "obs_host": self.var_obs_host.get().strip() or "localhost",
            "obs_port": self.obs_settings()["port"],
            "obs_password": self.var_obs_password.get(),
            "obs_scene": self.var_obs_scene.get().strip() or "Replay",
            "obs_source": self.var_obs_source.get().strip() or "CABReplayMedia",
        }

    def quit_requested(self):
        return self._quit_pending

    def consume_key(self):
        """Renvoie le code de la prochaine touche pressée dans Reglages, ou None."""
        if self._key_queue:
            return self._key_queue.pop(0)
        return None

    def consume_save_request(self):
        """Renvoie True une fois si l'utilisateur a cliqué sur 'Sauvegarder'."""
        if self._save_pending:
            self._save_pending = False
            return True
        return False

    def consume_save_last(self):
        if self._save_last_pending:
            self._save_last_pending = False
            return True
        return False

    def consume_save_prev(self):
        if self._save_prev_pending:
            self._save_prev_pending = False
            return True
        return False

    def close(self):
        try:
            self.destroy()
        except Exception:
            pass
