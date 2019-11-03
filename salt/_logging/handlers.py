"""
    salt._logging.handlers
    ~~~~~~~~~~~~~~~~~~~~~~

    Salt's logging handlers
"""


import atexit
import copy
import logging
import logging.handlers
import os
import pprint
import queue as _queue
import sys
import threading
import traceback
from collections import deque

from salt._logging.mixins import ExcInfoOnLogLevelFormatMixin, NewStyleClassMixin
from salt.utils.versions import warn_until_date

try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

log = logging.getLogger(__name__)


class TemporaryLoggingHandler(logging.NullHandler):
    """
    This logging handler will store all the log records up to its maximum
    queue size at which stage the first messages stored will be dropped.

    Should only be used as a temporary logging handler, while the logging
    system is not fully configured.

    Once configured, pass any logging handlers that should have received the
    initial log messages to the function
    :func:`TemporaryLoggingHandler.sync_with_handlers` and all stored log
    records will be dispatched to the provided handlers.

    .. versionadded:: 0.17.0
    """

    def __init__(self, level=logging.NOTSET, max_queue_size=10000):
        warn_until_date(
            "20230101",
            "Please stop using '{name}.TemporaryLoggingHandler'. "
            "'{name}.TemporaryLoggingHandler' will go away after "
            "{{date}}.".format(name=__name__),
        )
        self.__max_queue_size = max_queue_size
        super().__init__(level=level)
        self.__messages = deque(maxlen=max_queue_size)

    def handle(self, record):
        self.acquire()
        self.__messages.append(record)
        self.release()

    def sync_with_handlers(self, handlers=()):
        """
        Sync the stored log records to the provided log handlers.
        """
        if not handlers:
            return

        while self.__messages:
            record = self.__messages.popleft()
            for handler in handlers:
                if handler.level > record.levelno:
                    # If the handler's level is higher than the log record one,
                    # it should not handle the log record
                    continue
                handler.handle(record)


