# -*- coding: utf-8 -*-
'''
    salt.log.handlers
    ~~~~~~~~~~~~~~~~~

    .. versionadded:: 0.17.0

    Custom logging handlers to be used in salt.
'''
from __future__ import absolute_import

# Import python libs
import sys
import atexit
import logging
import threading
import logging.handlers

# Import salt libs
from salt.log.mixins import NewStyleClassMixIn, ExcInfoOnLogLevelFormatMixIn

log = logging.getLogger(__name__)


if sys.version_info < (2, 7):
    # Since the NullHandler is only available on python >= 2.7, here's a copy
    # with NewStyleClassMixIn so it's also a new style class
    class NullHandler(logging.Handler, NewStyleClassMixIn):
        '''
        This is 1 to 1 copy of python's 2.7 NullHandler
        '''
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):  # pylint: disable=C0103
            self.lock = None

    logging.NullHandler = NullHandler


class TemporaryLoggingHandler(logging.NullHandler):
    '''
    This logging handler will store all the log records up to its maximum
    queue size at which stage the first messages stored will be dropped.

    Should only be used as a temporary logging handler, while the logging
    system is not fully configured.

    Once configured, pass any logging handlers that should have received the
    initial log messages to the function
    :func:`TemporaryLoggingHandler.sync_with_handlers` and all stored log
    records will be dispatched to the provided handlers.

    .. versionadded:: 0.17.0
    '''

    def __init__(self, level=logging.NOTSET, max_queue_size=10000):
        self.__max_queue_size = max_queue_size
        super(TemporaryLoggingHandler, self).__init__(level=level)
        self.__messages = []

    def handle(self, record):
        self.acquire()
        if len(self.__messages) >= self.__max_queue_size:
            # Loose the initial log records
            self.__messages.pop(0)
        self.__messages.append(record)
        self.release()

    def sync_with_handlers(self, handlers=()):
        '''
        Sync the stored log records to the provided log handlers.
        '''
        if not handlers:
            return

        while self.__messages:
            record = self.__messages.pop(0)
            for handler in handlers:
                if handler.level > record.levelno:
                    # If the handler's level is higher than the log record one,
                    # it should not handle the log record
                    continue
                handler.handle(record)


class StreamHandler(ExcInfoOnLogLevelFormatMixIn, logging.StreamHandler, NewStyleClassMixIn):
    '''
    Stream handler which properly handles exc_info on a per handler basis
    '''


class FileHandler(ExcInfoOnLogLevelFormatMixIn, logging.FileHandler, NewStyleClassMixIn):
    '''
    File handler which properly handles exc_info on a per handler basis
    '''


class SysLogHandler(ExcInfoOnLogLevelFormatMixIn, logging.handlers.SysLogHandler, NewStyleClassMixIn):
    '''
    Syslog handler which properly handles exc_info on a per handler basis
    '''


if sys.version_info > (2, 6):
    class WatchedFileHandler(ExcInfoOnLogLevelFormatMixIn, logging.handlers.WatchedFileHandler, NewStyleClassMixIn):
        '''
        Watched file handler which properly handles exc_info on a per handler basis
        '''
