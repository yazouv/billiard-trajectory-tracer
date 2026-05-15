import sys
import threading
import time
import traceback
from pathlib import Path

import customtkinter as ctk
import cv2

import config
from capture import NdiSource, VideoSource, list_ndi_sources
from controls import Controls
from detector import DRAW_COLORS_BGR, detect_balls
from launcher import show_launcher
from recorder import PointRecorder
from table import rect_to_mask, select_table_rect
from tracker import Trajectories
from video_view import VideoView


def draw_table_outline(frame, rect):
    x, y, w, h = rect
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 1)


def draw_balls(frame, detections):
    for color, (x, y, r) in detections.items():
        bgr = DRAW_COLORS_BGR[color]
        cv2.circle(frame, (x, y), max(r, 6), bgr, 2)
        cv2.circle(frame, (x, y), 3, bgr, -1)


def _safe_list_ndi():
    try:
        return list_ndi_sources(timeout=2.0)
    except ImportError as e:
        raise RuntimeError("cyndilib n'est pas installé (pip install cyndilib)") from e


def open_source(choice):
    """choice = ('video', path) ou ('ndi', name) -> VideoSource | NdiSource."""
    mode, target = choice
    if mode == "video":
        return VideoSource(target)
    if mode == "ndi":
        return NdiSource(target)
    raise ValueError(f"Source inconnue: {mode}")


def pick_source(tk_root, default_video):
    """Ouvre le launcher et renvoie ('video'|'ndi', target). None si annulé."""
    return show_launcher(tk_root, default_video=default_video, ndi_lister=_safe_list_ndi)


def main(default_video):
    # Un unique root tkinter caché : sert de master au launcher et à Controls.
    tk_root = ctk.CTk()
    tk_root.withdraw()
    # Icône par défaut pour tous les Toplevel enfants (launcher + Réglages)
    try:
        from launcher import _icon_path
        ip = _icon_path()
        if ip:
            tk_root.iconbitmap(default=ip)
    except Exception:
        pass

    try:
        while True:
            choice = pick_source(tk_root, default_video)
            if choice is None:
                return
            try:
                cfg = config.load()
                controls = Controls(tk_root, cfg)
                _run(tk_root, choice, cfg, controls, default_video)
                break
            except RuntimeError as e:
                print(f"Source indisponible : {e}")
                # On retourne au menu pour permettre un autre choix
                continue
    finally:
        try:
            tk_root.destroy()
        except Exception:
            pass


def _default_captures_dir():
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parent.parent
    return root / "captures"


def _ensure_dir(p):
    p = Path(p) if p else _default_captures_dir()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        p = _default_captures_dir()
        p.mkdir(parents=True, exist_ok=True)
    return p


def _read_first_frame(src, mode, timeout=8.0):
    """Pour NDI, on retry pendant `timeout` secondes : la 1re frame arrive en différé."""
    import time
    deadline = time.monotonic() + timeout
    while True:
        ok, frame = src.read()
        if ok and frame is not None:
            return frame
        if mode != "ndi" or time.monotonic() >= deadline:
            return None
        time.sleep(0.05)


