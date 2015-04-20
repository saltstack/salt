# -*- coding: utf-8 -*-
'''
Send events covering service status
'''

# Import Python Libs
from __future__ import absolute_import

import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for service beacon should be a list of dicts
    if not isinstance(config, dict):
        log.info('Configuration for service beacon must be a dictionary.')
        return False
    return True


def beacon(config):
    '''
    Scan for the configured services and fire events

    Example Config

    .. code-block:: yaml

        beacons:
          service:
            salt-master:
            mysql:


    The config above sets up beacons to check for
    the salt-master and mysql services.
    '''
    ret = []
    for service in config:
        ret_dict = {}
        ret_dict[service] = __salt__['service.status'](service)
        ret.append(ret_dict)

    return ret
