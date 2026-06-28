from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


_LOGGER_NAMESPACE = "converse"
_MODULE_FIELD = "converse_module"
_HANDLER_MARKER = "_converse_daily_file_handler"
_DEFAULT_LEVEL = logging.INFO
_CONFIG_LOCK = Lock()

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _default_log_dir() -> Path:
    raw_log_dir = os.getenv("CONVERSE_LOG_DIR")
    if raw_log_dir:
        return Path(raw_log_dir).expanduser()

    return Path(__file__).resolve().parents[1] / "logs"


def _log_file_path(log_dir: Path, when: datetime | None = None) -> Path:
    timestamp = when or datetime.now()
    return log_dir / f"{timestamp:%Y%m%d}_converse.log"


def _prefix_date(timestamp: datetime) -> str:
    return f"{_WEEKDAYS[timestamp.weekday()]}{timestamp:%d}{_MONTHS[timestamp.month - 1]}{timestamp:%y}"


class _ConverseFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created)
        level_name = "WARN" if record.levelname == "WARNING" else record.levelname
        module_name = getattr(record, _MODULE_FIELD, None) or _record_module_name(record)
        message = record.getMessage()
        line = f"{_prefix_date(timestamp)} | {timestamp:%H:%M:%S} | {level_name} | [{module_name}] {message}"

        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"

        return line


class _DailyFileHandler(logging.FileHandler):
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_path = _log_file_path(self.log_dir)
        super().__init__(self._current_path, mode="a", encoding="utf-8", delay=True)

    @property
    def current_path(self) -> Path:
        return self._current_path

    def emit(self, record: logging.LogRecord) -> None:
        record_path = _log_file_path(self.log_dir, datetime.fromtimestamp(record.created))
        if record_path != self._current_path:
            self._switch_to(record_path)

        super().emit(record)

    def _switch_to(self, path: Path) -> None:
        self._current_path = path
        self.baseFilename = str(path)

        if self.stream:
            self.stream.flush()
            self.stream.close()
            self.stream = self._open()


class ConverseLogger:
    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self._logger = logging.getLogger(f"{_LOGGER_NAMESPACE}.{module_name}")

    def info(self, message: object, *args: object, **kwargs: Any) -> None:
        self._log(logging.INFO, message, *args, **kwargs)

    def warning(self, message: object, *args: object, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, *args, **kwargs)

    def error(self, message: object, *args: object, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, *args, **kwargs)

    def _log(self, level: int, message: object, *args: object, **kwargs: Any) -> None:
        configure_logging()
        extra = dict(kwargs.pop("extra", {}) or {})
        extra[_MODULE_FIELD] = self.module_name
        kwargs.setdefault("stacklevel", 3)
        self._logger.log(level, message, *args, extra=extra, **kwargs)


def configure_logging(log_dir: str | Path | None = None) -> Path:
    resolved_log_dir = Path(log_dir).expanduser() if log_dir else _default_log_dir()

    with _CONFIG_LOCK:
        logger = logging.getLogger(_LOGGER_NAMESPACE)
        logger.setLevel(_DEFAULT_LEVEL)
        logger.propagate = False

        handler = _existing_handler(logger)
        if handler is None:
            handler = _DailyFileHandler(resolved_log_dir)
            setattr(handler, _HANDLER_MARKER, True)
            handler.setFormatter(_ConverseFormatter())
            handler.setLevel(logging.NOTSET)
            logger.addHandler(handler)

        return handler.current_path


def get_current_log_file_path() -> Path:
    return configure_logging()


def get_logger(module_name: str) -> ConverseLogger:
    configure_logging()
    return ConverseLogger(module_name)


def _existing_handler(logger: logging.Logger) -> _DailyFileHandler | None:
    for handler in logger.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            return handler

    return None


def _record_module_name(record: logging.LogRecord) -> str:
    prefix = f"{_LOGGER_NAMESPACE}."
    if record.name.startswith(prefix):
        return record.name.removeprefix(prefix)

    return record.module


api_logger = get_logger("api")
conversations_logger = get_logger("conversations")
db_logger = get_logger("db")
debug_logger = get_logger("debug")
eval_logger = get_logger("eval")
followups_logger = get_logger("followups")
memory_logger = get_logger("memory")
persons_logger = get_logger("persons")


__all__ = [
    "ConverseLogger",
    "api_logger",
    "configure_logging",
    "conversations_logger",
    "db_logger",
    "debug_logger",
    "eval_logger",
    "followups_logger",
    "get_current_log_file_path",
    "get_logger",
    "memory_logger",
    "persons_logger",
]
