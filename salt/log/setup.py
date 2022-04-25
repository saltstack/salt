# pylint: disable=unused-import
from functools import wraps

from salt._logging.handlers import (
    FileHandler,
    QueueHandler,
    RotatingFileHandler,
    StreamHandler,
    SysLogHandler,
    WatchedFileHandler,
)
from salt._logging.impl import (
    LOG_COLORS,
    LOG_LEVELS,
    LOG_VALUES_TO_LEVELS,
    SORTED_LEVEL_NAMES,
    SaltColorLogRecord,
    SaltLogRecord,
)
from salt._logging.impl import set_log_record_factory as setLogRecordFactory
from salt.utils.versions import warn_until_date

warn_until_date(
    "20240101",
    "Please stop using '{name}' and instead use 'salt._logging'. "
    "'{name}' will go away after {{date}}. Do note however that "
    "'salt._logging' is now considered a non public implementation "
    "and is subject to change without deprecations.".format(name=__name__),
    stacklevel=4,
)


def _deprecated_warning(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        warn_until_date(
            "20240101",
            "Please stop using 'salt.log.setup.{name}()' as it no longer does anything and "
            "will go away after {{date}}.".format(name=func.__qualname__),
            stacklevel=4,
        )

    return wrapper


@_deprecated_warning
def is_console_configured():
    pass


@_deprecated_warning
def is_logfile_configured():
    pass


@_deprecated_warning
def is_logging_configured():
    pass


@_deprecated_warning
def is_temp_logging_configured():
    pass


@_deprecated_warning
def is_mp_logging_listener_configured():
    pass


@_deprecated_warning
def is_mp_logging_configured():
    pass


@_deprecated_warning
def is_extended_logging_configured():
    pass


class SaltLogQueueHandler(QueueHandler):
    """
    Subclassed just to differentiate when debugging
    """


@_deprecated_warning
def getLogger(name):
    pass


@_deprecated_warning
def setup_temp_logger(log_level="error"):
    pass


@_deprecated_warning
def setup_console_logger(log_level="error", log_format=None, date_format=None):
    pass


@_deprecated_warning
def setup_logfile_logger(
    log_path,
    log_level="error",
    log_format=None,
    date_format=None,
    max_bytes=0,
    backup_count=0,
):
    pass


@_deprecated_warning
def setup_extended_logging(opts):
    pass


@_deprecated_warning
def get_multiprocessing_logging_queue():
    pass


@_deprecated_warning
def set_multiprocessing_logging_queue(queue):
    pass


@_deprecated_warning
def get_multiprocessing_logging_level():
    pass


@_deprecated_warning
def set_multiprocessing_logging_level(log_level):
    pass


@_deprecated_warning
def set_multiprocessing_logging_level_by_opts(opts):
    pass


@_deprecated_warning
def setup_multiprocessing_logging(queue=None):
    pass


@_deprecated_warning
def shutdown_console_logging():
    pass


@_deprecated_warning
def shutdown_logfile_logging():
    pass


@_deprecated_warning
def shutdown_temp_logging():
    pass


@_deprecated_warning
def shutdown_multiprocessing_logging():
    pass


@_deprecated_warning
def shutdown_multiprocessing_logging_listener(daemonizing=False):
    pass


@_deprecated_warning
def set_logger_level(logger_name, log_level="error"):
    pass


@_deprecated_warning
def patch_python_logging_handlers():
    pass


@_deprecated_warning
def __process_multiprocessing_logging_queue(opts, queue):
    pass


@_deprecated_warning
def __remove_null_logging_handler():
    pass


@_deprecated_warning
def __remove_queue_logging_handler():
    pass


@_deprecated_warning
def __remove_temp_logging_handler():
    pass
