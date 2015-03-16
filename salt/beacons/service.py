# -*- coding: utf-8 -*-
'''
Send events covering service status
'''

# Import Python Libs
from __future__ import absolute_import

import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


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
    return [{srvc: __salt__['service.status'](srvc)} for srvc in config]
