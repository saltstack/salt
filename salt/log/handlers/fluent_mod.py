# -*- coding: utf-8 -*-
'''
    Fluent Logging Handler
    ========================

    .. versionadded:: 2015.8.0

    This module provides some `Fluent`_ logging handlers.


    Fluent Logging Handler
    -------------------

    In the salt configuration file:

    .. code-block:: yaml

        fluent_handler:
          host: localhost
          port: 24224

    In the `fluent`_ configuration file:

    .. code-block:: text

        <source>
          type forward
          port 24224
        </source>

    Log Level
    .........

    The ``fluent_handler``
    configuration section accepts an additional setting ``log_level``. If not
    set, the logging level used will be the one defined for ``log_level`` in
    the global configuration file section.

    .. admonition:: Inspiration

        This work was inspired in `fluent-logger-python`_

    .. _`fluentd`: http://www.fluentd.org
    .. _`fluent-logger-python`: https://github.com/fluent/fluent-logger-python

'''

# Import python libs
from __future__ import absolute_import, print_function
import logging
import logging.handlers
import time
import datetime
import socket
import threading


# Import salt libs
from salt.log.setup import LOG_LEVELS
from salt.log.mixins import NewStyleClassMixIn
import salt.utils.network

# Import Third party libs
import salt.ext.six as six
try:
    import simplejson as json
except ImportError:
    import json

log = logging.getLogger(__name__)

try:
    # Attempt to import msgpack
    import msgpack
    # There is a serialization issue on ARM and potentially other platforms
    # for some msgpack bindings, check for it
    if msgpack.loads(msgpack.dumps([1, 2, 3]), use_list=True) is None:
        raise ImportError
except ImportError:
    # Fall back to msgpack_pure
    try:
        import msgpack_pure as msgpack
    except ImportError:
        # TODO: Come up with a sane way to get a configured logfile
        #       and write to the logfile when this error is hit also
        LOG_FORMAT = '[%(levelname)-8s] %(message)s'
        salt.log.setup_console_logger(log_format=LOG_FORMAT)
        log.fatal('Unable to import msgpack or msgpack_pure python modules')
        # Don't exit if msgpack is not available, this is to make local mode
        # work without msgpack
        #sys.exit(salt.exitcodes.EX_GENERIC)

# Define the module's virtual name
__virtualname__ = 'fluent'

_global_sender = None


def setup(tag, **kwargs):
    host = kwargs.get('host', 'localhost')
    port = kwargs.get('port', 24224)

    global _global_sender
    _global_sender = FluentSender(tag, host=host, port=port)


def get_global_sender():
    return _global_sender


def __virtual__():
    if not any(['fluent_handler' in __opts__]):
        log.trace(
            'The required configuration section, \'fluent_handler\', '
            'was not found the in the configuration. Not loading the fluent '
            'logging handlers module.'
        )
        return False
    return __virtualname__


def setup_handlers():
    host = port = address = None

    if 'fluent_handler' in __opts__:
        host = __opts__['fluent_handler'].get('host', None)
        port = __opts__['fluent_handler'].get('port', None)
        version = __opts__['fluent_handler'].get('version', 1)

        if host is None and port is None:
            log.debug(
                'The required \'fluent_handler\' configuration keys, '
                '\'host\' and/or \'port\', are not properly configured. Not '
                'configuring the fluent logging handler.'
            )
        else:
            logstash_formatter = LogstashFormatter(version=version)
            fluent_handler = FluentHandler('salt', host=host, port=port)
            fluent_handler.setFormatter(logstash_formatter)
            fluent_handler.setLevel(
                LOG_LEVELS[
                    __opts__['fluent_handler'].get(
                        'log_level',
                        # Not set? Get the main salt log_level setting on the
                        # configuration file
                        __opts__.get(
                            'log_level',
                            # Also not set?! Default to 'error'
                            'error'
                        )
                    )
                ]
            )
            yield fluent_handler

    if host is None and port is None and address is None:
        yield False


