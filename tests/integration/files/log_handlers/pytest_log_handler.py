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
import traceback

# pylint: disable=import-error,no-name-in-module
try:
    from salt.utils.stringutils import to_unicode
except ImportError:  # pragma: no cover
    # This likely due to running backwards compatibility tests against older minions
    from salt.utils import to_unicode
try:
    from salt._logging.impl import LOG_LEVELS
    from salt._logging.mixins import ExcInfoOnLogLevelFormatMixin
except ImportError:  # pragma: no cover
    # This likely due to running backwards compatibility tests against older minions
    from salt.log.setup import LOG_LEVELS
    from salt.log.mixins import (
        ExcInfoOnLogLevelFormatMixIn as ExcInfoOnLogLevelFormatMixin,
    )
try:
    from salt._logging.mixins import NewStyleClassMixin
except ImportError:  # pragma: no cover
    try:
        # This likely due to running backwards compatibility tests against older minions
        from salt.log.mixins import NewStyleClassMixIn as NewStyleClassMixin
    except ImportError:  # pragma: no cover
        # NewStyleClassMixin was removed from salt

        class NewStyleClassMixin:
            """
            A copy of Salt's previous NewStyleClassMixin implementation
            """


# pylint: enable=import-error,no-name-in-module

try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:  # pragma: no cover
    HAS_MSGPACK = False
try:
    import zmq

    HAS_ZMQ = True
except ImportError:  # pragma: no cover
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

    # The start method is deferred until sending the first message because,
    # logging handlers, on platforms which support forking, are inherited
    # by forked processes, and we don't want the ZMQ machinery inherited.
    # For the cases where the ZMQ machinery is still inherited because a
    # process was forked after ZMQ has been prepped up, we check the handler's
    # pid attribute against the current process pid. If it's not a match, we
    # reconnect the ZMQ machinery.

    def __init__(
        self,
        host="127.0.0.1",
        port=3330,
        log_prefix=None,
        level=logging.NOTSET,
        socket_hwm=100000,
    ):
        super().__init__(level=level)
        self.pid = None
        self.host = host
        self.port = port
        self._log_prefix = log_prefix
        self.socket_hwm = socket_hwm
        self.log_prefix = self._get_log_prefix(log_prefix)
        self.context = self.pusher = None
        self._exiting = False

    def __getstate__(self):
        return {
            "host": self.host,
            "port": self.port,
            "log_prefix": self._log_prefix,
            "level": self.level,
            "socket_hwm": self.socket_hwm,
        }

    def __setstate__(self, state):
        self.__init__(**state)
        self.stop()
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
        if self.pid and self.pid != os.getpid():
            # This is not the starting pid, reconnect
            self.stop(flush=False)
            self._exiting = False

        if self._exiting is True:
            return

        if self.pusher is not None:
            # We're running ...
            return

        atexit.register(self.stop)
        context = pusher = None
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

        try:
            pusher = context.socket(zmq.PUSH)
            pusher.set_hwm(self.socket_hwm)
            pusher.connect("tcp://{}:{}".format(self.host, self.port))
            self.pusher = pusher
        except zmq.ZMQError as exc:
            if pusher is not None:
                pusher.close(0)
            sys.stderr.write(
                "Failed to connect the ZMQ PUSH socket: {}\n{}\n".format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            self.stop()
            # Allow the handler to re-try starting
            self._exiting = False
            return

        self.pid = os.getpid()

    def stop(self, flush=True):
        if self._exiting:
            return

        self._exiting = True

        try:
            atexit.unregister(self.stop)
        except AttributeError:  # pragma: no cover
            # Python 2
            try:
                atexit._exithandlers.remove((self.stop, (), {}))
            except ValueError:
                # The exit handler isn't registered
                pass

        try:
            if self.pusher is not None and not self.pusher.closed:
                if flush is True:
                    # Give it 1.5 seconds to flush any messages in it's queue
                    self.pusher.close(1500)
                else:
                    self.pusher.close()
                self.pusher = None
            if self.context is not None and not self.context.closed:
                self.context.term()
                self.context = None
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
            self.context = self.pusher = self.pid = None

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
        if self.pusher is None:
            sys.stderr.write(
                "Not sending log message over the wire because "
                "we were unable to connect to the log server.\n"
            )
            sys.stderr.flush()
            return
        try:
            msg = self.prepare(record)
            if msg:
                self.pusher.send(msg)
        except (  # pragma: no cover pylint: disable=try-except-raise
            SystemExit,
            KeyboardInterrupt,
        ):
            # Catch and raise SystemExit and KeyboardInterrupt so that we can handle
            # all other exception below
            raise
        except Exception:  # pragma: no cover pylint: disable=broad-except
            self.handleError(record)

    def close(self):
        """
        Tidy up any resources used by the handler.
        """
        # The logging machinery has asked to stop this handler
        self.stop()
        # self._exiting should already be True, nonetheless, we set it here
        # too to ensure the handler doesn't get a chance to restart itself
        self._exiting = True
        super().close()
