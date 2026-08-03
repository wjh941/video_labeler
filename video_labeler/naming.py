from dataclasses import dataclass
import re

from .models import (
    BEHAVIOR_LABELS,
    LIGHTING_VALUES,
    POLARITIES,
    VIEW_TYPES,
    ProjectMetadata,
)


_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
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


def _validate_metadata(metadata: ProjectMetadata) -> None:
    if not _DATE_PATTERN.fullmatch(metadata.date):
        raise ValueError("date must use YYYYMMDD format")
    if not _TOKEN_PATTERN.fullmatch(metadata.camera):
        raise ValueError("camera must use English letters, digits, or underscores")
    if metadata.view not in VIEW_TYPES:
        raise ValueError(f"view must be one of: {', '.join(VIEW_TYPES)}")


def _validate_labels(
    behaviors: tuple[str, ...], polarity: str, lighting: str, sequence: int
) -> None:
    if not behaviors:
        raise ValueError("at least one behavior label is required")
    if any(behavior not in BEHAVIOR_LABELS for behavior in behaviors):
        raise ValueError("unknown behavior label")
    if polarity not in POLARITIES:
        raise ValueError(f"polarity must be one of: {', '.join(POLARITIES)}")
    if lighting not in LIGHTING_VALUES:
        raise ValueError(f"lighting must be one of: {', '.join(LIGHTING_VALUES)}")
    if sequence < 1:
        raise ValueError("sequence must be at least 1")


def build_filename(
    metadata: ProjectMetadata,
    behaviors: tuple[str, ...],
    polarity: str,
    lighting: str,
    sequence: int,
) -> str:
    _validate_metadata(metadata)
    _validate_labels(behaviors, polarity, lighting, sequence)
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
    view = next(
        (
            option
            for option in VIEW_TYPES
            if camera_and_view.endswith(f"_{option}")
        ),
        None,
    )
    if view is None:
        return None

    camera = camera_and_view[: -(len(view) + 1)]
    behaviors = tuple(behavior_text.split("+"))
    try:
        sequence = int(sequence_text)
        metadata = ProjectMetadata(date=date, camera=camera, view=view)
        build_filename(metadata, behaviors, polarity, lighting, sequence)
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
