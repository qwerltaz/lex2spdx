"""lex2spdx logger."""

import datetime
import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import Optional

import colorama
from colorama import Fore, Style

from . import cvar

colorama.init()


class _ColoredFormatter(logging.Formatter):
    """Formatter that colors the levelname for terminal output."""

    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        levelno = record.levelno
        color = self.LEVEL_COLORS.get(levelno, "")
        if color:
            original = record.levelname
            try:
                record.levelname = f"{color}{original}{Style.RESET_ALL}"
                return super().format(record)
            finally:
                record.levelname = original
        return super().format(record)


_logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[%(levelname)s] %(message)s"},
        "verbose": {
            "format": "[%(levelname)s] %(asctime)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
        "color_verbose": {
            "()": _ColoredFormatter,
            "format": "[%(levelname)s] %(asctime)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "color_verbose",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "verbose",
            "filename": ".log",  # The default, overwritten by calling script's name.
            "mode": "a",
            "encoding": "utf-8",
        },
    },
    # Propagate this logger and library loggers, then root logs to stdout and file.
    "loggers": {
        "local_logger": {"level": "DEBUG", "propagate": True},
        "git": {"level": "DEBUG", "propagate": True},
        "git.cmd": {"level": "DEBUG", "propagate": True},
    },
    "root": {"level": "DEBUG", "handlers": ["stdout", "file"]},
}

_is_configured = False
_run_log_file_path: str | None = None


def _build_run_log_file_path() -> str:
    script_stem = Path(sys.argv[0]).stem or "session"
    run_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    return str(cvar.logs_dir / f"{script_stem}-{run_timestamp}-{os.getpid()}.log")


def _configure_logging_once() -> None:
    global _is_configured
    global _run_log_file_path

    if _is_configured:
        return

    cvar.logs_dir.mkdir(parents=True, exist_ok=True)
    _run_log_file_path = _build_run_log_file_path()
    _logging_config["handlers"]["file"]["filename"] = _run_log_file_path
    logging.config.dictConfig(_logging_config)
    _is_configured = True


def get() -> logging.Logger:
    """Get a configured logger instance."""
    _configure_logging_once()
    logger = logging.getLogger("local_logger")

    logger.info("Hi.")
    return logger
