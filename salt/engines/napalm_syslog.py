# -*- coding: utf-8 -*-
'''
NAPALM syslog engine
====================

.. versionadded:: Nitrogen

An engine that takes syslog messages structured in
OpenConfig_ or IETF format
and fires Salt events.

.. _OpenConfig: http://www.openconfig.net/

As there can be many messages pushed into the event bus,
the user is able to filter based on the object structure.

Requirements
------------

- `napalm-logs`_

.. _`napalm-logs`: https://github.com/napalm-automation/napalm-logs

This engine transfers objects from the napalm-logs library
into the event bus. The top dictionary has the following keys:

- ``ip``
- ``host``
- ``timestamp``
- ``os``: the network OS identified
- ``model_name``: the OpenConfig or IETF model name
- ``error``: the error name (consult the documentation)
- ``message_details``: details extracted from the syslog message
- ``open_config``: the OpenConfig model

The napalm-logs transfers the messages via widely used transport
mechanisms such as: ZeroMQ (default), Kafka, etc.

The user can select the right transport using the ``transport``
option in the configuration. The

:configuration: Example configuration

    .. code-block:: yaml

        engines:
          - napalm_syslog:
                transport: zmq
                address: 1.2.3.4
                port: 49018

Output object example:

.. code-block:: json

    {
      "error": "BGP_PREFIX_THRESH_EXCEEDED",
      "ip": "127.0.0.1",
      "host": "re0.edge01.bjm01",
      "message_details": {
        "processId": "2902",
        "error": "BGP_PREFIX_THRESH_EXCEEDED",
        "pri": "149",
        "processName": "rpd",
        "host": "re0.edge01.bjm01",
        "time": "12:45:19",
        "date": "Mar 30",
        "message": "1.2.3.4 (External AS 15169): Configured maximum prefix-limit threshold(160) exceeded for inet-unicast nlri: 181 (instance master)"
      },
      "model_name": "openconfig_bgp",
      "open_config": {
        "bgp": {
          "neighbors": {
            "neighbor": {
              "1.2.3.4": {
                "neighbor-address": "1.2.3.4",
                "state": {
                  "peer-as": 15169
                },
                "afi-safis": {
                  "afi-safi": {
                    "inet": {
                      "state": {
                        "prefixes": {
                          "received": 181
                        }
                      },
                      "ipv4-unicast": {
                        "prefix-limit": {
                          "state": {
                            "max-prefixes": 160
                          }
                        }
                      },
                      "afi-safi-name": "inet"
                    }
                  }
                }
              }
            }
          }
        }
      },
      "os": "junos",
      "timestamp": "1490877919"
    }


'''
from __future__ import absolute_import

# Import python stdlib
import logging

# Import third party libraries
try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

try:
    # pylint: disable=W0611
    import napalm_logs
    import napalm_logs.utils
    # pylint: enable=W0611
    HAS_NAPALM_LOGS = True
except ImportError:
    HAS_NAPALM_LOGS = False

# Import salt libs
from salt.utils import event

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

log = logging.getLogger(__name__)
__virtualname__ = 'napalm_syslog'

# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    Load only if napalm-logs is installed.
    '''
    if not HAS_NAPALM_LOGS or not HAS_ZMQ:
        return (False, 'napalm_syslog could not be loaded. \
            Please install napalm-logs library amd ZeroMQ.')
    return True


def _zmq(address, port):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect('tcp://{addr}:{port}'.format(
        addr=address,
        port=port)
    )
    socket.setsockopt(zmq.SUBSCRIBE, '')
    return socket.recv


def _get_transport_recv(name='zmq',
                        address='0.0.0.0',
                        port=49017):
    if name not in TRANSPORT_FUN_MAP:
        log.error('Invalid transport: {0}. Falling back to ZeroMQ.'.format(name))
        name = 'zmq'
    return TRANSPORT_FUN_MAP[name](address, port)


TRANSPORT_FUN_MAP = {
    'zmq': _zmq,
    'zeromq': _zmq
}

# ----------------------------------------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------------------------------------


def start(transport='zmq',
          address='0.0.0.0',
          port=49017,
          auth_address='0.0.0.0',
          auth_port=49018,
          disable_security=False,
          certificate=None):
    '''
    Listen to napalm-logs and publish events into the Salt event bus.

    transport: ``zmq``
        Choose the desired transport.

        .. note::
            Currently ``zmq`` is the only valid option.

    address: ``0.0.0.0``
        The address of the publisher.

    port: ``49017``
        The port of the publisher.

    auth_address: ``0.0.0.0``
        The address used for authentication
        when security is not disabled.

    auth_port: ``49018``
        Port used for authentication.

    disable_security: ``False``
        Trust unencrypted messages.
        Strongly discouraged in production.

    certificate
        Absolute path to the SSL certificate.
    '''
    if not disable_security:
        priv_key, verify_key = napalm_logs.utils.authenticate(certificate,
                                                              address=auth_address,
                                                              port=auth_port)
    transport_recv_fun = _get_transport_recv(name=transport,
                                             address=address,
                                             port=port)
    if not transport_recv_fun:
        log.critical('Unable to start the engine', exc_info=True)
        return
    master = False
    if __opts__['__role'] == 'master':
        master = True
    while True:
        log.debug('Waiting for napalm-logs to send anything...')
        raw_object = transport_recv_fun()
        log.debug('Received from napalm-logs:')
        log.debug(raw_object)
        if not disable_security:
            dict_object = napalm_logs.utils.decrypt(raw_object, verify_key, priv_key)
        else:
            dict_object = napalm_logs.utils.unserialize(raw_object)
        try:
            tag = 'napalm/syslog/{os}/{error}/{host}'.format(
                os=dict_object['os'],
                error=dict_object['error'],
                host=(dict_object.get('host') or dict_object.get('ip'))
            )
        except KeyError as kerr:
            log.warning('Missing keys from the napalm-logs object:', exc_info=True)
            log.warning(dict_object)
        log.debug('Sending event {0}'.format(tag))
        log.debug(raw_object)
        if master:
            event.get_master_event(__opts__,
                                   __opts__['sock_dir']
                                   ).fire_event(dict_object, tag)
        else:
            __salt__['event.send'](tag, dict_object)
