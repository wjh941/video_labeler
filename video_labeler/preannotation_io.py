"""Validated import for reviewable pre-annotation JSON files."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PreAnnotation:
    start_seconds: float
    end_seconds: float
    behaviors: tuple[str, ...]
    polarity: str = ""
    lighting: str = ""


def read_preannotation_json(path: Path) -> list[PreAnnotation]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("pre-annotation JSON is invalid") from error
    segments = document.get("segments") if isinstance(document, dict) else document
    if not isinstance(segments, list):
        raise ValueError("pre-annotation segments must be a list")
    return [_annotation_from_dict(segment) for segment in segments]


def _annotation_from_dict(document: Any) -> PreAnnotation:
    if not isinstance(document, dict):
        raise ValueError("pre-annotation segment must be an object")
    start = document.get("start_seconds", document.get("start"))
    end = document.get("end_seconds", document.get("end"))
    behaviors = document.get("behaviors", document.get("labels"))
    if not _is_time(start) or not _is_time(end):
        raise ValueError("pre-annotation times must be finite non-negative numbers")
    if float(end) <= float(start):
        raise ValueError("pre-annotation end_seconds must be greater than start_seconds")
    if not isinstance(behaviors, list) or not behaviors or not all(
        isinstance(tag, str) and tag.strip() for tag in behaviors
    ):
        raise ValueError("pre-annotation behaviors must be a non-empty list of strings")
    polarity = document.get("polarity", "")
    lighting = document.get("lighting", "")
    if not isinstance(polarity, str) or not isinstance(lighting, str):
        raise ValueError("pre-annotation polarity and lighting must be strings")
    return PreAnnotation(
        start_seconds=float(start),
        end_seconds=float(end),
        behaviors=tuple(dict.fromkeys(tag.strip() for tag in behaviors)),
        polarity=polarity.strip(),
        lighting=lighting.strip(),
    )


def _is_time(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0
    )
