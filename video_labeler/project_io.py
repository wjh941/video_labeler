import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .models import ClipRecord, ProjectMetadata
from .naming import validate_labels


PROJECT_MANIFEST_VERSION = 1


@dataclass(eq=True)
class ProjectState:
    source_path: Path | None
    output_dir: Path | None
    metadata: ProjectMetadata
    records: list[ClipRecord]


def _record_to_payload(record: ClipRecord) -> dict[str, Any]:
    return {
        "source": record.source,
        "start": record.start_seconds,
        "end": record.end_seconds,
        "output": record.output,
        "behaviors": list(record.behaviors),
        "polarity": record.polarity,
        "lighting": record.lighting,
        "sequence": record.sequence,
        "status": record.status,
        "error": record.error,
    }


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _record_from_payload(value: Any, index: int) -> ClipRecord:
    prefix = f"record {index}"
    try:
        payload = _require_mapping(value, prefix)
        source = payload["source"]
        output = payload["output"]
        start = payload["start"]
        end = payload["end"]
        behaviors = payload["behaviors"]
        polarity = payload["polarity"]
        lighting = payload["lighting"]
        sequence = payload["sequence"]
    except KeyError as error:
        raise ValueError(f"{prefix} is missing {error.args[0]}") from error

    if not isinstance(source, str) or not isinstance(output, str):
        raise ValueError(f"{prefix} source and output must be strings")
    if not _is_number(start) or not _is_number(end):
        raise ValueError(f"{prefix} start and end must be numeric")
    if end <= start:
        raise ValueError(f"{prefix} ends before it starts")
    if not isinstance(behaviors, list):
        raise ValueError(f"{prefix} behaviors must be a list")
    if not all(isinstance(behavior, str) for behavior in behaviors):
        raise ValueError(f"{prefix} behaviors must contain strings")
    if not isinstance(polarity, str) or not isinstance(lighting, str):
        raise ValueError(f"{prefix} label values must be strings")
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ValueError(f"{prefix} sequence must be an integer")

    labels = (tuple(behaviors), polarity, lighting, sequence)
    if any(labels):
        if not all(labels):
            raise ValueError(f"{prefix} has incomplete labels")
        try:
            validate_labels(*labels)
        except ValueError as error:
            raise ValueError(f"{prefix} has invalid labels: {error}") from error

    status = payload.get("status", "queued")
    error = payload.get("error", "")
    if not isinstance(status, str) or not isinstance(error, str):
        raise ValueError(f"{prefix} status and error must be strings")

    return ClipRecord(
        source=source,
        start_seconds=start,
        end_seconds=end,
        output=output,
        behaviors=tuple(behaviors),
        polarity=polarity,
        lighting=lighting,
        sequence=sequence,
        status=status,
        error=error,
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def write_project_manifest(path: Path, state: ProjectState) -> None:
    payload = {
        "version": PROJECT_MANIFEST_VERSION,
        "source_path": str(state.source_path.resolve()) if state.source_path else None,
        "output_dir": str(state.output_dir) if state.output_dir else None,
        "metadata": {
            "date": state.metadata.date,
            "camera": state.metadata.camera,
            "view": state.metadata.view,
        },
        "records": [_record_to_payload(record) for record in state.records],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_project_manifest(path: Path) -> ProjectState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"unable to read project manifest {path}: {error}") from error
    payload = _require_mapping(payload, "manifest")
    if payload.get("version") != PROJECT_MANIFEST_VERSION:
        raise ValueError(f"unsupported manifest version: {payload.get('version')}")

    metadata_payload = _require_mapping(payload.get("metadata"), "metadata")
    try:
        metadata = ProjectMetadata(
            date=metadata_payload["date"],
            camera=metadata_payload["camera"],
            view=metadata_payload["view"],
        )
    except KeyError as error:
        raise ValueError(f"metadata is missing {error.args[0]}") from error
    if not all(isinstance(value, str) for value in (metadata.date, metadata.camera, metadata.view)):
        raise ValueError("metadata values must be strings")

    records_payload = payload.get("records")
    if not isinstance(records_payload, list):
        raise ValueError("records must be a list")

    return ProjectState(
        source_path=_path_or_none(payload.get("source_path"), "source_path", absolute=True),
        output_dir=_path_or_none(payload.get("output_dir"), "output_dir"),
        metadata=metadata,
        records=[_record_from_payload(record, index) for index, record in enumerate(records_payload, start=1)],
    )


def _path_or_none(value: Any, name: str, *, absolute: bool = False) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string or null")
    result = Path(value)
    return result.resolve() if absolute else result
