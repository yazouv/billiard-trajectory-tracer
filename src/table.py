import cv2
import numpy as np


WINDOW_TITLE = "Ajuste les 4 coins (Entree=valider, R=reset, Echap=annuler)"

_HANDLE_RADIUS = 12
_PICK_RADIUS = 25


def _default_quad(w_img, h_img):
    """Quad rectangulaire par défaut, marges 8% du bord."""
    mx = int(w_img * 0.08)
    my = int(h_img * 0.08)
    return [
        [mx, my],                    # TL
        [w_img - mx, my],            # TR
        [w_img - mx, h_img - my],    # BR
        [mx, h_img - my],            # BL
    ]


def _draw_overlay(base, quad, active_idx):
    overlay = base.copy()
    pts = np.array(quad, dtype=np.int32)
    # Remplissage translucide
    fill = base.copy()
    cv2.fillPoly(fill, [pts], (0, 200, 0))
    cv2.addWeighted(fill, 0.18, overlay, 0.82, 0, overlay)
    # Contour
    cv2.polylines(overlay, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
    # Poignées
    for i, (x, y) in enumerate(quad):
        color = (0, 255, 255) if i == active_idx else (0, 255, 0)
        cv2.circle(overlay, (x, y), _HANDLE_RADIUS, color, 2)
        cv2.circle(overlay, (x, y), 3, color, -1)
        cv2.putText(overlay, str(i + 1), (x + 14, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
    # Aide en haut
    cv2.putText(overlay, "Glisse les 4 coins  |  Entree=valider  R=reset  Echap=annuler",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return overlay


def select_table_quad(frame_bgr, window=WINDOW_TITLE, initial_quad=None):
    """Demande à l'utilisateur d'ajuster 4 coins sur la 1re frame.
    Retourne une liste de 4 points [[x,y],...] dans l'ordre TL,TR,BR,BL."""
    h_img, w_img = frame_bgr.shape[:2]
    quad = [list(p) for p in (initial_quad or _default_quad(w_img, h_img))]

    state = {"dragging": None, "quad": quad}

    def on_mouse(event, x, y, flags, _):
        if event == cv2.EVENT_LBUTTONDOWN:
            best, best_d = None, _PICK_RADIUS ** 2
            for i, (px, py) in enumerate(state["quad"]):
                d = (px - x) ** 2 + (py - y) ** 2
                if d <= best_d:
                    best, best_d = i, d
            state["dragging"] = best
        elif event == cv2.EVENT_MOUSEMOVE and state["dragging"] is not None:
            xi = max(0, min(w_img - 1, x))
            yi = max(0, min(h_img - 1, y))
            state["quad"][state["dragging"]] = [xi, yi]
        elif event == cv2.EVENT_LBUTTONUP:
            state["dragging"] = None

    cv2.namedWindow(window, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    try:
        screen_w, screen_h = 1920, 1080
        max_w, max_h = int(screen_w * 0.9), int(screen_h * 0.9)
        scale = min(max_w / w_img, max_h / h_img, 1.0)
        cv2.resizeWindow(window, int(w_img * scale), int(h_img * scale))
    except Exception:
        cv2.resizeWindow(window, w_img, h_img)
    cv2.setMouseCallback(window, on_mouse)

    try:
        while True:
            img = _draw_overlay(frame_bgr, state["quad"], state["dragging"])
            cv2.imshow(window, img)
            key = cv2.waitKey(20) & 0xFF
            if key in (13, 10):  # Enter
                break
            if key == 27:  # Esc
                raise RuntimeError("Sélection annulée")
            if key in (ord('r'), ord('R')):
                state["quad"] = _default_quad(w_img, h_img)
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                raise RuntimeError("Fenêtre fermée")
    finally:
        cv2.destroyWindow(window)

    return [[int(x), int(y)] for x, y in state["quad"]]


def quad_to_mask(shape_hw, quad):
    """quad = liste de 4 [x,y] -> masque uint8 0/255 de la taille de la frame."""
    h_img, w_img = shape_hw[:2]
    mask = np.zeros((h_img, w_img), dtype=np.uint8)
    pts = np.array(quad, dtype=np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask


def rect_to_quad(rect):
    """Convertit un ancien (x,y,w,h) en quad TL,TR,BR,BL."""
    x, y, w, h = rect
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


# --- Compat: anciennes API conservées pour ne pas casser d'imports externes ---

def select_table_rect(*args, **kwargs):
    raise NotImplementedError("select_table_rect a été remplacé par select_table_quad")


def rect_to_mask(shape_hw, rect):
    return quad_to_mask(shape_hw, rect_to_quad(rect))
