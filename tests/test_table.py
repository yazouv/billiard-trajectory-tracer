import numpy as np

from table import rect_to_mask


def test_rect_to_mask_dims():
    mask = rect_to_mask((480, 640, 3), (10, 20, 100, 50))
    assert mask.shape == (480, 640)
    assert mask.dtype == np.uint8


def test_rect_to_mask_fills_only_rect():
    mask = rect_to_mask((100, 100), (10, 10, 20, 30))
    # Pixels dedans
    assert mask[20, 20] == 255
    # Pixels dehors
    assert mask[0, 0] == 0
    assert mask[90, 90] == 0
    # cv2.rectangle FILLED inclut les deux coins -> dimensions +1 chacun
    assert (mask == 255).sum() == (20 + 1) * (30 + 1)
