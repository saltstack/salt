# -*- coding: utf-8 -*-
'''
Watch current connections of haproxy server backends.
Fire an event when over a specified threshold.

.. versionadded:: Carbon
'''

# Import Python libs
from __future__ import absolute_import
import logging


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
    if not isinstance(config, dict):
        return False, ('Configuration for haproxy beacon must be a dictionary.')
    if 'haproxy' not in config:
        return False, ('Configuration for haproxy beacon requires a list of backends and servers')
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
    _validate = validate(config)
    if not _validate:
        log.debug('haproxy beacon unable to validate')
        return ret
    for backend in config:
        threshold = config[backend]['threshold']
        for server in config[backend]['servers']:
            scur = __salt__['haproxy.get_sessions'](server, backend)
            if scur:
                if int(scur) > int(threshold):
                    _server = {'server': server,
                               'scur': scur,
                               'threshold': threshold,
                               }
                    log.debug('Emit because {0} > {1} for {2} in {3}'.format(scur, threshold, server, backend))
                    ret.append(_server)
    return ret
