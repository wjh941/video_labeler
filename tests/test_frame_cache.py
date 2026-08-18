from video_labeler.frame_cache import FrameCache


def test_frame_cache_discards_least_recently_used_frames_over_byte_limit():
    cache = FrameCache(max_bytes=5)

    cache.put("first", b"one", size_bytes=3)
    cache.put("second", b"two", size_bytes=3)

    assert cache.get("first") is None
    assert cache.get("second") == b"two"
    assert cache.size_bytes == 3


def test_frame_cache_does_not_keep_a_frame_larger_than_its_limit():
    cache = FrameCache(max_bytes=4)

    cache.put("large", b"large", size_bytes=5)

    assert len(cache) == 0
    assert cache.size_bytes == 0