def _run(tk_root, choice, cfg, controls, default_video):

    src = open_source(choice)
    print(f"Source: {choice[1]}  {src.width}x{src.height} @ {src.fps:.1f} fps")

    first = _read_first_frame(src, choice[0])
    if first is None:
        raise RuntimeError("Source vide (aucune frame reçue dans le délai imparti)")

    if cfg.get("table_rect"):
        table_rect = tuple(cfg["table_rect"])
        print(f"Zone chargée depuis config : {table_rect}")
    else:
        table_rect = select_table_rect(first)
        config.save({"table_rect": list(table_rect)})
        print(f"Zone sélectionnée : {table_rect}")
    table_mask = rect_to_mask(first.shape, table_rect)

    trails = Trajectories(fps=src.fps)
    current_mode = choice[0]

    video_view = VideoView(tk_root, title="CAB Replay",
                           initial_size=(first.shape[1], first.shape[0]))
    rec_fps = src.fps if src.fps >= 5 else 30.0
    recorder = PointRecorder(_ensure_dir(controls.captures_dir()), fps=rec_fps)
    if not controls.captures_dir():
        controls.var_captures_dir.set(str(_default_captures_dir()))

    # État partagé worker <-> tk. Lock protège les swaps de gros objets.
    state_lock = threading.Lock()
    state = {
        "src": src,
        "trails": trails,
        "table_mask": table_mask,
        "table_rect": table_rect,
        "recorder": recorder,
        "mode": current_mode,
        "running": True,
        "worker_alive": False,
        "paused": False,
        "seek_to": None,
        "last_display": first,
        "last_position": 0,
        # snapshot des options de rendu, mis à jour par le thread tk
        "render_state": {
            "smooth_window": controls.smooth_window(),
            "show_balls": controls.show_balls(),
            "show_table_rect": controls.show_table_rect(),
            "visible_trails": controls.visible_trails(),
        },
    }

    def worker():
        state["worker_alive"] = True
        target_dt = 1.0 / max(state["src"].fps, 1.0)
        next_due = time.monotonic()
        while state["running"]:
            if state["paused"]:
                time.sleep(0.03)
                next_due = time.monotonic()
                continue

            with state_lock:
                seek = state["seek_to"]
                state["seek_to"] = None
            if seek is not None:
                try:
                    state["src"].seek(seek)
                    state["trails"].clear()
                except Exception as e:
                    print(f"Seek error: {e}")

            ok, fr = state["src"].read()
            if not ok:
                if state["mode"] == "ndi":
                    time.sleep(0.01)
                    continue
                state["running"] = False
                break

            with state_lock:
                mask = state["table_mask"]
                rect = state["table_rect"]
                rs = state["render_state"]
                trails_ref = state["trails"]
                recorder_ref = state["recorder"]

            detections = detect_balls(fr, roi_mask=mask)
            trails_ref.configure(smooth_window=rs.get("smooth_window", 3))
            cleared = trails_ref.update(detections)

            display = fr.copy()
            trails_ref.draw(display, DRAW_COLORS_BGR,
                            visible=rs.get("visible_trails"))
            if rs.get("show_table_rect"):
                draw_table_outline(display, rect)
            if rs.get("show_balls"):
                draw_balls(display, detections)

            recorder_ref.write(display)
            if cleared:
                recorder_ref.rotate()

            with state_lock:
                state["last_display"] = display
                state["last_position"] = getattr(state["src"], "position", 0)

            next_due += target_dt
            sleep_for = next_due - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            elif sleep_for < -0.5:
                next_due = time.monotonic()  # on est trop en retard, on recale

        state["worker_alive"] = False

    def start_worker():
        if state["worker_alive"]:
            return
        state["running"] = True
        threading.Thread(target=worker, daemon=True).start()

    start_worker()

    # Render tk : léger, juste affiche la dernière frame et gère les events.
    RENDER_DT_MS = 33  # ~30 fps de rendu, indépendant du fps source

    def render():
        if not state["running"]:
            return
        # Snapshot des options de rendu (lecture des vars tk depuis le main thread)
        new_rs = {
            "smooth_window": controls.smooth_window(),
            "show_balls": controls.show_balls(),
            "show_table_rect": controls.show_table_rect(),
            "visible_trails": controls.visible_trails(),
        }
        with state_lock:
            state["render_state"] = new_rs
            display = state["last_display"]
            position = state["last_position"]

        if display is not None:
            video_view.show_frame(display)

        controls.set_playback_info(
            position=position,
            total=getattr(state["src"], "frame_count", 0),
            fps=state["src"].fps,
            seekable=getattr(state["src"], "seekable", False),
        )

        seek_to = controls.consume_seek()
        if seek_to is not None:
            with state_lock:
                state["seek_to"] = seek_to

        state["paused"] = controls.is_paused()

        if video_view.quit_requested() or controls.quit_requested():
            state["running"] = False
            tk_root.quit()
            return

        # Touches
        key = video_view.consume_key() or controls.consume_key() or 0
        if key in (ord('q'), 27):
            state["running"] = False
            tk_root.quit()
            return
        elif key == ord(' '):
            controls.toggle_pause()
        elif key == ord('c'):
            with state_lock:
                state["trails"].clear()
        elif key == ord('r'):
            # Pause worker pendant qu'on dialogue
            was_paused = state["paused"]
            state["paused"] = True
            with state_lock:
                snap = state["last_display"]
            if snap is not None:
                try:
                    new_rect = select_table_rect(snap.copy())
                    with state_lock:
                        state["table_rect"] = new_rect
                        state["table_mask"] = rect_to_mask(snap.shape, new_rect)
                        state["trails"].clear()
                    config.save({"table_rect": list(new_rect)})
                    print(f"Zone redéfinie : {new_rect}")
                except Exception as e:
                    print(f"selectROI error: {e}")
            state["paused"] = was_paused
        elif key == ord('m'):
            new_choice = pick_source(tk_root, default_video)
            if new_choice is not None:
                if _switch_source(state, state_lock, controls, new_choice, tk_root):
                    start_worker()
        elif key == ord('s'):
            with state_lock:
                rect = state["table_rect"]
            config.save(controls.snapshot() | {"table_rect": list(rect)})
            print("Config sauvegardée.")

        if controls.consume_save_request():
            with state_lock:
                rect = state["table_rect"]
            config.save(controls.snapshot() | {"table_rect": list(rect)})
            print("Config sauvegardée.")

        if controls.consume_save_last():
            with state_lock:
                state["recorder"].dir = _ensure_dir(controls.captures_dir())
                started = state["recorder"].save_last(
                    on_done=lambda p: print(f"Dernier point sauvé : {p}" if p else
                                            "Erreur sauvegarde dernier point."))
            print("Encodage du dernier point en cours…" if started else
                  "Aucun dernier point disponible.")
        if controls.consume_save_prev():
            with state_lock:
                state["recorder"].dir = _ensure_dir(controls.captures_dir())
                started = state["recorder"].save_prev(
                    on_done=lambda p: print(f"Avant-dernier point sauvé : {p}" if p else
                                            "Erreur sauvegarde avant-dernier."))
            print("Encodage de l'avant-dernier point en cours…" if started else
                  "Aucun avant-dernier point disponible.")

        tk_root.after(RENDER_DT_MS, render)

    tk_root.after(0, render)
    tk_root.mainloop()

    state["running"] = False
    # Attend que le worker sorte avant de release les ressources
    deadline = time.monotonic() + 1.0
    while state["worker_alive"] and time.monotonic() < deadline:
        time.sleep(0.02)
    state["recorder"].close()
    state["src"].release()
    try:
        video_view.destroy()
    except Exception:
        pass
    controls.close()
    cv2.destroyAllWindows()


