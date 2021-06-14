"""
pytest_log_handler
~~~~~~~~~~~~~~~~~~

Salt External Logging Handler
"""
import atexit
import copy
import logging
import os
import pprint
import socket
import sys
import threading
import time
import traceback

# pylint: disable=import-error,no-name-in-module
try:
    from salt.utils.stringutils import to_unicode
except ImportError:
    # This likely due to running backwards compatibility tests against older minions
    from salt.utils import to_unicode
try:
    from salt._logging.impl import LOG_LEVELS
    from salt._logging.mixins import ExcInfoOnLogLevelFormatMixin
except ImportError:
    # This likely due to running backwards compatibility tests against older minions
    from salt.log.setup import LOG_LEVELS
    from salt.log.mixins import (
        ExcInfoOnLogLevelFormatMixIn as ExcInfoOnLogLevelFormatMixin,
    )
try:
    from salt._logging.mixins import NewStyleClassMixin
except ImportError:
    try:
        # This likely due to running backwards compatibility tests against older minions
        from salt.log.mixins import NewStyleClassMixIn as NewStyleClassMixin
    except ImportError:
        # NewStyleClassMixin was removed from salt

        class NewStyleClassMixin:
            """
            A copy of Salt's previous NewStyleClassMixin implementation
            """


# pylint: enable=import-error,no-name-in-module

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


__virtualname__ = "pytest_log_handler"

log = logging.getLogger(__name__)


def __virtual__():
    role = __opts__["__role"]
    pytest_key = "pytest-{}".format(role)

    pytest_config = __opts__[pytest_key]
    if "log" not in pytest_config:
        return False, "No 'log' key in opts {} dictionary".format(pytest_key)

    log_opts = pytest_config["log"]
    if "port" not in log_opts:
        return (
            False,
            "No 'port' key in opts['pytest']['log'] or opts['pytest'][{}]['log']".format(
                __opts__["role"]
            ),
        )
    if HAS_MSGPACK is False:
        return False, "msgpack was not importable. Please install msgpack."
    if HAS_ZMQ is False:
        return False, "zmq was not importable. Please install pyzmq."
    return True


def setup_handlers():
    role = __opts__["__role"]
    pytest_key = "pytest-{}".format(role)
    pytest_config = __opts__[pytest_key]
    log_opts = pytest_config["log"]
    if log_opts.get("disabled"):
        return
    host_addr = log_opts.get("host")
    if not host_addr:
        import subprocess

        if log_opts["pytest_windows_guest"] is True:
            proc = subprocess.Popen("ipconfig", stdout=subprocess.PIPE)
            for line in (
                proc.stdout.read().strip().encode(__salt_system_encoding__).splitlines()
            ):
                if "Default Gateway" in line:
                    parts = line.split()
                    host_addr = parts[-1]
                    break
        else:
            proc = subprocess.Popen(
                "netstat -rn | grep -E '^0.0.0.0|default' | awk '{ print $2 }'",
                shell=True,
                stdout=subprocess.PIPE,
            )
            host_addr = proc.stdout.read().strip().encode(__salt_system_encoding__)
    host_port = log_opts["port"]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host_addr, host_port))
    except OSError as exc:
        # Don't even bother if we can't connect
        log.warning(
            "Cannot connect back to log server at %s:%d: %s", host_addr, host_port, exc
        )
        return
    finally:
        sock.close()

    pytest_log_prefix = log_opts.get("prefix")
    try:
        level = LOG_LEVELS[(log_opts.get("level") or "error").lower()]
    except KeyError:
        level = logging.ERROR
    handler = ZMQHandler(
        host=host_addr, port=host_port, log_prefix=pytest_log_prefix, level=level
    )
    handler.setLevel(level)
    handler.start()
    return handler


