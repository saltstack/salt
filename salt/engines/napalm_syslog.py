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

:configuration: Configuration example, excluding messages from iosxr devices:

    .. code-block:: yaml

        engines:
          - napalm_syslog:
              transport: kafka
              address: 1.2.3.4
              port: 49018
              os_blacklist:
                - iosxr

Event example:

.. code-block:: json

    napalm/syslog/junos/BGP_PREFIX_THRESH_EXCEEDED/vmx01    {
        "_stamp": "2017-05-26T10:03:18.653045",
        "error": "BGP_PREFIX_THRESH_EXCEEDED",
        "host": "vmx01",
        "ip": "192.168.140.252",
        "message_details": {
            "date": "May 25",
            "host": "vmx01",
            "message": "192.168.140.254 (External AS 65001): Configured maximum prefix-limit threshold(22) exceeded for inet-unicast nlri: 28 (instance master)",
            "pri": "28",
            "processId": "2957",
            "processName": "rpd",
            "tag": "BGP_PREFIX_THRESH_EXCEEDED",
            "time": "20:50:41"
        },
        "model_name": "openconfig_bgp",
        "open_config": {
            "bgp": {
                "neighbors": {
                    "neighbor": {
                        "192.168.140.254": {
                            "afi_safis": {
                                "afi_safi": {
                                    "inet": {
                                        "afi_safi_name": "inet",
                                        "ipv4_unicast": {
                                            "prefix_limit": {
                                                "state": {
                                                    "max_prefixes": 22
                                                }
                                            }
                                        },
                                        "state": {
                                            "prefixes": {
                                                "received": 28
                                            }
                                        }
                                    }
                                }
                            },
                            "neighbor_address": "192.168.140.254",
                            "state": {
                                "peer_as": 65001
                            }
                        }
                    }
                }
            }
        },
        "os": "junos",
        "timestamp": "1495741841"
    }

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
import salt.utils
import salt.utils.network
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


def _zmq(address, port, **kwargs):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    if salt.utils.network.is_ipv6(address):
        socket.ipv6 = True
    socket.connect('tcp://{addr}:{port}'.format(
        addr=address,
        port=port)
    )
    socket.setsockopt(zmq.SUBSCRIBE, '')
    return socket.recv


def _get_transport_recv(name='zmq',
                        address='0.0.0.0',
                        port=49017,
                        **kwargs):
    if name not in TRANSPORT_FUN_MAP:
        log.error('Invalid transport: {0}. Falling back to ZeroMQ.'.format(name))
        name = 'zmq'
    return TRANSPORT_FUN_MAP[name](address, port, **kwargs)


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
          certificate=None,
          os_whitelist=None,
          os_blacklist=None,
          error_whitelist=None,
          error_blacklist=None,
          host_whitelist=None,
          host_blacklist=None):
    '''
    Listen to napalm-logs and publish events into the Salt event bus.

    transport: ``zmq``
        Choose the desired transport.

        .. note::
            Currently ``zmq`` is the only valid option.

    address: ``0.0.0.0``
        The address of the publisher, as configured on napalm-logs.

    port: ``49017``
        The port of the publisher, , as configured on napalm-logs.

    auth_address: ``0.0.0.0``
        The address used for authentication
        when security is not disabled.

    auth_port: ``49018``
        Port used for authentication.

    disable_security: ``False``
        Trust unencrypted messages.
        Strongly discouraged in production.

    certificate: ``None``
        Absolute path to the SSL certificate.

    os_whitelist: ``None``
        List of operating systems allowed. By default everything is allowed.

    os_blacklist: ``None``
        List of operating system to be ignored. Nothing ignored by default.

    error_whitelist: ``None``
        List of errors allowed.

    error_blacklist: ``None``
        List of errors ignored.

    host_whitelist: ``None``
        List of hosts or IPs to be allowed.

    host_blacklist: ``None``
        List of hosts of IPs to be ignored.
    '''
    if not disable_security:
        if not certificate:
            log.critical('Please use a certificate, or disable the security.')
            return
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
            event_os = dict_object['os']
            if os_blacklist or os_whitelist:
                valid_os = salt.utils.check_whitelist_blacklist(event_os,
                                                                whitelist=os_whitelist,
                                                                blacklist=os_blacklist)
                if not valid_os:
                    log.info('Ignoring NOS {} as per whitelist/blacklist'.format(event_os))
                    continue
            event_error = dict_object['error']
            if error_blacklist or error_whitelist:
                valid_error = salt.utils.check_whitelist_blacklist(event_error,
                                                                   whitelist=error_whitelist,
                                                                   blacklist=error_blacklist)
                if not valid_error:
                    log.info('Ignoring error {} as per whitelist/blacklist'.format(event_error))
                    continue
            event_host = dict_object.get('host') or dict_object.get('ip')
            if host_blacklist or host_whitelist:
                valid_host = salt.utils.check_whitelist_blacklist(event_host,
                                                                  whitelist=host_whitelist,
                                                                  blacklist=host_blacklist)
                if not valid_host:
                    log.info('Ignoring messages from {} as per whitelist/blacklist'.format(event_host))
                    continue
            tag = 'napalm/syslog/{os}/{error}/{host}'.format(
                os=event_os,
                error=event_error,
                host=event_host
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
