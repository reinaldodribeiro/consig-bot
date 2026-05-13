"""Loguru configuration — clean (default) or debug console mode.

File sinks always at DEBUG. Idempotent — safe to call multiple times so the
entrypoint can reconfigure once `config.bot.debug` is known.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.utils.paths import ensure_dir

_CLEAN_FORMAT = (
    "<dim>{time:HH:mm:ss}</dim> "
    "<level>{level: <7}</level> "
    "{message}"
)
_DEBUG_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "{message}"
)
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{name}:{function}:{line} - {message}"
)
_ERROR_FILE_FORMAT = _FILE_FORMAT + "\n{exception}"


def configure_loguru(log_dir: Path, debug: bool = False) -> None:
    """Configure Loguru sinks. `debug=True` makes the console verbose."""
    ensure_dir(log_dir)
    logger.remove()

    if debug:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format=_DEBUG_FORMAT,
            colorize=True,
            backtrace=False,
            diagnose=False,
        )
    else:
        # Clean mode: only WARNING+ in console; user-facing milestones go via Rich.
        logger.add(
            sys.stderr,
            level="WARNING",
            format=_CLEAN_FORMAT,
            colorize=True,
            backtrace=False,
            diagnose=False,
        )

    logger.add(
        log_dir / "consig-bot_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format=_FILE_FORMAT,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format=_ERROR_FILE_FORMAT,
        rotation="10 MB",
        retention="30 days",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
