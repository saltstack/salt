# -*- coding: utf-8 -*-
'''
    salt.log.handlers
    ~~~~~~~~~~~~~~~~~

    Custom logging handlers to be used in salt.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import sys
import atexit
import logging
import threading

# Import salt libs
from salt._compat import Queue
from salt.log.mixins import NewStyleClassMixIn

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
    This logging handler will store all the log records up to it's maximum
    queue size at which stage the first messages stored will be dropped.

    Should only be used as a temporary logging handler, while the logging
    system is not fully configured.

    Once configured, pass any logging handlers that should have received the
    initial log messages to the function
    :func:`TemporaryLoggingHandler.sync_with_handlers` and all stored log
    records will be dispatched to the provided handlers.
    '''

    def __init__(self, max_queue_size=10000):
        self.__max_queue_size = max_queue_size
        super(TemporaryLoggingHandler, self).__init__()
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
                handler.handle(record)


class QueueDispatchingHandler(logging.Handler, NewStyleClassMixIn):
    '''
    This logging handler is heavily inspired by Python 3 Queue logging handler
    and dispatcher.

    http://docs.python.org/3.4/howto/logging-cookbook.html#dealing-with-handlers-that-block
    '''

    _sentinel = object()

    def __init__(self, queue_size=-1):
        super(QueueDispatchingHandler, self).__init__()
        self._handlers = set()
        self._queue = Queue.Queue(queue_size)
        self._stop = threading.Event()
        self._thread = None

    def addHandler(self, handler):
        log.debug(
            'Adding handler {0!r} to {1!r}'.format(
                handler, self.__class__.__name__
            )
        )
        self._handlers.add(handler)

    def removeHandler(self, handler):
        log.debug(
            'Removing handler {0!r} from {1!r}'.format(
                handler, self.__class__.__name__
            )
        )
        self._handlers.remove(handler)

    def enqueue(self, record):
        self._queue.put_nowait(record)

    def dequeue(self, block):
        return self._queue.get(block)

    def handle(self, record):
        try:
            self.enqueue(record)
        except (KeyboardInterrupt, SystemExit):
            self.stop()
            raise
        except:
            self.handleError(record)

    def emit(self, record):
        '''
        This will never get called but it's overridden
        '''

    def dispatch(self, record):
        for handler in self._handlers:
            handler.handle(record)

    def start(self):
        log.debug(
            'Starting background dispatcher thread on {0!r}'.format(
                self.__class__.__name__
            )
        )
        self._thread = threading.Thread(target=self._monitor)
        self._thread.daemon = True
        self._thread.start()
        atexit.register(self.__shutdown_on_mainthread_exit)

    def stop(self, timeout=5):
        qsize = self._queue.qsize()
        if qsize:
            log.info(
                'Attempting to process {0} log records on {1}. Waiting up to '
                '{2} seconds...'.format(
                    qsize,
                    self.__class__.__name__,
                    timeout
                )
            )
        self._stop.set()
        self.enqueue(self._sentinel)
        self._thread.join(timeout=timeout)
        self._thread = None
        for handler in self._handlers:
            if not hasattr(handler, 'stop'):
                continue
            handler.stop()
        # The next log message should only be seen on the console and file
        # loggers since we've now stopped all other logging handlers
        log.debug('Stopped {0!r} process.'.format(self.__class__.__name__))

    def _monitor(self):
        has_task_done = hasattr(self._queue, 'task_done')
        while not self._stop.isSet():
            try:
                record = self.dequeue(True)
                if record is self._sentinel:
                    break
                self.dispatch(record)
                if has_task_done:
                    self._queue.task_done()
            except Queue.Empty:
                pass
        # There might still be records in the queue.
        while True:
            try:
                record = self.dequeue(False)
                if record is self._sentinel:
                    break
                self.dispatch(record)
                if has_task_done:
                    self._queue.task_done()
            except Queue.Empty:
                break

    def __shutdown_on_mainthread_exit(self):
        self.stop()
