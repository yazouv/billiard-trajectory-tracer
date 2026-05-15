import sys
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

WINDOW = "CAB Replay"


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

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    paused = False
    frame = first
    detections = {}

    # Le seek se fait via le slider de la fenêtre Réglages (controls)

    rec_fps = src.fps if src.fps >= 5 else 30.0
    recorder = PointRecorder(_ensure_dir(controls.captures_dir()), fps=rec_fps)
    target_frame_ms = 1000.0 / rec_fps
    import time as _time
    # Si le user n'avait jamais choisi, on affiche le défaut dans Réglages
    if not controls.captures_dir():
        controls.var_captures_dir.set(str(_default_captures_dir()))

    while True:
        loop_start = _time.monotonic()
        if not paused:
            ok, frame = src.read()
            if not ok:
                if current_mode == "ndi":
                    cv2.waitKey(10)
                    continue
                break
            detections = detect_balls(frame, roi_mask=table_mask)
            trails.configure(smooth_window=controls.smooth_window())
            cleared = trails.update(detections)

        display = frame.copy()
        trails.draw(display, DRAW_COLORS_BGR, visible=controls.visible_trails())
        if controls.show_table_rect():
            draw_table_outline(display, table_rect)
        if controls.show_balls():
            draw_balls(display, detections)

        # Enregistre la frame affichée (avec traces + overlays) dans le mp4 en cours
        if not paused:
            recorder.write(display)
            if cleared:
                recorder.rotate()

        # Synchronise l'état de lecture vers Réglages (slider + time label)
        controls.set_playback_info(
            position=getattr(src, "position", 0),
            total=getattr(src, "frame_count", 0),
            fps=src.fps,
            seekable=getattr(src, "seekable", False),
        )

        # Demande de seek faite par l'utilisateur sur le slider
        seek_to = controls.consume_seek()
        if seek_to is not None:
            try:
                src.seek(seek_to)
                trails.clear()
            except Exception as e:
                print(f"Seek error: {e}")

        # Synchronise pause depuis Réglages
        paused = controls.is_paused()

        cv2.imshow(WINDOW, display)
        controls.refresh()

        # Croix de la fenêtre vidéo cliquée
        try:
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break
        # Croix de la fenêtre Réglages cliquée
        if controls.quit_requested():
            break

        # Pacing : on vise target_frame_ms par tour pour respecter le fps
        elapsed_ms = (_time.monotonic() - loop_start) * 1000.0
        wait_ms = max(1, int(target_frame_ms - elapsed_ms))
        key = cv2.waitKey(wait_ms) & 0xFF
        if key == 255:  # rien depuis OpenCV → vérifie côté Réglages
            from_ctrl = controls.consume_key()
            if from_ctrl is not None:
                key = from_ctrl & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord(' '):
            controls.toggle_pause()
            paused = controls.is_paused()
        elif key == ord('c'):
            trails.clear()
        elif key == ord('r'):
            new_rect = select_table_rect(frame)
            table_rect = new_rect
            table_mask = rect_to_mask(frame.shape, table_rect)
            trails.clear()
            config.save({"table_rect": list(table_rect)})
            print(f"Zone redéfinie : {table_rect}")
        elif key == ord('m'):
            new_choice = pick_source(tk_root, default_video)
            if new_choice is None:
                continue
            src.release()
            try:
                src = open_source(new_choice)
            except Exception as e:
                print(f"Erreur ouverture source : {e}")
                break
            current_mode = new_choice[0]
            trails = Trajectories(fps=src.fps)
            frame = _read_first_frame(src, current_mode)
            if frame is None:
                print("Source vide.")
                break
            table_mask = rect_to_mask(frame.shape, table_rect)
            recorder.close()
            recorder = PointRecorder(
                _ensure_dir(controls.captures_dir()),
                fps=src.fps if src.fps >= 5 else 30.0,
            )
            print(f"Source: {new_choice[1]}  {src.width}x{src.height} @ {src.fps:.1f} fps")
        elif key == ord('s'):
            config.save(controls.snapshot() | {"table_rect": list(table_rect)})
            print("Config sauvegardée.")

        if controls.consume_save_request():
            config.save(controls.snapshot() | {"table_rect": list(table_rect)})
            print("Config sauvegardée.")

        if controls.consume_save_last():
            recorder.dir = _ensure_dir(controls.captures_dir())
            started = recorder.save_last(
                on_done=lambda p: print(f"Dernier point sauvé : {p}" if p else
                                        "Erreur lors de la sauvegarde du dernier point."))
            if not started:
                print("Aucun dernier point disponible (le point doit s'être terminé).")
            else:
                print("Encodage du dernier point en cours…")
        if controls.consume_save_prev():
            recorder.dir = _ensure_dir(controls.captures_dir())
            started = recorder.save_prev(
                on_done=lambda p: print(f"Avant-dernier point sauvé : {p}" if p else
                                        "Erreur lors de la sauvegarde de l'avant-dernier point."))
            if not started:
                print("Aucun avant-dernier point disponible.")
            else:
                print("Encodage de l'avant-dernier point en cours…")

    recorder.close()
    src.release()
    controls.close()
    cv2.destroyAllWindows()


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
