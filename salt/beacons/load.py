# -*- coding: utf-8 -*-
'''
Beacon to emit system load averages
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt libs
import salt.utils

# Import Py3 compat
from salt.ext.six.moves import zip

log = logging.getLogger(__name__)

__virtualname__ = 'load'


def __virtual__():
    if salt.utils.is_windows():
        return False
    else:
        return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''

    # Configuration for load beacon should be a list of dicts
    if not isinstance(config, list):
        return False, ('Configuration for load beacon must be a list.')
    else:
        for config_item in config:
            if not isinstance(config_item, dict):
                return False, ('Configuration for load beacon must '
                               'be a list of dictionaries.')
            else:
                if not any(j in ['1m', '5m', '15m'] for j in config_item.keys()):
                    return False, ('Configuration for load beacon must '
                                   'contain 1m, 5m and 15m items.')

            for item in config_item:
                if not isinstance(config_item[item], list):
                    return False, ('Configuration for load beacon: '
                                   '1m, 5m and 15m items must be '
                                   'a list of two items.')
                else:
                    if len(config_item[item]) != 2:
                        return False, ('Configuration for load beacon: '
                                       '1m, 5m and 15m items must be '
                                       'a list of two items.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Emit the load averages of this host.

    Specify thresholds for each load average
    and only emit a beacon if any of them are
    exceeded.

    .. code-block:: yaml

        beacons:
          load:
            1m:
              - 0.0
              - 2.0
            5m:
              - 0.0
              - 1.5
            15m:
              - 0.1
              - 1.0

    '''
    log.trace('load beacon starting')
    ret = []
    if not os.path.isfile('/proc/loadavg'):
        return ret
    with salt.utils.fopen('/proc/loadavg', 'rb') as fp_:
        avgs = fp_.read().split()[:3]
        avg_keys = ['1m', '5m', '15m']
        avg_dict = dict(zip(avg_keys, avgs))
        # Check each entry for threshold
        if float(avgs[0]) < float(config['1m'][0]) or \
        float(avgs[0]) > float(config['1m'][1]) or \
        float(avgs[1]) < float(config['5m'][0]) or \
        float(avgs[1]) > float(config['5m'][1]) or \
        float(avgs[2]) < float(config['15m'][0]) or \
        float(avgs[2]) > float(config['15m'][1]):
            ret.append(avg_dict)
    return ret
