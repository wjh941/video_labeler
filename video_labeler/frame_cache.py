from collections import OrderedDict
from collections.abc import Hashable
from typing import Any


class FrameCache:
    """A byte-bounded LRU cache for paused video frames."""

    def __init__(self, *, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self.max_bytes = max_bytes
        self.size_bytes = 0
        self._frames: OrderedDict[Hashable, tuple[Any, int]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._frames)

    def get(self, key: Hashable) -> Any | None:
        entry = self._frames.get(key)
        if entry is None:
            return None
        self._frames.move_to_end(key)
        return entry[0]

    def put(self, key: Hashable, frame: Any, *, size_bytes: int) -> None:
        if size_bytes < 1 or size_bytes > self.max_bytes:
            return
        previous = self._frames.pop(key, None)
        if previous is not None:
            self.size_bytes -= previous[1]
        while self._frames and self.size_bytes + size_bytes > self.max_bytes:
            _, (_, removed_size) = self._frames.popitem(last=False)
            self.size_bytes -= removed_size
        self._frames[key] = (frame, size_bytes)
        self.size_bytes += size_bytes

    def clear(self) -> None:
        self._frames.clear()
        self.size_bytes = 0
