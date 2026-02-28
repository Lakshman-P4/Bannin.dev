"""Bannin logging configuration.

Centralised logger setup. All modules import from here:
    from bannin.log import logger

Writes to ~/.bannin/bannin.log (rotating, 5 MB max, 3 backups).
Console output is suppressed by default to avoid polluting user's terminal.
"""

from __future__ import annotations

import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

_logger_lock = threading.Lock()


def _get_log_dir() -> Path:
    """Return ~/.bannin/, creating it if needed."""
    log_dir = Path.home() / ".bannin"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _setup_logger() -> logging.Logger:
    """Configure and return the bannin logger."""
    log = logging.getLogger("bannin")

    with _logger_lock:
        if log.handlers:
            return log

        log.setLevel(logging.DEBUG)
        log.propagate = False

        try:
            log_path = _get_log_dir() / "bannin.log"
            handler = RotatingFileHandler(
                str(log_path),
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
                encoding="utf-8",
            )
            handler.setLevel(logging.DEBUG)
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(fmt)
            log.addHandler(handler)
        except Exception:
            # If we can't write to disk, add a NullHandler so logging calls don't error
            import sys
            log.addHandler(logging.NullHandler())
            try:
                sys.stderr.write("bannin: WARNING: could not create log file, logging disabled\n")
            except Exception:
                pass

    return log


logger = _setup_logger()
