# -*- coding: utf-8 -*-
'''
    Logstash Logging Handler
    ========================

    .. versionadded:: 0.17.0

    This module provides some `Logstash`_ logging handlers.


    UDP Logging Handler
    -------------------

    For versions of `Logstash`_ before 1.2.0:

    In the salt configuration file:

    .. code-block:: yaml

        logstash_udp_handler:
          host: 127.0.0.1
          port: 9999
          version: 0

    In the `Logstash`_ configuration file:

    .. code-block:: text

        input {
          udp {
            type => "udp-type"
            format => "json_event"
          }
        }

    For version 1.2.0 of `Logstash`_ and newer:

    In the salt configuration file:

    .. code-block:: yaml

        logstash_udp_handler:
          host: 127.0.0.1
          port: 9999
          version: 1

    In the `Logstash`_ configuration file:

    .. code-block:: text

        input {
          udp {
            port => 9999
            codec => json
          }
        }

    Please read the `UDP input`_ configuration page for additional information.


    ZeroMQ Logging Handler
    ----------------------

    For versions of `Logstash`_ before 1.2.0:

    In the salt configuration file:

    .. code-block:: yaml

        logstash_zmq_handler:
          address: tcp://127.0.0.1:2021
          version: 0

    In the `Logstash`_ configuration file:

    .. code-block:: text

        input {
          zeromq {
            type => "zeromq-type"
            mode => "server"
            topology => "pubsub"
            address => "tcp://0.0.0.0:2021"
            charset => "UTF-8"
            format => "json_event"
          }
        }

    For version 1.2.0 of `Logstash`_ and newer:

    In the salt configuration file:

    .. code-block:: yaml

        logstash_zmq_handler:
          address: tcp://127.0.0.1:2021
          version: 1

    In the `Logstash`_ configuration file:

    .. code-block:: text

        input {
          zeromq {
            topology => "pubsub"
            address => "tcp://0.0.0.0:2021"
            codec => json
          }
        }

    Please read the `ZeroMQ input`_ configuration page for additional
    information.

    .. admonition:: Important Logstash Setting

        One of the most important settings that you should not forget on your
        `Logstash`_ configuration file regarding these logging handlers is
        ``format``.
        Both the `UDP` and `ZeroMQ` inputs need to have ``format`` as
        ``json_event`` which is what we send over the wire.


    Log Level
    .........

    Both the ``logstash_udp_handler`` and the ``logstash_zmq_handler``
    configuration sections accept an additional setting ``log_level``. If not
    set, the logging level used will be the one defined for ``log_level`` in
    the global configuration file section.

    HWM
    ...

    The `high water mark`_ for the ZMQ socket setting. Only applicable for the
    ``logstash_zmq_handler``.



    .. admonition:: Inspiration

        This work was inspired in `pylogstash`_, `python-logstash`_, `canary`_
        and the `PyZMQ logging handler`_.


    .. _`Logstash`: http://logstash.net
    .. _`canary`: https://github.com/ryanpetrello/canary
    .. _`pylogstash`: https://github.com/turtlebender/pylogstash
    .. _`python-logstash`: https://github.com/vklochan/python-logstash
    .. _`PyZMQ logging handler`: https://github.com/zeromq/pyzmq/blob/master/zmq/log/handlers.py
    .. _`UDP input`: http://logstash.net/docs/latest/inputs/udp
    .. _`ZeroMQ input`: http://logstash.net/docs/latest/inputs/zeromq
    .. _`high water mark`: http://api.zeromq.org/3-2:zmq-setsockopt

'''

# Import python libs
from __future__ import absolute_import
import os
import json
import logging
import logging.handlers
import datetime

# Import salt libs
from salt.log.setup import LOG_LEVELS
from salt.log.mixins import NewStyleClassMixIn
import salt.utils.network

# Import Third party libs
import salt.ext.six as six
try:
    import zmq
except ImportError:
    pass

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'logstash'


