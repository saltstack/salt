import logging

from salt._logging.handlers import (
    FileHandler,
    QueueHandler,
    RotatingFileHandler,
    StreamHandler,
    SysLogHandler,
    TemporaryLoggingHandler,
    WatchedFileHandler,
)
from salt.utils.versions import warn_until_date

warn_until_date(
    "20240101",
    "Please stop using '{name}' and instead use 'salt._logging.handlers'. "
    "'{name}' will go away after {{date}}.".format(name=__name__),
)

NullHandler = logging.NullHandler
