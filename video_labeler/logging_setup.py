"""Rotating file logging so key actions and crashes can be traced later.

The GUI keeps an in-app log panel, but enterprise deployments also need a
persistent record that survives the process. All status messages and uncaught
exceptions go through :func:`app_logger` into ``APPDATA``.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

LOGGER_NAME = "video_labeler"
_CONFIGURED = False


def log_directory() -> Path:
    root = Path(os.environ.get("APPDATA", str(Path.home())))
    return root / "VideoSegmentLabeler" / "logs"


def setup_logging() -> Path:
    """Attach one rotating file handler; safe to call repeatedly."""
    global _CONFIGURED
    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    if not _CONFIGURED:
        handler = logging.handlers.RotatingFileHandler(
            directory / "app.log",
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _CONFIGURED = True
    return directory


def app_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
