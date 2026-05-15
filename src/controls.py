import cv2
import numpy as np

WINDOW = "Reglages"


def _noop(_):
    pass


class Controls:
    """Petite fenêtre OpenCV avec trackbars + rappel des touches clavier."""

    def __init__(self, initial):
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 420, 240)
        cv2.createTrackbar("Lissage", WINDOW, int(initial.get("smooth_window", 3)), 31, _noop)
        cv2.createTrackbar("Contours billes", WINDOW,
                           1 if initial.get("show_balls", False) else 0, 1, _noop)
        self._help_img = self._build_help_image()
        cv2.imshow(WINDOW, self._help_img)

    @staticmethod
    def _build_help_image():
        img = np.full((180, 420, 3), 32, dtype=np.uint8)
        lines = [
            "Touches dans la fenetre video :",
            "  ESPACE   pause / lecture",
            "  R        redefinir la zone de jeu",
            "  C        effacer les traces",
            "  S        sauvegarder la config",
            "  Q / ESC  quitter",
        ]
        y = 24
        for line in lines:
            cv2.putText(img, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (220, 220, 220), 1, cv2.LINE_AA)
            y += 22
        return img

    def refresh(self):
        cv2.imshow(WINDOW, self._help_img)

    def smooth_window(self):
        return max(1, cv2.getTrackbarPos("Lissage", WINDOW))

    def show_balls(self):
        return cv2.getTrackbarPos("Contours billes", WINDOW) > 0

    def snapshot(self):
        return {
            "smooth_window": self.smooth_window(),
            "show_balls": self.show_balls(),
        }
