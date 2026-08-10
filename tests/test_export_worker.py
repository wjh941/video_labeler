from dataclasses import replace

import pytest

try:
    from video_labeler import export_worker
    from video_labeler.export_worker import (
        ExportSummary,
        ExportWorker,
        validate_batch_source,
        write_failed_report,
    )
    from video_labeler.ffmpeg_service import ExportResult
    from video_labeler.models import ClipRecord
except ImportError:
    ClipRecord = None
    ExportResult = None
    ExportSummary = None
    ExportWorker = None
    export_worker = None
    validate_batch_source = None
    write_failed_report = None


def _require_export_api():
    assert ExportSummary is not None, "background export API is not implemented"


def _worker(tmp_path, records, workers=0):
    assert ExportWorker is not None, "background export worker API is not implemented"
    return ExportWorker(
        records=records,
        input_path=tmp_path / "cam02.mp4",
        output_dir=tmp_path / "out",
        ffmpeg="ffmpeg.exe",
        ffprobe="ffprobe.exe",
        mode="encode",
        overwrite=False,
        workers=workers,
    )


def _record() -> object:
    return ClipRecord(
        source="cam02.mp4",
        start_seconds=2.5,
        end_seconds=4.0,
        output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
        behaviors=("dog_out",),
        polarity="pos",
        lighting="daytime",
        sequence=1,
    )


def test_export_summary_counts_each_result_status():
    _require_export_api()

    summary = ExportSummary.from_results(
        [
            ExportResult("ok"),
            ExportResult("skip"),
            ExportResult("fail", error="bad input"),
            ExportResult("canceled"),
        ]
    )

    assert (summary.success, summary.skipped, summary.failed, summary.canceled) == (
        1,
        1,
        1,
        1,
    )


def test_write_failed_report_preserves_batch_debugging_fields(tmp_path):
    _require_export_api()
    report_path = tmp_path / "failed_clips.csv"

    write_failed_report(
        report_path,
        [(1, _record(), ExportResult("fail", error="source video not found"))],
    )

    assert report_path.read_text(encoding="utf-8-sig").splitlines() == [
        "row_index,source,start,end,output,error",
        (
            "1,cam02.mp4,00:00:02.500,00:00:04.000,"
            "20260729-cam02_panorama-dog_out-pos-daytime-001.mp4,"
            "source video not found"
        ),
    ]


def test_automatic_worker_count_is_two(tmp_path):
    worker = _worker(tmp_path, records=[])

    assert worker._workers == 2


def test_validate_batch_source_rejects_rows_from_another_video(tmp_path):
    assert validate_batch_source is not None, "batch source validation is not implemented"
    records = [_record(), replace(_record(), source="cam03.mp4")]

    with pytest.raises(ValueError, match="cam03.mp4"):
        validate_batch_source(records, tmp_path / "cam02.mp4")


def test_worker_passes_ffprobe_and_one_shared_control_to_each_export(
    tmp_path, monkeypatch
):
    worker = _worker(tmp_path, records=[_record(), _record()], workers=2)
    submitted = []

    def export(request, control):
        submitted.append((request, control))
        return ExportResult("ok", output=request.output_path.name)

    monkeypatch.setattr(export_worker, "run_clip_export", export)

    worker.run()

    assert [request.ffprobe for request, _ in submitted] == ["ffprobe.exe"] * 2
    assert {id(control) for _, control in submitted} == {id(worker._control)}


def test_worker_cancel_delegates_to_shared_control(tmp_path, monkeypatch):
    worker = _worker(tmp_path, records=[])
    canceled = []
    monkeypatch.setattr(worker._control, "cancel", lambda: canceled.append(True))

    worker.cancel()

    assert canceled == [True]


def test_worker_marks_unsubmitted_records_canceled_after_cancellation(
    tmp_path, monkeypatch
):
    records = [_record(), _record(), _record()]
    worker = _worker(tmp_path, records=records, workers=2)
    results = []

    def export(request, control):
        worker.cancel()
        return ExportResult("canceled", output=request.output_path.name)

    monkeypatch.setattr(export_worker, "run_clip_export", export)
    worker.clip_finished.connect(lambda _, result: results.append(result))

    worker.run()

    assert [result.status for result in results] == ["canceled"] * 3
    assert [record.status for record in records] == ["canceled"] * 3


def test_worker_rejects_mismatched_sources_without_submitting_exports(
    tmp_path, monkeypatch
):
    records = [_record(), replace(_record(), source="cam03.mp4")]
    worker = _worker(tmp_path, records=records)
    submitted = []
    results = []
    progress = []
    summaries = []

    monkeypatch.setattr(
        export_worker,
        "run_clip_export",
        lambda *args: (
            submitted.append(args),
            ExportResult("ok", output=args[0].output_path.name),
        )[1],
    )
    worker.clip_finished.connect(lambda _, result: results.append(result))
    worker.progress.connect(lambda completed, total: progress.append((completed, total)))
    worker.export_completed.connect(summaries.append)

    worker.run()

    assert submitted == []
    assert [result.status for result in results] == ["fail", "fail"]
    assert {result.error for result in results} == {
        "All clips must use the selected source video; mismatched rows: cam03.mp4"
    }
    assert progress == [(1, 2), (2, 2)]
    assert (summaries[0].success, summaries[0].failed) == (0, 2)
    assert "cam03.mp4" in (tmp_path / "out" / "failed_clips.csv").read_text(
        encoding="utf-8-sig"
    )


def test_worker_does_not_submit_after_cancellation_wins_submission_lock(
    tmp_path, monkeypatch
):
    worker = _worker(tmp_path, records=[_record()])
    submitted = []

    class CancellationWinningLock:
        def __enter__(self):
            worker._control.cancel()
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(
        export_worker,
        "run_clip_export",
        lambda *args: (
            submitted.append(args),
            ExportResult("ok", output=args[0].output_path.name),
        )[1],
    )
    worker._submission_lock = CancellationWinningLock()

    worker.run()

    assert submitted == []
