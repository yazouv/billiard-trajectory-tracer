import cv2
import numpy as np

# Plages HSV par couleur de bille. À ajuster après le premier run sur la vidéo.
# OpenCV: H in [0,179], S in [0,255], V in [0,255]
HSV_RANGES = {
    "white":  [(np.array([0,   0, 200]), np.array([179,  40, 255]))],
    "yellow": [(np.array([18, 100, 120]), np.array([35, 255, 255]))],
    # Le rouge enjambe H=0, donc deux plages
    "red":    [(np.array([0,  120,  90]), np.array([10, 255, 255])),
               (np.array([165,120,  90]), np.array([179,255, 255]))],
}

DRAW_COLORS_BGR = {
    "white":  (255, 255, 255),
    "yellow": (0, 220, 255),
    "red":    (0, 0, 255),
}

# Contraintes géométriques d'une bille (à ajuster selon la résolution de la vidéo)
MIN_RADIUS = 6
MAX_RADIUS = 35
MIN_CIRCULARITY = 0.55  # 1.0 = cercle parfait ; bandes/objets allongés < 0.5


def _mask_for(hsv, ranges):
    mask = None
    for lo, hi in ranges:
        m = cv2.inRange(hsv, lo, hi)
        mask = m if mask is None else cv2.bitwise_or(mask, m)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return mask


def _best_ball_candidate(mask):
    """Cherche le meilleur contour ressemblant à une bille (taille + circularité)."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_score = 0.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < 20:
            continue
        perim = cv2.arcLength(c, True)
        if perim <= 0:
            continue
        circularity = 4 * np.pi * area / (perim * perim)
        if circularity < MIN_CIRCULARITY:
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        if r < MIN_RADIUS or r > MAX_RADIUS:
            continue
        # Score: combine circularité et "remplissage" du cercle englobant
        fill = area / (np.pi * r * r + 1e-6)
        score = circularity * fill
        if score > best_score:
            best_score = score
            best = (int(x), int(y), int(r))
    return best


def detect_balls(frame_bgr, roi_mask=None):
    """Retourne {color: (x, y, r)} pour les billes détectées.

    roi_mask : masque uint8 optionnel (0/255) restreignant la zone de recherche
    (typiquement le tapis de la table).
    """
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    result = {}
    for color, ranges in HSV_RANGES.items():
        mask = _mask_for(hsv, ranges)
        if roi_mask is not None:
            mask = cv2.bitwise_and(mask, roi_mask)
        det = _best_ball_candidate(mask)
        if det is not None:
            result[color] = det
    return result
