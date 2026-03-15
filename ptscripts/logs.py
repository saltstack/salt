from __future__ import annotations

import logging
import os
import sys

STDOUT = sys.maxsize
logging.STDOUT = STDOUT  # type: ignore[attr-defined]
STDERR = sys.maxsize - 1
logging.STDERR = STDERR  # type: ignore[attr-defined]
logging.addLevelName(STDOUT, "STDOUT")
logging.addLevelName(STDERR, "STDERR")


class LevelFilter(logging.Filter):
    def __init__(
        self,
        level: int | None = None,
        not_levels: list[int] | tuple[int, ...] | None = None,
    ) -> None:
        self.level = level
        self.not_levels = not_levels or []

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if self.not_levels and record.levelno in self.not_levels:
            return False
        if self.level and record.levelno != self.level:
            return False
        return True


class DuplicateTimesFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_timestamp: str | None = None

    def formatTime(
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        formatted_time = super().formatTime(record, datefmt=datefmt)
        if self._last_timestamp and formatted_time == self._last_timestamp:
            formatted_time = " " * len(formatted_time)
        else:
            self._last_timestamp = formatted_time
        return formatted_time

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        if "\r\n" in record.msg:
            line_split = "\r\n"
        else:
            line_split = "\n"
        lines = record.msg.replace("\r\n", "\n").splitlines()
        outlines = [lines.pop(0)]
        if self._last_timestamp:
            prefix = " " * len(self._last_timestamp)
        else:
            prefix = " " * len(self.formatTime(record, self.datefmt))
            self._last_timestamp = None
        outlines.extend([f"{prefix}{line.rstrip()}" for line in lines])
        record.msg = line_split.join(outlines).rstrip()
        if line_split.endswith("\r\n"):
            record.msg += "\r"
        return super().format(record)


class LoggingClass(logging.Logger):
    def stderr(self, msg: str, *args, **kwargs):  # noqa: ANN201
        return self.log(STDERR, msg, *args, **kwargs)

    def stdout(self, msg: str, *args, **kwargs):  # noqa: ANN201
        return self.log(STDOUT, msg, *args, **kwargs)


# Override the python's logging logger class as soon as this module is imported
if logging.getLoggerClass() is not LoggingClass:
    logging.setLoggerClass(LoggingClass)

# Reset logging handlers
logging.root.handlers.clear()
logging.root.setLevel(logging.INFO)

NO_TIMESTAMP_FORMATTER = logging.Formatter(fmt="%(message)s")
TIMESTAMP_FORMATTER = DuplicateTimesFormatter(
    fmt="%(asctime)s%(message)s", datefmt="[%H:%M:%S] "
)

DEFAULT_FORMATTER: logging.Formatter | DuplicateTimesFormatter
if "CI" in os.environ:
    DEFAULT_FORMATTER = TIMESTAMP_FORMATTER
else:
    DEFAULT_FORMATTER = NO_TIMESTAMP_FORMATTER
STDERR_HANDLER = logging.StreamHandler(stream=sys.stderr)
STDERR_HANDLER.setLevel(STDERR)
STDERR_HANDLER.addFilter(LevelFilter(level=STDERR))

STDOUT_HANDLER = logging.StreamHandler(stream=sys.stdout)
STDOUT_HANDLER.setLevel(STDOUT)
STDOUT_HANDLER.addFilter(LevelFilter(level=STDOUT))

ROOT_HANDLER = logging.StreamHandler(stream=sys.stderr)
ROOT_HANDLER.setLevel(logging.DEBUG)
ROOT_HANDLER.addFilter(LevelFilter(not_levels=(STDERR, STDOUT)))

for handler in (ROOT_HANDLER, STDERR_HANDLER, STDOUT_HANDLER):
    handler.setFormatter(DEFAULT_FORMATTER)
    logging.root.addHandler(handler)


def include_timestamps() -> bool:
    """
    Return True if any of the configured logging handlers includes timestamps.
    """
    return any(
        handler.formatter is TIMESTAMP_FORMATTER for handler in logging.root.handlers
    )
