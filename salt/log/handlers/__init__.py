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


if sys.version_info < (3, 2):
    class QueueHandler(ExcInfoOnLogLevelFormatMixIn, logging.Handler, NewStyleClassMixIn):
        '''
        This handler sends events to a queue. Typically, it would be used together
        with a multiprocessing Queue to centralise logging to file in one process
        (in a multi-process application), so as to avoid file write contention
        between processes.

        This code is new in Python 3.2, but this class can be copy pasted into
        user code for use with earlier Python versions.
        '''

        def __init__(self, queue):
            '''
            Initialise an instance, using the passed queue.
            '''
            logging.Handler.__init__(self)
            self.queue = queue

        def enqueue(self, record):
            '''
            Enqueue a record.

            The base implementation uses put_nowait. You may want to override
            this method if you want to use blocking, timeouts or custom queue
            implementations.
            '''
            self.queue.put_nowait(record)

        def prepare(self, record):
            '''
            Prepares a record for queuing. The object returned by this method is
            enqueued.

            The base implementation formats the record to merge the message
            and arguments, and removes unpickleable items from the record
            in-place.

            You might want to override this method if you want to convert
            the record to a dict or JSON string, or send a modified copy
            of the record while leaving the original intact.
            '''
            # The format operation gets traceback text into record.exc_text
            # (if there's exception data), and also puts the message into
            # record.message. We can then use this to replace the original
            # msg + args, as these might be unpickleable. We also zap the
            # exc_info attribute, as it's no longer needed and, if not None,
            # will typically not be pickleable.
            self.format(record)
            record.msg = record.getMessage()
            record.args = None
            record.exc_info = None
            return record

        def emit(self, record):
            '''
            Emit a record.

            Writes the LogRecord to the queue, preparing it for pickling first.
            '''
            try:
                self.enqueue(self.prepare(record))
            except Exception:
                self.handleError(record)
else:
    class QueueHandler(ExcInfoOnLogLevelFormatMixIn, logging.handlers.QueueHandler):  # pylint: disable=no-member,E0240
        pass
