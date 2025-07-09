"""
    Fluent Logging Handler
    ======================

    .. versionadded:: 2015.8.0

    This module provides some fluentd_ logging handlers.


    Fluent Logging Handler
    ----------------------

    In the `fluent` configuration file:

    .. code-block:: text

        <source>
          type forward
          bind localhost
          port 24224
        </source>

    Then, to send logs via fluent in Logstash format, add the
    following to the salt (master and/or minion) configuration file:

    .. code-block:: yaml

        fluent_handler:
          host: localhost
          port: 24224

    To send logs via fluent in the Graylog raw json format, add the
    following to the salt (master and/or minion) configuration file:

    .. code-block:: yaml

        fluent_handler:
          host: localhost
          port: 24224
          payload_type: graylog
          tags:
          - salt_master.SALT

    The above also illustrates the `tags` option, which allows
    one to set descriptive (or useful) tags on records being
    sent.  If not provided, this defaults to the single tag:
    'salt'.  Also note that, via Graylog "magic", the 'facility'
    of the logged message is set to 'SALT' (the portion of the
    tag after the first period), while the tag itself will be
    set to simply 'salt_master'.  This is a feature, not a bug :)

    Note:
    There is a third emitter, for the GELF format, but it is
    largely untested, and I don't currently have a setup supporting
    this config, so while it runs cleanly and outputs what LOOKS to
    be valid GELF, any real-world feedback on its usefulness, and
    correctness, will be appreciated.

    Log Level
    .........

    The ``fluent_handler`` configuration section accepts an additional setting
    ``log_level``. If not set, the logging level used will be the one defined
    for ``log_level`` in the global configuration file section.

    .. admonition:: Inspiration

        This work was inspired in `fluent-logger-python`_

    .. _fluentd: http://www.fluentd.org
    .. _`fluent-logger-python`: https://github.com/fluent/fluent-logger-python

"""

import datetime
import logging
import logging.handlers
import socket
import threading
import time

import salt.utils.msgpack
import salt.utils.network
from salt._logging import LOG_LEVELS

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = "fluent"

_global_sender = None

# Python logger's idea of "level" is wildly at variance with
# Graylog's (and, incidentally, the rest of the civilized world).
syslog_levels = {
    "EMERG": 0,
    "ALERT": 2,
    "CRIT": 2,
    "ERR": 3,
    "WARNING": 4,
    "NOTICE": 5,
    "INFO": 6,
    "DEBUG": 7,
}


def setup(tag, **kwargs):
    host = kwargs.get("host", "localhost")
    port = kwargs.get("port", 24224)

    global _global_sender
    _global_sender = FluentSender(tag, host=host, port=port)


def get_global_sender():
    return _global_sender


def __virtual__():
    if not any(["fluent_handler" in __opts__]):
        log.trace(
            "The required configuration section, 'fluent_handler', "
            "was not found the in the configuration. Not loading the fluent "
            "logging handlers module."
        )
        return False
    return __virtualname__


def setup_handlers():
    host = port = None

    if "fluent_handler" in __opts__:
        host = __opts__["fluent_handler"].get("host", None)
        port = __opts__["fluent_handler"].get("port", None)
        payload_type = __opts__["fluent_handler"].get("payload_type", None)
        # in general, you want the value of tag to ALSO be a member of tags
        tags = __opts__["fluent_handler"].get("tags", ["salt"])
        tag = tags[0] if tags else "salt"
        if payload_type == "graylog":
            version = 0
        elif payload_type == "gelf":
            # We only support version 1.1 (the latest) of GELF...
            version = 1.1
        else:
            # Default to logstash for backwards compat
            payload_type = "logstash"
            version = __opts__["fluent_handler"].get("version", 1)

        if host is None and port is None:
            log.debug(
                "The required 'fluent_handler' configuration keys, "
                "'host' and/or 'port', are not properly configured. Not "
                "enabling the fluent logging handler."
            )
        else:
            formatter = MessageFormatter(
                payload_type=payload_type, version=version, tags=tags
            )
            fluent_handler = FluentHandler(tag, host=host, port=port)
            fluent_handler.setFormatter(formatter)
            fluent_handler.setLevel(
                LOG_LEVELS[
                    __opts__["fluent_handler"].get(
                        "log_level", __opts__.get("log_level", "error")
                    )
                ]
            )
            yield fluent_handler

    if host is None and port is None:
        yield False


