from tracker import Trajectories


def _detections(white=None, yellow=None, red=None):
    out = {}
    if white is not None:
        out["white"] = (*white, 10)
    if yellow is not None:
        out["yellow"] = (*yellow, 10)
    if red is not None:
        out["red"] = (*red, 10)
    return out


def test_update_adds_points():
    t = Trajectories(fps=30)
    t.update(_detections(white=(10, 10)))
    t.update(_detections(white=(20, 10)))
    assert t.points["white"] == [(10, 10), (20, 10)]


def test_clear_resets_points():
    t = Trajectories(fps=30)
    t.update(_detections(white=(10, 10)))
    t.clear()
    assert t.points["white"] == []


def test_snapshot_before_clear_keeps_last_and_prev():
    t = Trajectories(fps=30)
    # Premier point
    for _ in range(5):
        t.update(_detections(white=(10, 10), yellow=(20, 20), red=(30, 30)))
    t._snapshot_before_clear()
    t.clear()
    assert t.last_snapshot is not None
    assert "white" in t.last_snapshot
    # Deuxième point
    for _ in range(5):
        t.update(_detections(white=(100, 100), yellow=(200, 200)))
    t._snapshot_before_clear()
    t.clear()
    # prev = ancien last, last = nouveau snapshot
    assert "red" in t.prev_snapshot
    assert "red" not in t.last_snapshot
    assert "yellow" in t.last_snapshot
