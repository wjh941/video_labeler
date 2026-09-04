from video_labeler.media_locator import find_media_candidate, relocate_media_paths

def test_find_unique_media_candidate_case_insensitive(tmp_path):
    candidate = tmp_path / "nested" / "Camera.MP4"
    candidate.parent.mkdir()
    candidate.write_bytes(b"x")
    assert find_media_candidate(tmp_path / "old" / "camera.mp4", tmp_path) == candidate.resolve()

def test_relocation_does_not_guess_ambiguous_names(tmp_path):
    first = tmp_path / "a" / "clip.mp4"
    second = tmp_path / "b" / "clip.mp4"
    first.parent.mkdir(); second.parent.mkdir()
    first.write_bytes(b"a"); second.write_bytes(b"b")
    missing = tmp_path / "old" / "clip.mp4"
    assert relocate_media_paths([missing], tmp_path) == {}
