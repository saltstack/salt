# -*- coding: utf-8 -*-
'''
Returns event data for state execution only using a tcp socket, this method of
returning data can be used for Splunk.

State events are split out by state name.

It is strongly recommended to use the ``event_return_whitelist`` so not all
events are returned, for example:

..code-block:: yaml

   event_return_whitelist:
      - salt/job/*/ret/*

.. versionadded:: Boron

Add the following to the master configuration file:

..code-block:: yaml

   returner.tcp_return.host:<recieving server ip>
   returner.tcp_return.port: <listening port>

For events return set the event_return to tcp_return

This is NOT a job cache returner, it was designed to send events to a Splunk
server.

'''

from __future__ import absolute_import

# Import python libs
import json
import socket
import logging

# Import Salt libs
import salt.utils.jid
import salt.returners

log = logging.getLogger(__name__)

# Define virtual name
__virtualname__ = 'tcp_return'


def __virtual__():
    return __virtualname__


def _get_options(ret=None):
    attrs = {'host': 'host',
             'port': 'port'}
    _options = salt.returners.get_returner_options('returner.{0}'.format
                                                   (__virtualname__),
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def _return_states(connection, data, host, port):
    if data.get('fun') == 'state.sls' or data.get('fun') == 'state.highstate':
        for state_name, state in data.get('return').iteritems():
            # Add extra data to state event
            state.update({'state_name': state_name,
                          'state_id': state_name.split('_|-')[1],
                          'minion_id': data.get('id'),
                          'jid': data.get('jid'),
                          'event_type': 'state_return'})
            log.debug('Sending event_return using {0} returner. Settings, '
                      'TCP_IP: {1}, '
                      'TCP_PORT: {2}. '
                      'Data: {3}'.format(__virtualname__, host, port, state))
            connection.send(json.dumps(state))


def event_return(events):
    _options = _get_options()
    host = _options.get('host')
    port = _options.get('port')
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection.connect((host, port))
    for event in events:
        data = event.get('data', {})
        _return_states(connection, data, host, port)
    connection.shutdown(socket.SHUT_RDWR)
    connection.close()
