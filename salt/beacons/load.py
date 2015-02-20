# -*- coding: utf-8 -*-
'''
Becaon to emit system load averages
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'load'


def __virtual__():
    if salt.utils.is_windows():
        return False
    else:
        return __virtualname__


def beacon(config):
    '''
    Emit the load averages of this host.

    Specify thresholds for for each load average
    and only emit a beacon if any of them are
    exceeded.

    code_block:: yaml

        beacons:
            - load:
              - 1m:
                - 0.0
                - 2.0
              - 5m:
                - 0.0
                - 1.5
              - 15m:
                - 0.1
                - 1.0

    '''
    log.trace('load beacon starting')
    print(config)
    ret = []
    if not os.path.isfile('/proc/loadavg'):
        return ret
    with salt.utils.fopen('/proc/loadavg', 'rb') as fp_:
        avgs = fp_.read().split()[:3]
        # Check each entry for threshold
        if avgs[0] < float(config[0]['1m'][0]) or \
        avgs[0] > float(config[0]['1m'][1]) or \
        avgs[1] < float(config[0]['5m'][0]) or \
        avgs[1] > float(config[0]['5m'][1]) or \
        avgs[2] < float(config[0]['15m'][0]) or \
        avgs[2] > float(config[0]['15m'][1]):
            ret.append({'avg': avgs})
    return ret