class MessageFormatter(logging.Formatter):
    def __init__(self, payload_type, version, tags, msg_type=None, msg_path=None):
        self.payload_type = payload_type
        self.version = version
        self.tag = tags[0] if tags else "salt"  # 'salt' for backwards compat
        self.tags = tags
        self.msg_path = msg_path if msg_path else payload_type
        self.msg_type = msg_type if msg_type else payload_type
        format_func = f"format_{payload_type}_v{version}".replace(".", "_")
        self.format = getattr(self, format_func)
        super().__init__(fmt=None, datefmt=None)

    def formatTime(self, record, datefmt=None):
        if self.payload_type == "gelf":  # GELF uses epoch times
            return record.created
        return datetime.datetime.utcfromtimestamp(record.created).isoformat()[:-3] + "Z"

    def format_graylog_v0(self, record):
        """
        Graylog 'raw' format is essentially the raw record, minimally munged to provide
        the bare minimum that td-agent requires to accept and route the event.  This is
        well suited to a config where the client td-agents log directly to Graylog.
        """
        message_dict = {
            "message": record.getMessage(),
            "timestamp": self.formatTime(record),
            # Graylog uses syslog levels, not whatever it is Python does...
            "level": syslog_levels.get(record.levelname, "ALERT"),
            "tag": self.tag,
        }

        if record.exc_info:
            exc_info = self.formatException(record.exc_info)
            message_dict.update({"full_message": exc_info})

        # Add any extra attributes to the message field
        for key, value in record.__dict__.items():
            if key in (
                "args",
                "asctime",
                "bracketlevel",
                "bracketname",
                "bracketprocess",
                "created",
                "exc_info",
                "exc_text",
                "id",
                "levelname",
                "levelno",
                "msecs",
                "msecs",
                "message",
                "msg",
                "relativeCreated",
                "version",
            ):
                # These are already handled above or explicitly pruned.
                continue

            if value is None or isinstance(value, (str, bool, dict, float, int, list)):
                val = value
            else:
                val = repr(value)
            message_dict.update({f"{key}": val})
        return message_dict

    def format_gelf_v1_1(self, record):
        """
        If your agent is (or can be) configured to forward pre-formed GELF to Graylog
        with ZERO fluent processing, this function is for YOU, pal...
        """
        message_dict = {
            "version": self.version,
            "host": salt.utils.network.get_fqhostname(),
            "short_message": record.getMessage(),
            "timestamp": self.formatTime(record),
            "level": syslog_levels.get(record.levelname, "ALERT"),
            "_tag": self.tag,
        }

        if record.exc_info:
            exc_info = self.formatException(record.exc_info)
            message_dict.update({"full_message": exc_info})

        # Add any extra attributes to the message field
        for key, value in record.__dict__.items():
            if key in (
                "args",
                "asctime",
                "bracketlevel",
                "bracketname",
                "bracketprocess",
                "created",
                "exc_info",
                "exc_text",
                "id",
                "levelname",
                "levelno",
                "msecs",
                "msecs",
                "message",
                "msg",
                "relativeCreated",
                "version",
            ):
                # These are already handled above or explicitly avoided.
                continue

            if value is None or isinstance(value, (str, bool, dict, float, int, list)):
                val = value
            else:
                val = repr(value)
            # GELF spec require "non-standard" fields to be prefixed with '_' (underscore).
            message_dict.update({f"_{key}": val})

        return message_dict

    def format_logstash_v0(self, record):
        """
        Messages are formatted in logstash's expected format.
        """
        host = salt.utils.network.get_fqhostname()
        message_dict = {
            "@timestamp": self.formatTime(record),
            "@fields": {
                "levelname": record.levelname,
                "logger": record.name,
                "lineno": record.lineno,
                "pathname": record.pathname,
                "process": record.process,
                "threadName": record.threadName,
                "funcName": record.funcName,
                "processName": record.processName,
            },
            "@message": record.getMessage(),
            "@source": f"{self.msg_type}://{host}/{self.msg_path}",
            "@source_host": host,
            "@source_path": self.msg_path,
            "@tags": self.tags,
            "@type": self.msg_type,
        }

        if record.exc_info:
            message_dict["@fields"]["exc_info"] = self.formatException(record.exc_info)

        # Add any extra attributes to the message field
        for key, value in record.__dict__.items():
            if key in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "id",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
            ):
                # These are already handled above or not handled at all
                continue

            if value is None:
                message_dict["@fields"][key] = value
                continue

            if isinstance(value, (str, bool, dict, float, int, list)):
                message_dict["@fields"][key] = value
                continue

            message_dict["@fields"][key] = repr(value)
        return message_dict

    def format_logstash_v1(self, record):
        """
        Messages are formatted in logstash's expected format.
        """
        message_dict = {
            "@version": 1,
            "@timestamp": self.formatTime(record),
            "host": salt.utils.network.get_fqhostname(),
            "levelname": record.levelname,
            "logger": record.name,
            "lineno": record.lineno,
            "pathname": record.pathname,
            "process": record.process,
            "threadName": record.threadName,
            "funcName": record.funcName,
            "processName": record.processName,
            "message": record.getMessage(),
            "tags": self.tags,
            "type": self.msg_type,
        }

        if record.exc_info:
            message_dict["exc_info"] = self.formatException(record.exc_info)

        # Add any extra attributes to the message field
        for key, value in record.__dict__.items():
            if key in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "id",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
            ):
                # These are already handled above or not handled at all
                continue

            if value is None:
                message_dict[key] = value
                continue

            if isinstance(value, (str, bool, dict, float, int, list)):
                message_dict[key] = value
                continue

            message_dict[key] = repr(value)
        return message_dict


