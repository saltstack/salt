"""
    salt._logging.handlers
    ~~~~~~~~~~~~~~~~~~~~~~

    Salt's logging handlers
"""

import logging
import logging.handlers
import sys
from collections import deque

from salt._logging.mixins import ExcInfoOnLogLevelFormatMixin

log = logging.getLogger(__name__)


class StreamHandler(ExcInfoOnLogLevelFormatMixin, logging.StreamHandler):
    """
    Stream handler which properly handles exc_info on a per handler basis
    """


class DeferredStreamHandler(StreamHandler):
    """
    This logging handler will store all the log records up to its maximum
    queue size at which stage the first messages stored will be dropped.

    Should only be used as a temporary logging handler, while the logging
    system is not fully configured.

    Once configured, pass any logging handlers that should have received the
    initial log messages to the function
    :func:`DeferredStreamHandler.sync_with_handlers` and all stored log
    records will be dispatched to the provided handlers.

    If anything goes wrong before logging is properly setup, all stored messages
    will be flushed to the handler's stream, ie, written to console.

    .. versionadded:: 3005
    """

    def __init__(self, stream, max_queue_size=10000):
        super().__init__(stream)
        self.__messages = deque(maxlen=max_queue_size)
        self.__emitting = False

    def handle(self, record):
        self.acquire()
        self.__messages.append(record)
        self.release()

    def flush(self):
        if self.__emitting:
            # We set the flushing flag because the stream handler actually calls flush when
            # emitting a log record and we don't want to cause a RecursionError
            return
        while self.__messages:
            try:
                self.__emitting = True
                record = self.__messages.popleft()
                # We call the parent's class handle method so it's actually
                # handled and not queued back
                # However, temporarily
                super().handle(record)
            finally:
                self.__emitting = False
        # Seeing an exception from calling flush on a closed file in the test
        # suite. Handling this condition for now but this seems to be
        # indicitive of an un-clean teardown at some point.
        if not self.stream.closed:
            super().flush()

    def sync_with_handlers(self, handlers=()):
        """
        Sync the stored log records to the provided log handlers.
        """
        while self.__messages:
            record = self.__messages.popleft()
            for handler in handlers:
                if handler is self:
                    continue
                handler.handle(record)


class FileHandler(ExcInfoOnLogLevelFormatMixin, logging.FileHandler):
    """
    File handler which properly handles exc_info on a per handler basis
    """


class SysLogHandler(ExcInfoOnLogLevelFormatMixin, logging.handlers.SysLogHandler):
    """
    Syslog handler which properly handles exc_info on a per handler basis
    """

    def handleError(self, record):
        """
        Override the default error handling mechanism for py3
        Deal with syslog os errors when the log file does not exist
        """
        handled = False
        if sys.stderr:
            exc_type, exc, exc_traceback = sys.exc_info()
            try:
                if exc_type.__name__ in "FileNotFoundError":
                    sys.stderr.write(
                        "[WARNING ] The log_file does not exist. Logging not "
                        "setup correctly or syslog service not started.\n"
                    )
                    handled = True
            finally:
                # 'del' recommended. See documentation of
                # 'sys.exc_info()' for details.
                del exc_type, exc, exc_traceback

        if not handled:
            super().handleError(record)


class RotatingFileHandler(
    ExcInfoOnLogLevelFormatMixin, logging.handlers.RotatingFileHandler
):
    """
    Rotating file handler which properly handles exc_info on a per handler basis
    """

    def handleError(self, record):
        """
        Override the default error handling mechanism

        Deal with log file rotation errors due to log file in use
        more softly.
        """
        handled = False

        # Can't use "salt.utils.platform.is_windows()" in this file
        if (
            sys.platform.startswith("win") and logging.raiseExceptions and sys.stderr
        ):  # see Python issue 13807
            exc_type, exc, exc_traceback = sys.exc_info()
            try:
                # PermissionError is used since Python 3.3.
                # OSError is used for previous versions of Python.
                if (
                    exc_type.__name__ in ("PermissionError", "OSError")
                    and exc.winerror == 32
                ):
                    if self.level <= logging.WARNING:
                        sys.stderr.write(
                            '[WARNING ] Unable to rotate the log file "{}" '
                            "because it is in use\n".format(self.baseFilename)
                        )
                    handled = True
            finally:
                # 'del' recommended. See documentation of
                # 'sys.exc_info()' for details.
                del exc_type, exc, exc_traceback

        if not handled:
            super().handleError(record)


class WatchedFileHandler(
    ExcInfoOnLogLevelFormatMixin, logging.handlers.WatchedFileHandler
):
    """
    Watched file handler which properly handles exc_info on a per handler basis
    """
