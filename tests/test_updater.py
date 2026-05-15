from updater import _version_tuple


def test_version_tuple_basic():
    assert _version_tuple("0.1.0") == (0, 1, 0)
    assert _version_tuple("v0.1.0") == (0, 1, 0)
    assert _version_tuple("v1.2.3") == (1, 2, 3)


def test_version_tuple_comparison_more_recent():
    assert _version_tuple("0.1.1") > _version_tuple("0.1.0")
    assert _version_tuple("0.2.0") > _version_tuple("0.1.9")
    assert _version_tuple("1.0.0") > _version_tuple("0.99.99")


def test_version_tuple_handles_garbage():
    # Une partie non numérique stoppe le parsing mais ne crashe pas
    assert _version_tuple("0.1.0-rc1") == (0, 1)  # "0-rc1" stoppe le parse
    assert _version_tuple("abc") == ()