class FluentHandler(logging.Handler):
    """
    Logging Handler for fluent.
    """

    def __init__(self, tag, host="localhost", port=24224, timeout=3.0, verbose=False):

        self.tag = tag
        self.sender = FluentSender(
            tag, host=host, port=port, timeout=timeout, verbose=verbose
        )
        logging.Handler.__init__(self)

    def emit(self, record):
        data = self.format(record)
        self.sender.emit(None, data)

    def close(self):
        self.acquire()
        try:
            self.sender._close()
            logging.Handler.close(self)
        finally:
            self.release()


class FluentSender:
    def __init__(
        self,
        tag,
        host="localhost",
        port=24224,
        bufmax=1 * 1024 * 1024,
        timeout=3.0,
        verbose=False,
    ):

        self.tag = tag
        self.host = host
        self.port = port
        self.bufmax = bufmax
        self.timeout = timeout
        self.verbose = verbose

        self.socket = None
        self.pendings = None
        self.lock = threading.Lock()

        try:
            self._reconnect()
        except Exception:  # pylint: disable=broad-except
            # will be retried in emit()
            self._close()

    def emit(self, label, data):
        cur_time = int(time.time())
        self.emit_with_time(label, cur_time, data)

    def emit_with_time(self, label, timestamp, data):
        bytes_ = self._make_packet(label, timestamp, data)
        self._send(bytes_)

    def _make_packet(self, label, timestamp, data):
        if label:
            tag = ".".join((self.tag, label))
        else:
            tag = self.tag
        packet = (tag, timestamp, data)
        if self.verbose:
            print(packet)
        return salt.utils.msgpack.packb(packet)

    def _send(self, bytes_):
        self.lock.acquire()
        try:
            self._send_internal(bytes_)
        finally:
            self.lock.release()

    def _send_internal(self, bytes_):
        # buffering
        if self.pendings:
            self.pendings += bytes_
            bytes_ = self.pendings

        try:
            # reconnect if possible
            self._reconnect()

            # send message
            self.socket.sendall(bytes_)

            # send finished
            self.pendings = None
        except Exception:  # pylint: disable=broad-except
            # close socket
            self._close()
            # clear buffer if it exceeds max bufer size
            if self.pendings and (len(self.pendings) > self.bufmax):
                # TODO: add callback handler here
                self.pendings = None
            else:
                self.pendings = bytes_

    def _reconnect(self):
        if not self.socket:
            if self.host.startswith("unix://"):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect(self.host[len("unix://") :])
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
            self.socket = sock

    def _close(self):
        if self.socket:
            self.socket.close()
        self.socket = None
