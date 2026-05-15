import cv2
import numpy as np


def cyndilib_available():
    """Renvoie True si cyndilib est importable."""
    try:
        import cyndilib  # noqa: F401
        return True
    except ImportError:
        return False


class VideoSource:
    """Lecture d'un fichier vidéo via cv2.VideoCapture (seekable)."""

    seekable = True

    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la source: {path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def frame_count(self):
        return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

    @property
    def position(self):
        return int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))

    def seek(self, frame_idx):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(frame_idx)))

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()


class NdiSource:
    """Réception d'un flux NDI via cyndilib. Même interface que VideoSource."""

    seekable = False
    frame_count = 0
    position = 0

    def seek(self, frame_idx):
        pass  # flux live : pas de seek possible

    def __init__(self, source_name, fps_hint=60.0):
        from cyndilib.finder import Finder
        from cyndilib.receiver import Receiver
        from cyndilib.video_frame import VideoFrameSync
        from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat

        # Découverte (un peu plus longue) puis résolution du nom
        self._finder = Finder()
        self._finder.open()
        self._finder.wait_for_sources(timeout=5.0)
        try:
            self._finder.update_sources()
        except Exception:
            pass

        source = self._finder.get_source(source_name)
        if source is None:
            available = list(self._finder.get_source_names())
            self._finder.close()
            raise RuntimeError(
                f"Source NDI introuvable: '{source_name}'. "
                f"Sources visibles: {available or '(aucune)'}"
            )

        # BGRX_BGRA : on récupère du 4-octets/pixel, facile à convertir en BGR.
        self._receiver = Receiver(
            color_format=RecvColorFormat.BGRX_BGRA,
            bandwidth=RecvBandwidth.highest,
        )
        self._video_frame = VideoFrameSync()
        self._receiver.frame_sync.set_video_frame(self._video_frame)
        self._receiver.set_source(source)

        self.source_name = source_name
        self.fps = fps_hint
        self.width = 0
        self.height = 0

    def _dims(self):
        for w_attr, h_attr in (("xres", "yres"), ("width", "height")):
            w = getattr(self._video_frame, w_attr, None)
            h = getattr(self._video_frame, h_attr, None)
            if w and h:
                return int(w), int(h)
        return 0, 0

    def read(self):
        self._receiver.frame_sync.capture_video()
        try:
            arr = self._video_frame.get_array()
        except Exception:
            return False, None
        if arr is None or arr.size == 0:
            return False, None

        w, h = self._dims()
        # Reshape si on a un buffer plat (BGRA = 4 octets / pixel)
        if arr.ndim == 1:
            if not (w and h):
                return False, None
            try:
                arr = np.asarray(arr, dtype=np.uint8).reshape(h, w, 4)
            except ValueError:
                return False, None

        if arr.ndim == 3 and arr.shape[2] == 4:
            frame = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
        else:
            frame = np.asarray(arr)
        self.height, self.width = frame.shape[:2]
        return True, frame

    def release(self):
        try:
            self._receiver.set_source(None)
        except Exception:
            pass
        try:
            self._finder.close()
        except Exception:
            pass


def list_ndi_sources(timeout=8.0, poll_interval=0.3):
    """Découverte des sources NDI : callback + polling, attend jusqu'au timeout."""
    import threading
    import time

    from cyndilib.finder import Finder

    finder = Finder()
    event = threading.Event()
    try:
        finder.set_change_callback(event.set)
    except Exception:
        pass
    finder.open()
    try:
        # Première chance : notification immédiate
        event.wait(timeout=timeout)
        names = []
        deadline = time.monotonic() + min(2.0, timeout)
        while True:
            try:
                finder.update_sources()
            except Exception:
                pass
            try:
                names = list(finder.get_source_names())
            except Exception:
                names = []
            if names or time.monotonic() >= deadline:
                break
            time.sleep(poll_interval)
        return names
    finally:
        try:
            finder.close()
        except Exception:
            pass


