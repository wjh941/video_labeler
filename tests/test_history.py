from video_labeler.models import ClipRecord


def _record(sequence: int, *, status: str = "queued") -> ClipRecord:
    return ClipRecord(
        source="camera.mp4",
        start_seconds=float(sequence),
        end_seconds=float(sequence + 1),
        output=f"clip-{sequence}.mp4",
        behaviors=("dog_out",),
        polarity="pos",
        lighting="daytime",
        sequence=sequence,
        status=status,
    )


def test_undo_and_redo_restore_independent_segment_snapshots():
    from video_labeler.history import SegmentHistory

    history = SegmentHistory()
    before = [_record(1)]
    after = [_record(1), _record(2)]

    history.push(before, after)

    assert history.can_undo()
    restored_before = history.undo(after)
    assert restored_before == before
    assert restored_before is not before
    assert restored_before[0] is not before[0]
    assert history.can_redo()

    restored_after = history.redo(before)
    assert restored_after == after
    assert restored_after is not after
    assert restored_after[1] is not after[1]


def test_new_change_after_undo_discards_redo_branch():
    from video_labeler.history import SegmentHistory

    history = SegmentHistory()
    original = [_record(1)]
    added = [_record(1), _record(2)]
    replacement = [_record(3)]
    history.push(original, added)
    assert history.undo(added) == original
    history.push(original, replacement)

    assert not history.can_redo()
    assert history.undo(replacement) == original


def test_history_snapshots_do_not_change_when_input_records_are_mutated():
    from video_labeler.history import SegmentHistory

    current = [_record(1)]
    changed = [_record(1, status="completed")]
    history = SegmentHistory()
    history.push(current, changed)

    current[0].status = "failed"
    changed[0].status = "queued"

    assert history.undo(changed)[0].status == "queued"
    assert history.redo(current)[0].status == "completed"


def test_empty_undo_and_redo_return_independent_copies():
    from video_labeler.history import SegmentHistory

    history = SegmentHistory()
    current = [_record(1)]

    undone = history.undo(current)
    redone = history.redo(current)

    assert undone == current
    assert redone == current
    assert undone is not current
    assert redone is not current
    assert undone[0] is not current[0]
    assert redone[0] is not current[0]


def test_identical_change_does_not_create_history_entry():
    from video_labeler.history import SegmentHistory

    history = SegmentHistory()
    records = [_record(1)]

    history.push(records, list(records))

    assert not history.can_undo()
    assert not history.can_redo()