def _switch_source(state, state_lock, controls, new_choice, tk_root):
    """Stoppe le worker, swap la source. Renvoie True si OK (caller doit relancer worker)."""
    state["running"] = False
    # Attend que le worker sorte
    deadline = time.monotonic() + 1.0
    while state["worker_alive"] and time.monotonic() < deadline:
        time.sleep(0.02)
    try:
        state["src"].release()
    except Exception:
        pass

    try:
        new_src = open_source(new_choice)
    except Exception as e:
        print(f"Erreur ouverture source : {e}")
        tk_root.quit()
        return False

    fr2 = _read_first_frame(new_src, new_choice[0])
    if fr2 is None:
        print("Source vide.")
        tk_root.quit()
        return False

    with state_lock:
        state["src"] = new_src
        state["mode"] = new_choice[0]
        state["trails"] = Trajectories(fps=new_src.fps)
        state["table_mask"] = rect_to_mask(fr2.shape, state["table_rect"])
        state["last_display"] = fr2
        state["recorder"].close()
        state["recorder"] = PointRecorder(
            _ensure_dir(controls.captures_dir()),
            fps=new_src.fps if new_src.fps >= 5 else 30.0,
        )
    print(f"Source: {new_choice[1]}  {new_src.width}x{new_src.height} @ {new_src.fps:.1f} fps")
    return True


def _default_video_path():
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parent.parent
    return root / "datas" / "video.mp4"


if __name__ == "__main__":
    # En exe windowed (console=False), sys.stdout/stderr peuvent etre None
    # et faire crasher les print(). On redirige vers un fichier log.
    if getattr(sys, "frozen", False):
        log_path = Path(sys.executable).resolve().parent / "cabreplay.log"
        try:
            sys.stdout = open(log_path, "a", buffering=1, encoding="utf-8")
            sys.stderr = sys.stdout
        except OSError:
            import os
            sys.stdout = open(os.devnull, "w")
            sys.stderr = sys.stdout

    default = sys.argv[1] if len(sys.argv) > 1 else str(_default_video_path())
    try:
        main(default)
    except Exception:
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            log = Path(sys.executable).resolve().parent / "crash.log"
            try:
                with open(log, "w", encoding="utf-8") as f:
                    traceback.print_exc(file=f)
            except OSError:
                pass
        raise