class ZMQHandler(ExcInfoOnLogLevelFormatMixin, logging.Handler, NewStyleClassMixin):

    # We offload sending the log records to the consumer to a separate
    # thread because PUSH socket's WILL block if the receiving end can't
    # receive fast enough, thus, also blocking the main thread.
    #
    # To achieve this, we create an inproc zmq.PAIR, which also guarantees
    # message delivery, but should be way faster than the PUSH.
    # We also set some high enough high water mark values to cope with the
    # message flooding.
    #
    # We also implement a start method which is deferred until sending the
    # first message because, logging handlers, on platforms which support
    # forking, are inherited by forked processes, and we don't want the ZMQ
    # machinery inherited.
    # For the cases where the ZMQ machinery is still inherited because a
    # process was forked after ZMQ has been prepped up, we check the handler's
    # pid attribute against the current process pid. If it's not a match, we
    # reconnect the ZMQ machinery.

    def __init__(
        self, host="127.0.0.1", port=3330, log_prefix=None, level=logging.NOTSET
    ):
        super().__init__(level=level)
        self.pid = os.getpid()
        self.push_address = "tcp://{}:{}".format(host, port)
        self.log_prefix = self._get_log_prefix(log_prefix)
        self.context = self.proxy_address = self.in_proxy = self.proxy_thread = None
        self.running_event = threading.Event()
        self._exiting = False

    def _get_log_prefix(self, log_prefix):
        if log_prefix is None:
            return
        if sys.argv[0] == sys.executable:
            cli_arg_idx = 1
        else:
            cli_arg_idx = 0
        cli_name = os.path.basename(sys.argv[cli_arg_idx])
        return log_prefix.format(cli_name=cli_name)

    def start(self):
        if self.pid != os.getpid():
            self.stop()
            self._exiting = False

        if self._exiting is True:
            return

        if self.in_proxy is not None:
            # We're running ...
            return

        atexit.register(self.stop)
        context = in_proxy = None
        try:
            context = zmq.Context()
            self.context = context
        except zmq.ZMQError as exc:
            sys.stderr.write(
                "Failed to create the ZMQ Context: {}\n{}\n".format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            self.stop()
            # Allow the handler to re-try starting
            self._exiting = False
            return

        # Let's start the proxy thread
        socket_bind_event = threading.Event()
        self.proxy_thread = threading.Thread(
            target=self._proxy_logs_target, args=(socket_bind_event, self.running_event)
        )
        self.proxy_thread.start()
        # Now that we discovered which random port to use, let's continue with the setup
        if socket_bind_event.wait(5) is not True:
            sys.stderr.write("Failed to bind the ZMQ socket PAIR\n")
            sys.stderr.flush()
            socket_bind_event.clear()
            self.running_event.clear()
            context.term()
            if self.proxy_thread.is_alive():
                # Wait for the thread to terminate
                self.proxy_thread.join(5)
                if self.proxy_thread.is_alive():
                    # Hmm.. Still alive?!
                    # Wait a little longer
                    self.proxy_thread.join(5)
            self.context = self.proxy_thread = None
            self.stop()
            # Allow the handler to re-try starting
            self._exiting = False
            return

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
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            socket_bind_event.clear()
            self.running_event.clear()
            self.context.term()
            if self.proxy_thread.is_alive():
                # Wait for the thread to terminate
                self.proxy_thread.join(5)
                if self.proxy_thread.is_alive():
                    # Hmm.. Still alive?!
                    # Wait a little longer
                    self.proxy_thread.join(5)
            self.context = self.proxy_thread = self.proxy_address = None
            self.stop()
            # Allow the handler to re-try starting
            self._exiting = False
            return

        self.pid = os.getpid()  # In case we're restarting
        self.running_event.set()

    def stop(self):
        if self._exiting:
            return

        self._exiting = True
        self.running_event.clear()

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
            if self.in_proxy is not None and not self.in_proxy.closed:
                # Give it 1.5 seconds to flush any messages in it's queue
                self.in_proxy.close(1500)
                self.in_proxy = None
            if self.context is not None and not self.context.closed:
                self.context.term()
                self.context = None
            if self.proxy_thread is not None and self.proxy_thread.is_alive():
                # Wait for the thread to terminate
                self.proxy_thread.join(5)
                if self.proxy_thread.is_alive():
                    # Hmm.. Still alive?!
                    # Wait a little longer
                    self.proxy_thread.join(5)
                self.proxy_thread = None
        except (  # pragma: no cover pylint: disable=try-except-raise
            SystemExit,
            KeyboardInterrupt,
        ):
            # Don't write these exceptions to stderr
            raise
        except Exception as exc:  # pragma: no cover pylint: disable=broad-except
            sys.stderr.write(
                "Failed to terminate ZMQHandler: {}\n{}\n".format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            raise
        finally:
            self.context = self.in_proxy = self.proxy_address = self.proxy_thread = None

    def format(self, record):
        msg = super().format(record)
        if self.log_prefix:
            msg = "[{}] {}".format(to_unicode(self.log_prefix), to_unicode(msg))
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
        # On Python >= 3.5 we also have stack_info, but we've formatted already so, reset it
        record.stack_info = None
        try:
            return msgpack.dumps(record.__dict__, use_bin_type=True)
        except TypeError as exc:
            # Failed to serialize something with msgpack
            sys.stderr.write(
                "Failed to serialize log record:{}.\n{}\nLog Record:\n{}\n".format(
                    exc, traceback.format_exc(), pprint.pformat(record.__dict__)
                )
            )
            sys.stderr.flush()
            self.handleError(record)

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        # Python's logging machinery acquires a lock before calling this method
        # that's why it's safe to call the start method without an explicit acquire
        if self._exiting:
            return
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
        except (  # pragma: no cover pylint: disable=try-except-raise
            SystemExit,
            KeyboardInterrupt,
        ):
            # Catch and raise SystemExit and KeyboardInterrupt so that we can handle
            # all other exception below
            raise
        except Exception:  # pragma: no cover pylint: disable=broad-except
            self.handleError(record)

    def _proxy_logs_target(self, socket_bind_event, running_event):
        context = zmq.Context()
        out_proxy = pusher = None
        try:
            out_proxy = context.socket(zmq.PAIR)
            out_proxy.set_hwm(100000)
            proxy_port = out_proxy.bind_to_random_port("tcp://127.0.0.1")
            self.proxy_address = "tcp://127.0.0.1:{}".format(proxy_port)
        except zmq.ZMQError as exc:
            if out_proxy is not None:
                out_proxy.close(1000)
            context.term()
            sys.stderr.write(
                "Failed to bind the ZMQ PAIR socket: {}\n{}\n".format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            return

        try:
            pusher = context.socket(zmq.PUSH)
            pusher.set_hwm(100000)
            pusher.connect(self.push_address)
        except zmq.ZMQError as exc:
            if pusher is not None:
                pusher.close(1000)
            context.term()
            sys.stderr.write(
                "Failed to connect the ZMQ PUSH socket: {}\n{}\n".format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            return

        socket_bind_event.set()

        try:
            if running_event.wait(5) is False:
                sys.stderr.write(
                    "Running event failed to set after 5 seconds. Stop processing...."
                )
                sys.stderr.flush()
                self.stop()
                return

            while running_event.is_set():
                try:
                    msg = out_proxy.recv(zmq.NOBLOCK)
                    pusher.send(msg)
                except zmq.error.Again:
                    # no messages yet, a little sleep
                    time.sleep(0.001)
                except zmq.ZMQError as exc:
                    sys.stderr.write(
                        "Failed to proxy log message: {}\n{}\n".format(
                            exc, traceback.format_exc()
                        )
                    )
                    sys.stderr.flush()
                    self.stop()
                    break
        finally:
            # Close the receiving end of the PAIR proxy socket
            if not out_proxy.closed:
                out_proxy.close(0)
            if not pusher.closed:
                # Allow, the pusher queue to send any messages in it's queue for
                # the next 1.5 seconds
                pusher.close(1500)
            if not context.closed:
                context.term()