class StreamHandler(
    ExcInfoOnLogLevelFormatMixin, logging.StreamHandler, NewStyleClassMixin
):
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

    .. versionadded:: 3000.0
    """

    def __init__(self, stream, max_queue_size=10000):
        self.__max_queue_size = max_queue_size
        super().__init__(stream)
        self.__messages = deque(maxlen=max_queue_size)

    def handle(self, record):
        self.acquire()
        self.__messages.append(record)
        self.release()

    def flush(self):
        while self.__messages:
            record = self.__messages.popleft()
            # We call the parent's class handle method so it's actually
            # handled and not queued back
            super().handle(record)
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


class FileHandler(
    ExcInfoOnLogLevelFormatMixin, logging.FileHandler, NewStyleClassMixin
):
    """
    File handler which properly handles exc_info on a per handler basis
    """


class SysLogHandler(
    ExcInfoOnLogLevelFormatMixin, logging.handlers.SysLogHandler, NewStyleClassMixin
):
    """
    Syslog handler which properly handles exc_info on a per handler basis
    """

    def handleError(self, record):
        """
        Override the default error handling mechanism for py3
        Deal with syslog os errors when the log file does not exist
        """
        handled = False
        if sys.stderr and sys.version_info >= (3, 5, 4):
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
    ExcInfoOnLogLevelFormatMixin,
    logging.handlers.RotatingFileHandler,
    NewStyleClassMixin,
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
    ExcInfoOnLogLevelFormatMixin,
    logging.handlers.WatchedFileHandler,
    NewStyleClassMixin,
):
    """
    Watched file handler which properly handles exc_info on a per handler basis
    """


if sys.version_info < (3, 2):

    class QueueHandler(
        ExcInfoOnLogLevelFormatMixin, logging.Handler, NewStyleClassMixin
    ):
        """
        This handler sends events to a queue. Typically, it would be used together
        with a multiprocessing Queue to centralise logging to file in one process
        (in a multi-process application), so as to avoid file write contention
        between processes.

        This code is new in Python 3.2, but this class can be copy pasted into
        user code for use with earlier Python versions.
        """

        def __init__(self, queue):
            """
            Initialise an instance, using the passed queue.
            """
            warn_until_date(
                "20230101",
                "Please stop using '{name}.QueueHandler' and instead "
                "use 'logging.handlers.QueueHandler'. "
                "'{name}.QueueHandler' will go away after "
                "{{date}}.".format(name=__name__),
            )
            logging.Handler.__init__(self)
            self.queue = queue

        def enqueue(self, record):
            """
            Enqueue a record.

            The base implementation uses put_nowait. You may want to override
            this method if you want to use blocking, timeouts or custom queue
            implementations.
            """
            try:
                self.queue.put_nowait(record)
            except _queue.Full:
                sys.stderr.write(
                    "[WARNING ] Message queue is full, "
                    'unable to write "{}" to log'.format(record)
                )

        def prepare(self, record):
            """
            Prepares a record for queuing. The object returned by this method is
            enqueued.
            The base implementation formats the record to merge the message
            and arguments, and removes unpickleable items from the record
            in-place.
            You might want to override this method if you want to convert
            the record to a dict or JSON string, or send a modified copy
            of the record while leaving the original intact.
            """
            # The format operation gets traceback text into record.exc_text
            # (if there's exception data), and also returns the formatted
            # message. We can then use this to replace the original
            # msg + args, as these might be unpickleable. We also zap the
            # exc_info and exc_text attributes, as they are no longer
            # needed and, if not None, will typically not be pickleable.
            msg = self.format(record)
            # bpo-35726: make copy of record to avoid affecting other handlers in the chain.
            record = copy.copy(record)
            record.message = msg
            record.msg = msg
            record.args = None
            record.exc_info = None
            record.exc_text = None
            return record

        def emit(self, record):
            """
            Emit a record.

            Writes the LogRecord to the queue, preparing it for pickling first.
            """
            try:
                self.enqueue(self.prepare(record))
            except Exception:  # pylint: disable=broad-except
                self.handleError(record)


elif sys.version_info < (3, 7):
    # On python versions lower than 3.7, we sill subclass and overwrite prepare to include the fix for:
    #  https://bugs.python.org/issue35726
    class QueueHandler(
        ExcInfoOnLogLevelFormatMixin, logging.handlers.QueueHandler
    ):  # pylint: disable=no-member,inconsistent-mro
        def __init__(self, queue):  # pylint: disable=useless-super-delegation
            super().__init__(queue)
            warn_until_date(
                "20230101",
                "Please stop using '{name}.QueueHandler' and instead "
                "use 'logging.handlers.QueueHandler'. "
                "'{name}.QueueHandler' will go away after "
                "{{date}}.".format(name=__name__),
            )

        def enqueue(self, record):
            """
            Enqueue a record.

            The base implementation uses put_nowait. You may want to override
            this method if you want to use blocking, timeouts or custom queue
            implementations.
            """
            try:
                self.queue.put_nowait(record)
            except _queue.Full:
                sys.stderr.write(
                    "[WARNING ] Message queue is full, "
                    'unable to write "{}" to log.\n'.format(record)
                )

        def prepare(self, record):
            """
            Prepares a record for queuing. The object returned by this method is
            enqueued.
            The base implementation formats the record to merge the message
            and arguments, and removes unpickleable items from the record
            in-place.
            You might want to override this method if you want to convert
            the record to a dict or JSON string, or send a modified copy
            of the record while leaving the original intact.
            """
            # The format operation gets traceback text into record.exc_text
            # (if there's exception data), and also returns the formatted
            # message. We can then use this to replace the original
            # msg + args, as these might be unpickleable. We also zap the
            # exc_info and exc_text attributes, as they are no longer
            # needed and, if not None, will typically not be pickleable.
            msg = self.format(record)
            # bpo-35726: make copy of record to avoid affecting other handlers in the chain.
            record = copy.copy(record)
            record.message = msg
            record.msg = msg
            record.args = None
            record.exc_info = None
            record.exc_text = None
            return record


else:

    class QueueHandler(
        ExcInfoOnLogLevelFormatMixin, logging.handlers.QueueHandler
    ):  # pylint: disable=no-member,inconsistent-mro
        def __init__(self, queue):  # pylint: disable=useless-super-delegation
            super().__init__(queue)
            warn_until_date(
                "20230101",
                "Please stop using '{name}.QueueHandler' and instead "
                "use 'logging.handlers.QueueHandler'. "
                "'{name}.QueueHandler' will go away after "
                "{{date}}.".format(name=__name__),
            )

        def enqueue(self, record):
            """
            Enqueue a record.

            The base implementation uses put_nowait. You may want to override
            this method if you want to use blocking, timeouts or custom queue
            implementations.
            """
            try:
                self.queue.put_nowait(record)
            except _queue.Full:
                sys.stderr.write(
                    "[WARNING ] Message queue is full, "
                    'unable to write "{}" to log.\n'.format(record)
                )


class ZMQHandler(ExcInfoOnLogLevelFormatMixin, logging.Handler, NewStyleClassMixin):

    # We offload sending the log records to the consumer to a separate
    # thread because PUSH socket's WILL block if the receiving end can't
    # receive fast engough, thus, also blocking the main thread.
    #
    # To achive this, we create an inproc zmq.PAIR, which also guarantees
    # message delivery, but should be way faster than the PUSH.
    # We also set some high enough high water mark values to cope with the
    # message flooding.
    #
    # We also implement a start method which is deferred until sending the
    # first message because, logging handlers, on platforms which support
    # forking, are inherited by forked processes, and we don't want the ZMQ
    # machinery inherited.
    # For the cases where the ZMQ machinery is still inherited because a
    # process was forked after ZMQ has been prep'ed up, we check the handler's
    # pid attribute against, the current process pid. If it's not a match, we
    # reconnect the ZMQ machinery.

    def __init__(
        self, host="127.0.0.1", port=3330, log_prefix=None, level=logging.NOTSET
    ):
        if not HAS_ZMQ:
            raise RuntimeError("pyzmq is not installed")
        if not HAS_MSGPACK:
            raise RuntimeError("msgpack is not installed")
        super().__init__(level=level)
        self.pid = os.getpid()
        self.push_address = "tcp://{}:{}".format(host, port)
        self.log_prefix = log_prefix
        self.context = self.proxy_address = self.in_proxy = self.proxy_thread = None

    def start(self):
        if self.pid != os.getpid():
            self.stop()
        elif self.in_proxy is not None:
            return
        atexit.register(self.stop)
        context = in_proxy = None
        try:
            context = zmq.Context()
            self.context = context
        except zmq.ZMQError as exc:
            sys.stderr.write(
                "Failed to create the ZMQ Context: {}\n{}\n".format(
                    exc, traceback.format_exc(exc)
                )
            )
            sys.stderr.flush()

        # Let's start the proxy thread
        socket_bind_event = threading.Event()
        self.proxy_thread = threading.Thread(
            target=self._proxy_logs_target, args=(socket_bind_event,)
        )
        self.proxy_thread.start()
        # Now that we discovered which random port to use, lest's continue with the setup
        if socket_bind_event.wait(5) is not True:
            sys.stderr.write("Failed to bind the ZMQ socket PAIR\n")
            sys.stderr.flush()

        if self.proxy_address is not None:
            # And we can now also connect the messages input side of the proxy
            try:
                in_proxy = self.context.socket(zmq.PAIR)
                in_proxy.set_hwm(100000)
                in_proxy.connect(self.proxy_address)
                self.in_proxy = in_proxy
            except zmq.ZMQError as exc:
                if in_proxy is not None:
                    in_proxy.close(1000)
                sys.stderr.write(
                    "Failed to bind the ZMQ PAIR socket: {}\n{}\n".format(
                        exc, traceback.format_exc(exc)
                    )
                )
                sys.stderr.flush()

    def stop(self):
        try:
            atexit.unregister(self.stop)
        except AttributeError:
            # Python 2
            try:
                atexit._exithandlers.remove((self.stop, (), {}))
            except ValueError:
                # The exit handler isn't registered
                pass

        try:
            if self.in_proxy is not None:
                self.in_proxy.send(msgpack.dumps(None))
                self.in_proxy.close(1500)
                self.proxy_thread.join()
            if self.context is not None:
                self.context.term()
        except Exception as exc:  # pylint: disable=broad-except
            sys.stderr.write(
                "Failed to terminate ZMQHandler: {}\n{}\n".format(
                    exc, traceback.format_exc(exc)
                )
            )
            sys.stderr.flush()
            raise
        finally:
            self.context = self.in_proxy = self.proxy_address = self.proxy_thread = None

    def format(self, record):
        msg = super().format(record)
        if self.log_prefix:
            import salt.utils.stringutils

            msg = str(
                "[{}] {}".format(
                    salt.utils.stringutils.to_unicode(self.log_prefix),
                    salt.utils.stringutils.to_unicode(msg),
                )
            )
        return msg

    def prepare(self, record):
        msg = self.format(record)
        record = copy.copy(record)
        record.msg = msg
        # Reduce network bandwidth, we don't need these any more
        record.args = None
        record.exc_info = None
        record.exc_text = None
        record.message = None  # redundant with msg
        # On Python >= 3.5 we also have stack_info, but we've formatted altready so, reset it
        record.stack_info = None
        try:
            return msgpack.dumps(record.__dict__, use_bin_type=True)
        except TypeError as exc:
            # Failed to serialize something with msgpack
            logging.getLogger(__name__).error(
                "Failed to serialize log record: %s.\n%s",
                exc,
                pprint.pformat(record.__dict__),
            )
            self.handleError(record)

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        # Python's logging machinery acquires a lock before calling this method
        # that's why it's safe to call the start method wihtout an explicit acquire
        self.start()
        if self.in_proxy is None:
            sys.stderr.write(
                "Not sending log message over the wire because "
                "we were unable to properly configure a ZMQ PAIR socket.\n"
            )
            sys.stderr.flush()
            return
        try:
            msg = self.prepare(record)
            self.in_proxy.send(msg)
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)

    def _proxy_logs_target(self, socket_bind_event):
        out_proxy = pusher = None
        try:
            out_proxy = self.context.socket(zmq.PAIR)
            out_proxy.set_hwm(100000)
            proxy_port = out_proxy.bind_to_random_port("tcp://127.0.0.1")
            self.proxy_address = "tcp://127.0.0.1:{}".format(proxy_port)
        except zmq.ZMQError as exc:
            if out_proxy is not None:
                out_proxy.close(1000)
            sys.stderr.write(
                "Failed to bind the ZMQ PAIR socket: {}\n{}\n".format(
                    exc, traceback.format_exc(exc)
                )
            )
            sys.stderr.flush()
            return
        finally:
            socket_bind_event.set()

        try:
            pusher = self.context.socket(zmq.PUSH)
            pusher.set_hwm(100000)
            pusher.connect(self.push_address)
        except zmq.ZMQError as exc:
            if pusher is not None:
                pusher.close(1000)
            sys.stderr.write(
                "Failed to connect the ZMQ PUSH socket: {}\n{}\n".format(
                    exc, traceback.format_exc(exc)
                )
            )
            sys.stderr.flush()

        sentinel = msgpack.dumps(None)
        socket_bind_event.set()

        while True:
            try:
                msg = out_proxy.recv()
                if msg == sentinel:
                    # Received sentinel to stop
                    break
                pusher.send(msg)
            except zmq.ZMQError as exc:
                sys.stderr.write(
                    "Failed to proxy log message: {}\n{}\n".format(
                        exc, traceback.format_exc(exc)
                    )
                )
                sys.stderr.flush()
                break

        # Close the receiving end of the PAIR proxy socket
        out_proxy.close(0)
        # Allow, the pusher queue to send any messsges in it's queue for
        # the next 1.5 seconds
        pusher.close(1500)
