import cv2
import numpy as np


def select_table_rect(frame_bgr, window="Selectionne la zone de jeu (Entree pour valider)"):
    """Demande à l'utilisateur de tracer un rectangle sur la 1re frame.
    Retourne (x, y, w, h)."""
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