def __virtual__():
    if not any(['logstash_udp_handler' in __opts__,
                'logstash_zmq_handler' in __opts__]):
        log.trace(
            'None of the required configuration sections, '
            '\'logstash_udp_handler\' and \'logstash_zmq_handler\', '
            'were found the in the configuration. Not loading the Logstash '
            'logging handlers module.'
        )
        return False
    return __virtualname__


def setup_handlers():
    host = port = address = None

    if 'logstash_udp_handler' in __opts__:
        host = __opts__['logstash_udp_handler'].get('host', None)
        port = __opts__['logstash_udp_handler'].get('port', None)
        version = __opts__['logstash_udp_handler'].get('version', 0)

        if host is None and port is None:
            log.debug(
                'The required \'logstash_udp_handler\' configuration keys, '
                '\'host\' and/or \'port\', are not properly configured. Not '
                'configuring the logstash UDP logging handler.'
            )
        else:
            logstash_formatter = LogstashFormatter(version=version)
            udp_handler = DatagramLogstashHandler(host, port)
            udp_handler.setFormatter(logstash_formatter)
            udp_handler.setLevel(
                LOG_LEVELS[
                    __opts__['logstash_udp_handler'].get(
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
            yield udp_handler

    if 'logstash_zmq_handler' in __opts__:
        address = __opts__['logstash_zmq_handler'].get('address', None)
        zmq_hwm = __opts__['logstash_zmq_handler'].get('hwm', 1000)
        version = __opts__['logstash_zmq_handler'].get('version', 0)

        if address is None:
            log.debug(
                'The required \'logstash_zmq_handler\' configuration key, '
                '\'address\', is not properly configured. Not '
                'configuring the logstash ZMQ logging handler.'
            )
        else:
            logstash_formatter = LogstashFormatter(version=version)
            zmq_handler = ZMQLogstashHander(address, zmq_hwm=zmq_hwm)
            zmq_handler.setFormatter(logstash_formatter)
            zmq_handler.setLevel(
                LOG_LEVELS[
                    __opts__['logstash_zmq_handler'].get(
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
            yield zmq_handler

    if host is None and port is None and address is None:
        yield False


class LogstashFormatter(logging.Formatter, NewStyleClassMixIn):
    def __init__(self, msg_type='logstash', msg_path='logstash', version=0):
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


class DatagramLogstashHandler(logging.handlers.DatagramHandler):
    '''
    Logstash UDP logging handler.
    '''

    def makePickle(self, record):
        return self.format(record)


class ZMQLogstashHander(logging.Handler, NewStyleClassMixIn):
    '''
    Logstash ZMQ logging handler.
    '''

    def __init__(self, address, level=logging.NOTSET, zmq_hwm=1000):
        super(ZMQLogstashHander, self).__init__(level=level)
        self._context = self._publisher = None
        self._address = address
        self._zmq_hwm = zmq_hwm
        self._pid = os.getpid()

    @property
    def publisher(self):
        current_pid = os.getpid()
        if not getattr(self, '_publisher') or self._pid != current_pid:
            # We forked? Multiprocessing? Recreate!!!
            self._pid = current_pid
            self._context = zmq.Context()
            self._publisher = self._context.socket(zmq.PUB)
            # Above 1000 unsent events in the socket queue, stop dropping them
            try:
                # Above the defined high water mark(unsent messages), start
                # dropping them
                self._publisher.setsockopt(zmq.HWM, self._zmq_hwm)
            except AttributeError:
                # In ZMQ >= 3.0, there are separate send and receive HWM
                # settings
                self._publisher.setsockopt(zmq.SNDHWM, self._zmq_hwm)
                self._publisher.setsockopt(zmq.RCVHWM, self._zmq_hwm)

            self._publisher.connect(self._address)
        return self._publisher

    def emit(self, record):
        formatted_object = self.format(record)
        self.publisher.send(formatted_object)

    def close(self):
        if self._context is not None:
            # One second to send any queued messages
            if hasattr(self._context, 'destroy'):
                self._context.destroy(1 * 1000)
            else:
                if getattr(self, '_publisher', None) is not None:
                    self._publisher.setsockopt(zmq.LINGER, 1 * 1000)
                    self._publisher.close()

                if self._context.closed is False:
                    self._context.term()
