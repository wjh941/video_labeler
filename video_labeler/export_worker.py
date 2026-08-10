import csv
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PySide6.QtCore import QThread, Signal

from .ffmpeg_service import (
    ExportControl,
    ExportRequest,
    ExportResult,
    format_seconds,
    run_clip_export,
)
from .models import ClipRecord


@dataclass(frozen=True)
class ExportSummary:
    success: int
    skipped: int
    failed: int
    canceled: int

    @classmethod
    def from_results(cls, results: Iterable[ExportResult]) -> "ExportSummary":
        statuses = [result.status for result in results]
        return cls(
            success=statuses.count("ok"),
            skipped=statuses.count("skip"),
            failed=statuses.count("fail"),
            canceled=statuses.count("canceled"),
        )


def write_failed_report(
    path: Path, failures: Sequence[tuple[int, ClipRecord, ExportResult]]
) -> None:
    fieldnames = ("row_index", "source", "start", "end", "output", "error")
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row_index, record, result in failures:
            writer.writerow(
                {
                    "row_index": row_index,
                    "source": record.source,
                    "start": format_seconds(record.start_seconds),
                    "end": format_seconds(record.end_seconds),
                    "output": record.output,
                    "error": result.error,
                }
            )


def validate_batch_source(
    records: Sequence[ClipRecord], input_path: Path
) -> None:
    expected = input_path.name.casefold()
    mismatches = sorted(
        {
            record.source
            for record in records
            if Path(record.source).name.casefold() != expected
        }
    )
    if mismatches:
        raise ValueError(
            "All clips must use the selected source video; mismatched rows: "
            + ", ".join(mismatches)
        )


class ExportWorker(QThread):
    clip_finished = Signal(int, object)
    progress = Signal(int, int)
    export_completed = Signal(object)

    def __init__(
        self,
        records: Sequence[ClipRecord],
        input_path: Path,
        output_dir: Path,
        ffmpeg: str,
        ffprobe: str,
        mode: str,
        overwrite: bool,
        workers: int = 0,
    ) -> None:
        super().__init__()
        self._records = list(records)
        self._input_path = input_path
        self._output_dir = output_dir
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._mode = mode
        self._overwrite = overwrite
        self._workers = workers or 2
        self._control = ExportControl()

    def cancel(self) -> None:
        self._control.cancel()

    def run(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self._records)
        results: list[ExportResult | None] = [None] * total
        completed = 0
        next_index = 0
        futures = {}

        def submit_available(executor: ThreadPoolExecutor) -> None:
            nonlocal next_index
            while (
                not self._control.is_canceled()
                and next_index < total
                and len(futures) < self._workers
            ):
                record = self._records[next_index]
                request = ExportRequest(
                    ffmpeg=self._ffmpeg,
                    ffprobe=self._ffprobe,
                    input_path=self._input_path,
                    output_path=self._output_dir / record.output,
                    start=format_seconds(record.start_seconds),
                    end=format_seconds(record.end_seconds),
                    mode=self._mode,
                    overwrite=self._overwrite,
                )
                futures[executor.submit(run_clip_export, request, self._control)] = (
                    next_index
                )
                next_index += 1

        with ThreadPoolExecutor(max_workers=self._workers) as executor:
            submit_available(executor)
            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    index = futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as error:
                        result = ExportResult(
                            status="fail",
                            output=self._records[index].output,
                            error=str(error),
                        )
                    results[index] = result
                    record = self._records[index]
                    record.status = result.status
                    record.error = result.error
                    completed += 1
                    self.clip_finished.emit(index, result)
                    self.progress.emit(completed, total)
                submit_available(executor)

        while next_index < total:
            result = ExportResult(
                status="canceled",
                output=self._records[next_index].output,
            )
            results[next_index] = result
            self._records[next_index].status = result.status
            self.clip_finished.emit(next_index, result)
            completed += 1
            self.progress.emit(completed, total)
            next_index += 1

        completed_results = [result for result in results if result is not None]
        failures = [
            (index + 1, self._records[index], result)
            for index, result in enumerate(results)
            if result is not None and result.status == "fail"
        ]
        write_failed_report(self._output_dir / "failed_clips.csv", failures)
        self.export_completed.emit(ExportSummary.from_results(completed_results))
