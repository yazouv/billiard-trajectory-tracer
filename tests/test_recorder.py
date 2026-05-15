import numpy as np

from recorder import PointRecorder


def _frame(w=64, h=48, color=(0, 128, 0)):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = color
    return img


def test_write_buffers_in_memory(tmp_path):
    rec = PointRecorder(tmp_path, fps=30, max_seconds=2)
    for _ in range(10):
        rec.write(_frame())
    assert len(rec._current) == 10
    # Aucun fichier créé à ce stade
    assert list(tmp_path.iterdir()) == []


def test_rotate_promotes_current_to_last_and_prev(tmp_path):
    rec = PointRecorder(tmp_path, fps=30, max_seconds=2)
    for _ in range(20):
        rec.write(_frame())
    rec.rotate()
    assert rec._last is not None
    assert rec._prev is None
    assert len(rec._current) == 0

    for _ in range(20):
        rec.write(_frame(color=(255, 255, 255)))
    rec.rotate()
    assert rec._last is not None
    assert rec._prev is not None


def test_rotate_drops_tiny_points(tmp_path):
    rec = PointRecorder(tmp_path, fps=30, max_seconds=2)
    # Moins que fps * 0.4 = 12 frames -> rejeté
    for _ in range(5):
        rec.write(_frame())
    rec.rotate()
    assert rec._last is None
    assert len(rec._current) == 0


def test_save_last_writes_mp4(tmp_path):
    rec = PointRecorder(tmp_path, fps=30, max_seconds=2)
    for _ in range(20):
        rec.write(_frame())
    rec.rotate()

    out = rec._encode(rec._last, "last")  # synchrone pour le test
    assert out is not None
    assert out.exists()
    assert out.suffix == ".mp4"
    assert out.stat().st_size > 0
