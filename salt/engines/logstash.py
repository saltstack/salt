# -*- coding: utf-8 -*-
'''
An engine that reads messages from the salt event bus and pushes
them onto a logstash endpoint.

.. versionadded: 2015.8.0

:configuration:

    Example configuration
        engines:
          - logstash:
            host: log.my_network.com
            port: 5959
            proto: tcp

:depends: logstash
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils.event

# Import third-party libs
try:
    import logstash
    HAS_LOGSTASH = True
except ImportError:
    HAS_LOGSTASH = False


def __virtual__():
    if not HAS_LOGSTASH:
        return False
    else:
        return True

log = logging.getLogger(__name__)


def start(host, port=5959, tag='salt/engine/logstash', proto='udp'):
    '''
    Listen to salt events and forward them to logstash
    '''

    if proto == 'tcp':
        logstashHandler = logstash.TCPLogstashHandler
    elif proto == 'udp':
        logstashHandler = logstash.UDPLogstashHandler

    logstash_logger = logging.getLogger('python-logstash-logger')
    logstash_logger.setLevel(logging.INFO)
    logstash_logger.addHandler(logstashHandler(host, port, version=1))

    if __opts__.get('id').endswith('_master'):
        event_bus = salt.utils.event.get_master_event(
                __opts__,
                __opts__['sock_dir'],
                listen=True)
    else:
        event_bus = salt.utils.event.get_event(
            'minion',
            transport=__opts__['transport'],
            opts=__opts__,
            sock_dir=__opts__['sock_dir'],
            listen=True)
        log.debug('Logstash engine started')

    while True:
        event = event_bus.get_event()
        if event:
            logstash_logger.info(tag, extra=event)
