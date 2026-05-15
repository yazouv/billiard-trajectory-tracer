import cv2
import numpy as np


def select_table_rect(frame_bgr, window="Selectionne la zone de jeu (Entree pour valider)"):
    """Demande à l'utilisateur de tracer un rectangle sur la 1re frame.
    Retourne (x, y, w, h) en coordonnées image (pas écran)."""
    h_img, w_img = frame_bgr.shape[:2]
    # Fenêtre redimensionnable mais affichée à taille native pour éviter les
    # décalages entre coordonnées écran et coordonnées image.
    cv2.namedWindow(window, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    # Cap à 90% de l'écran pour éviter de déborder
    try:
        screen_w = 1920  # défaut prudent
        screen_h = 1080
        max_w, max_h = int(screen_w * 0.9), int(screen_h * 0.9)
        scale = min(max_w / w_img, max_h / h_img, 1.0)
        cv2.resizeWindow(window, int(w_img * scale), int(h_img * scale))
    except Exception:
        cv2.resizeWindow(window, w_img, h_img)

    x, y, w, h = cv2.selectROI(window, frame_bgr, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(window)
    if w == 0 or h == 0:
        raise RuntimeError("Aucune zone sélectionnée")
    return int(x), int(y), int(w), int(h)


def rect_to_mask(shape_hw, rect):
    """rect = (x, y, w, h) -> masque uint8 0/255 de la taille de la frame."""
    h_img, w_img = shape_hw[:2]
    mask = np.zeros((h_img, w_img), dtype=np.uint8)
    x, y, w, h = rect
    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, thickness=cv2.FILLED)
    return mask
