from dataclasses import dataclass, replace
from typing import Sequence

from .models import ClipRecord


def _snapshot(records: Sequence[ClipRecord]) -> tuple[ClipRecord, ...]:
    """Copy records so callers cannot mutate saved history entries."""
    return tuple(replace(record) for record in records)


@dataclass(frozen=True)
class SegmentHistoryEntry:
    before: tuple[ClipRecord, ...]
    after: tuple[ClipRecord, ...]


class SegmentHistory:
    """Cursor-based undo/redo history for one video's segment list."""

    def __init__(self) -> None:
        self._entries: list[SegmentHistoryEntry] = []
        self._cursor = 0

    def push(
        self,
        before: Sequence[ClipRecord],
        after: Sequence[ClipRecord],
    ) -> None:
        if tuple(before) == tuple(after):
            return

        del self._entries[self._cursor :]
        self._entries.append(
            SegmentHistoryEntry(_snapshot(before), _snapshot(after))
        )
        self._cursor = len(self._entries)

    def can_undo(self) -> bool:
        return self._cursor > 0

    def can_redo(self) -> bool:
        return self._cursor < len(self._entries)

    def undo(self, current: Sequence[ClipRecord]) -> list[ClipRecord]:
        if not self.can_undo():
            return [replace(record) for record in current]

        self._cursor -= 1
        return [replace(record) for record in self._entries[self._cursor].before]

    def redo(self, current: Sequence[ClipRecord]) -> list[ClipRecord]:
        if not self.can_redo():
            return [replace(record) for record in current]

        entry = self._entries[self._cursor]
        self._cursor += 1
        return [replace(record) for record in entry.after]
