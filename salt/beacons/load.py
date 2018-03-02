# -*- coding: utf-8 -*-
'''
Beacon to emit system load averages
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import logging
import os

# Import Salt libs
import salt.utils.platform
from salt.ext.six.moves import map

# Import Py3 compat
from salt.ext.six.moves import zip

log = logging.getLogger(__name__)

__virtualname__ = 'load'

LAST_STATUS = {}


def __virtual__():
    if salt.utils.platform.is_windows():
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
        _config = {}
        list(map(_config.update, config))

        if 'averages' not in _config:
            return False, ('Averages configuration is required'
                           ' for load beacon.')
        else:

            if not any(j in ['1m', '5m', '15m'] for j
                       in _config.get('averages', {})):
                return False, ('Averages configuration for load beacon '
                               'must contain 1m, 5m or 15m items.')

            for item in ['1m', '5m', '15m']:
                if not isinstance(_config['averages'][item], list):
                    return False, ('Averages configuration for load beacon: '
                                   '1m, 5m and 15m items must be '
                                   'a list of two items.')
                else:
                    if len(_config['averages'][item]) != 2:
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

    `onchangeonly`: when `onchangeonly` is True the beacon will fire
    events only when the load average pass one threshold.  Otherwise, it will fire an
    event at each beacon interval.  The default is False.

    `emitatstartup`: when `emitatstartup` is False the beacon will not fire
     event when the minion is reload. Applicable only when `onchangeonly` is True.
     The default is True.

    .. code-block:: yaml

        beacons:
          load:
            - averages:
                1m:
                  - 0.0
                  - 2.0
                5m:
                  - 0.0
                  - 1.5
                15m:
                  - 0.1
                  - 1.0
            - emitatstartup: True
            - onchangeonly: False

    '''
    log.trace('load beacon starting')

    _config = {}
    list(map(_config.update, config))

    # Default config if not present
    if 'emitatstartup' not in _config:
        _config['emitatstartup'] = True
    if 'onchangeonly' not in _config:
        _config['onchangeonly'] = False

    ret = []
    avgs = os.getloadavg()
    avg_keys = ['1m', '5m', '15m']
    avg_dict = dict(zip(avg_keys, avgs))

    if _config['onchangeonly']:
        if not LAST_STATUS:
            for k in ['1m', '5m', '15m']:
                LAST_STATUS[k] = avg_dict[k]
            if not config['emitatstartup']:
                log.debug('Dont emit because emitatstartup is False')
                return ret

    send_beacon = False

    # Check each entry for threshold
    for k in ['1m', '5m', '15m']:
        if k in _config.get('averages', {}):
            if _config['onchangeonly']:
                # Emit if current is more that threshold and old value less
                # that threshold
                if float(avg_dict[k]) > float(_config['averages'][k][1]) and \
                   float(LAST_STATUS[k]) < float(_config['averages'][k][1]):
                    log.debug('Emit because %f > %f and last was '
                              '%f', float(avg_dict[k]),
                              float(_config['averages'][k][1]),
                              float(LAST_STATUS[k]))
                    send_beacon = True
                    break
                # Emit if current is less that threshold and old value more
                # that threshold
                if float(avg_dict[k]) < float(_config['averages'][k][0]) and \
                   float(LAST_STATUS[k]) > float(_config['averages'][k][0]):
                    log.debug('Emit because %f < %f and last was'
                              '%f', float(avg_dict[k]),
                              float(_config['averages'][k][0]),
                              float(LAST_STATUS[k]))
                    send_beacon = True
                    break
            else:
                # Emit no matter LAST_STATUS
                if float(avg_dict[k]) < float(_config['averages'][k][0]) or \
                   float(avg_dict[k]) > float(_config['averages'][k][1]):
                    log.debug('Emit because %f < %f or > '
                              '%f', float(avg_dict[k]),
                              float(_config['averages'][k][0]),
                              float(_config['averages'][k][1]))
                    send_beacon = True
                    break

    if _config['onchangeonly']:
        for k in ['1m', '5m', '15m']:
            LAST_STATUS[k] = avg_dict[k]

    if send_beacon:
        ret.append(avg_dict)

    return ret