class LogstashFormatter(logging.Formatter, NewStyleClassMixIn):
    def __init__(self, msg_type='logstash', msg_path='logstash', version=1):
        self.msg_path = msg_path
        self.msg_type = msg_type
        self.version = version
        self.format = getattr(self, 'format_v{0}'.format(version))
        super(LogstashFormatter, self).__init__(fmt=None, datefmt=None)

    def formatTime(self, record, datefmt=None):
        return datetime.datetime.utcfromtimestamp(record.created).isoformat()[:-3] + 'Z'

    def format_v0(self, record):
        host = salt.utils.network.get_fqhostname()
        message_dict = {
            '@timestamp': self.formatTime(record),
            '@fields': {
                'levelname': record.levelname,
                'logger': record.name,
                'lineno': record.lineno,
                'pathname': record.pathname,
                'process': record.process,
                'threadName': record.threadName,
                'funcName': record.funcName,
                'processName': record.processName
            },
            '@message': record.getMessage(),
            '@source': '{0}://{1}/{2}'.format(
                self.msg_type,
                host,
                self.msg_path
            ),
            '@source_host': host,
            '@source_path': self.msg_path,
            '@tags': ['salt'],
            '@type': self.msg_type,
        }

        if record.exc_info:
            message_dict['@fields']['exc_info'] = self.formatException(
                record.exc_info
            )

        # Add any extra attributes to the message field
        for key, value in six.iteritems(record.__dict__):
            if key in ('args', 'asctime', 'created', 'exc_info', 'exc_text',
                       'filename', 'funcName', 'id', 'levelname', 'levelno',
                       'lineno', 'module', 'msecs', 'msecs', 'message', 'msg',
                       'name', 'pathname', 'process', 'processName',
                       'relativeCreated', 'thread', 'threadName'):
                # These are already handled above or not handled at all
                continue

            if value is None:
                message_dict['@fields'][key] = value
                continue

            if isinstance(value, (six.string_types, bool, dict, float, int, list)):
                message_dict['@fields'][key] = value
                continue

            message_dict['@fields'][key] = repr(value)
        return json.dumps(message_dict)

    def format_v1(self, record):
        message_dict = {
            '@version': 1,
            '@timestamp': self.formatTime(record),
            'host': salt.utils.network.get_fqhostname(),
            'levelname': record.levelname,
            'logger': record.name,
            'lineno': record.lineno,
            'pathname': record.pathname,
            'process': record.process,
            'threadName': record.threadName,
            'funcName': record.funcName,
            'processName': record.processName,
            'message': record.getMessage(),
            'tags': ['salt'],
            'type': self.msg_type
        }

        if record.exc_info:
            message_dict['exc_info'] = self.formatException(
                record.exc_info
            )

        # Add any extra attributes to the message field
        for key, value in six.iteritems(record.__dict__):
            if key in ('args', 'asctime', 'created', 'exc_info', 'exc_text',
                       'filename', 'funcName', 'id', 'levelname', 'levelno',
                       'lineno', 'module', 'msecs', 'msecs', 'message', 'msg',
                       'name', 'pathname', 'process', 'processName',
                       'relativeCreated', 'thread', 'threadName'):
                # These are already handled above or not handled at all
                continue

            if value is None:
                message_dict[key] = value
                continue

            if isinstance(value, (six.string_types, bool, dict, float, int, list)):
                message_dict[key] = value
                continue

            message_dict[key] = repr(value)
        return json.dumps(message_dict)


class FluentHandler(logging.Handler):
    '''
    Logging Handler for fluent.
    '''
    def __init__(self,
                 tag,
                 host='localhost',
                 port=24224,
                 timeout=3.0,
                 verbose=False):

        self.tag = tag
        self.sender = FluentSender(tag,
                                   host=host, port=port,
                                   timeout=timeout, verbose=verbose)
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


class FluentSender(object):
    def __init__(self,
                 tag,
                 host='localhost',
                 port=24224,
                 bufmax=1 * 1024 * 1024,
                 timeout=3.0,
                 verbose=False):

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
        except Exception:
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
            tag = '.'.join((self.tag, label))
        else:
            tag = self.tag
        packet = (tag, timestamp, data)
        if self.verbose:
            print(packet)
        return msgpack.packb(packet)

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
        except Exception:
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
            if self.host.startswith('unix://'):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect(self.host[len('unix://'):])
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
            self.socket = sock

    def _close(self):
        if self.socket:
            self.socket.close()
        self.socket = None
