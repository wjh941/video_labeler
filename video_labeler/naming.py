from dataclasses import dataclass
import re

from .models import (
    ProjectMetadata,
)


_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_VIEW_TOKEN_PATTERN = re.compile(r"^[a-z0-9]+$")
_LABEL_TOKEN_PATTERN = re.compile(r"^[a-z0-9_]+$")
_DATE_PATTERN = re.compile(r"^\d{8}$")
_INVALID_WINDOWS_FILENAME_CHARACTERS = set('<>:"/\\|?*')
_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


@dataclass(frozen=True)
class ParsedFilename:
    metadata: ProjectMetadata
    behaviors: tuple[str, ...]
    polarity: str
    lighting: str
    sequence: int


def normalize_view_token(value: str) -> str:
    normalized = value.strip().lower()
    if not _VIEW_TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError("view must use lowercase English letters and digits")
    return normalized


def normalize_label_token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not _LABEL_TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"{field_name} must use lowercase English letters, digits, or underscores"
        )
    return normalized


def _validate_metadata(metadata: ProjectMetadata) -> ProjectMetadata:
    if not _DATE_PATTERN.fullmatch(metadata.date):
        raise ValueError("date must use YYYYMMDD format")
    if not _TOKEN_PATTERN.fullmatch(metadata.camera):
        raise ValueError("camera must use English letters, digits, or underscores")
    return ProjectMetadata(
        date=metadata.date,
        camera=metadata.camera,
        view=normalize_view_token(metadata.view),
    )


def _validate_labels(
    behaviors: tuple[str, ...], polarity: str, lighting: str, sequence: int
) -> tuple[str, str]:
    if not behaviors:
        raise ValueError("at least one behavior label is required")
    for behavior in behaviors:
        if not isinstance(behavior, str):
            raise ValueError("behavior label must be a string")
        normalize_label_token(behavior, "behavior label")
    if sequence < 1:
        raise ValueError("sequence must be at least 1")
    return (
        normalize_label_token(polarity, "polarity"),
        normalize_label_token(lighting, "lighting"),
    )


def build_filename(
    metadata: ProjectMetadata,
    behaviors: tuple[str, ...],
    polarity: str,
    lighting: str,
    sequence: int,
) -> str:
    metadata = _validate_metadata(metadata)
    polarity, lighting = _validate_labels(behaviors, polarity, lighting, sequence)
    behavior_text = "+".join(behaviors)
    return (
        f"{metadata.date}-{metadata.camera}_{metadata.view}-{behavior_text}-"
        f"{polarity}-{lighting}-{sequence:03d}.mp4"
    )


def validate_output_filename(filename: str) -> None:
    if not filename or filename != filename.strip():
        raise ValueError("output filename cannot be empty or padded with spaces")
    if not filename.lower().endswith(".mp4"):
        raise ValueError("output filename must end with .mp4")
    if filename.endswith((".", " ")):
        raise ValueError("output filename cannot end with a dot or space")
    if any(
        character in _INVALID_WINDOWS_FILENAME_CHARACTERS or ord(character) < 32
        for character in filename
    ):
        raise ValueError("output filename contains invalid Windows characters")

    stem = filename[:-4].upper()
    if stem in _RESERVED_WINDOWS_NAMES:
        raise ValueError("output filename uses a reserved Windows device name")


def parse_filename(filename: str) -> ParsedFilename | None:
    if not filename.lower().endswith(".mp4"):
        return None

    parts = filename[:-4].split("-")
    if len(parts) != 6:
        return None

    date, camera_and_view, behavior_text, polarity, lighting, sequence_text = parts
    camera, separator, view = camera_and_view.rpartition("_")
    if not separator:
        return None

    behaviors = tuple(behavior_text.split("+"))
    try:
        sequence = int(sequence_text)
        metadata = _validate_metadata(
            ProjectMetadata(date=date, camera=camera, view=view)
        )
        polarity, lighting = _validate_labels(
            behaviors,
            polarity,
            lighting,
            sequence,
        )
    except ValueError:
        return None

    return ParsedFilename(
        metadata=metadata,
        behaviors=behaviors,
        polarity=polarity,
        lighting=lighting,
        sequence=sequence,
    )


def next_sequence(sequences: list[int]) -> int:
    return max((sequence for sequence in sequences if sequence > 0), default=0) + 1
