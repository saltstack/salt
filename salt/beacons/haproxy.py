# -*- coding: utf-8 -*-
'''
Watch current connections of haproxy server backends.
Fire an event when over a specified threshold.

.. versionadded:: 2016.11.0
'''

# Import Python libs
from __future__ import absolute_import
import logging
from salt.ext.six.moves import map

log = logging.getLogger(__name__)

__virtualname__ = 'haproxy'


def __virtual__():
    '''
    Only load the module if haproxyctl module is installed
    '''
    if 'haproxy.get_sessions' in __salt__:
        return __virtualname__
    else:
        return False


def validate(config):
    '''
    Validate the beacon configuration
    '''
    if not isinstance(config, list):
        return False, ('Configuration for haproxy beacon must '
                       'be a list.')

    _config = {}
    list(map(_config.update, config))

    # Look for servers list
    _servers_found = False
    for config_item in config:
        for x in config_item:
            if isinstance(config_item[x], dict) and \
               'servers' in config_item[x]:
                if isinstance(config_item[x]['servers'], list):
                    _servers_found = True

    if not _servers_found:
        return False, ('Configuration for haproxy beacon requires a list '
                       'of backends and servers')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Check if current number of sessions of a server for a specific haproxy backend
    is over a defined threshold.

    .. code-block:: yaml

        beacons:
          haproxy:
            - www-backend:
                threshold: 45
                servers:
                  - web1
                  - web2
            - interval: 120
    '''
    log.debug('haproxy beacon starting')

    ret = []
    for backend_config in config:

        backend = backend_config.keys()[0]

        threshold = backend_config[backend]['threshold']
        for server in backend_config[backend]['servers']:
            scur = __salt__['haproxy.get_sessions'](server, backend)
            if scur:
                if int(scur) > int(threshold):
                    _server = {'server': server,
                               'scur': scur,
                               'threshold': threshold,
                               }
                    log.debug('Emit because {0} > {1}'
                              ' for {2} in {3}'.format(scur,
                                                       threshold,
                                                       server,
                                                       backend))
                    ret.append(_server)
    return ret
