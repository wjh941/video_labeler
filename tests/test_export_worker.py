try:
    from video_labeler.export_worker import ExportSummary, write_failed_report
    from video_labeler.ffmpeg_service import ExportResult
    from video_labeler.models import ClipRecord
except ImportError:
    ClipRecord = None
    ExportResult = None
    ExportSummary = None
    write_failed_report = None


def _require_export_api():
    assert ExportSummary is not None, "background export API is not implemented"


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
