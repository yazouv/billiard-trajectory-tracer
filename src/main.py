import sys
from pathlib import Path

import cv2

import config
from capture import VideoSource
from controls import Controls
from detector import detect_balls, DRAW_COLORS_BGR
from table import select_table_rect, rect_to_mask
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


def main(video_path):
    cfg = config.load()

    src = VideoSource(video_path)
    print(f"Source: {video_path}  {src.width}x{src.height} @ {src.fps:.1f} fps")

    ok, first = src.read()
    if not ok:
        raise RuntimeError("Vidéo vide")

    # Zone de jeu : recharge si déjà sauvée, sinon on demande
    if cfg.get("table_rect"):
        table_rect = tuple(cfg["table_rect"])
        print(f"Zone chargée depuis config : {table_rect}")
    else:
        table_rect = select_table_rect(first)
        config.save({"table_rect": list(table_rect)})
        print(f"Zone sélectionnée : {table_rect}")
    table_mask = rect_to_mask(first.shape, table_rect)

    trails = Trajectories(fps=src.fps)
    controls = Controls(cfg)

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    paused = False
    frame = first
    detections = {}

    while True:
        if not paused:
            ok, frame = src.read()
            if not ok:
                break
            detections = detect_balls(frame, roi_mask=table_mask)
            trails.configure(smooth_window=controls.smooth_window())
            trails.update(detections)

        display = frame.copy()
        trails.draw(display, DRAW_COLORS_BGR)
        draw_table_outline(display, table_rect)
        if controls.show_balls():
            draw_balls(display, detections)

        cv2.imshow(WINDOW, display)
        controls.refresh()

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord(' '):
            paused = not paused
        elif key == ord('c'):
            trails.clear()
        elif key == ord('r'):
            new_rect = select_table_rect(frame)
            table_rect = new_rect
            table_mask = rect_to_mask(frame.shape, table_rect)
            trails.clear()
            config.save({"table_rect": list(table_rect)})
            print(f"Zone redéfinie : {table_rect}")
        elif key == ord('s'):
            config.save(controls.snapshot() | {"table_rect": list(table_rect)})
            print("Config sauvegardée.")

    src.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent / "datas" / "video.mp4"
    path = sys.argv[1] if len(sys.argv) > 1 else str(default)
    main(path)
