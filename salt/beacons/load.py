# -*- coding: utf-8 -*-
'''
Beacon to emit system load averages
'''

# Import Python libs
from __future__ import absolute_import
import logging
import psutil

# Import Salt libs
import salt.utils

# Import Py3 compat
from salt.ext.six.moves import zip

log = logging.getLogger(__name__)

__virtualname__ = 'load'

LAST_STATUS = -1


def __virtual__():
    return __virtualname__

'''
Units in seconds [interval] and percent [min, max]
Reports below min or above max. Set both to 0 for reports every interval

beacons
  load:
    interval: 30
    min: 1
    max: 70
'''

def validate(config):
    # Configuration for load beacon should be a list of dicts
    if not isinstance(config, dict):
        return False, ('Configuration for service beacon must be a dictionary.')
    return True, 'Valid beacon configuration'


def beacon(config):
    log.trace('load beacon starting')
    log.trace(config)

    # Default config if not present
    if 'emitatstartup' not in config:
        config['emitatstartup'] = True
    if 'onchangeonly' not in config:
        config['onchangeonly'] = False
    if 'max' not in config:
        config['max'] = 101
    if 'min' not in config:
        config['min'] = -1

    ret = []
    cpu_percent = psutil.cpu_percent(interval=1)
    log.trace(cpu_percent)
    send_beacon = False

    if config['onchangeonly']:
        if not LAST_STATUS:
            LAST_STATUS = cpu_percent
            if not config['emitatstartup']:
                log.debug('Dont emit because emitatstartup is False')
                return ret

    # Check each entry for threshold
    if config['onchangeonly']:
        # Emit if current is more that threshold and old value less that threshold
        if int(cpu_percent) > int(config['max']) and int(LAST_STATUS) != int(cpu_percent):
            log.debug('Emit because {0} > {1} and last was {2}'.format(int(cpu_percent), int(config['max']), int(LAST_STATUS)))
            send_beacon = True
        # Emit if current is less that threshold and old value more that threshold
        if int(cpu_percent) < int(config['min']) and int(LAST_STATUS) != int(cpu_percent):
            log.debug('Emit because {0} < {1} and last was {2}'.format(int(cpu_percent), int(config['min']), int(LAST_STATUS)))
            send_beacon = True
    else:
        # Emit no matter LAST_STATUS
        if int(cpu_percent) < int(config['min']) or \
        int(cpu_percent) > int(config['max']):
            log.debug('Emit because {0} < {1} or > {2}'.format(int(cpu_percent), int(config['min']), int(config['max'])))
            send_beacon = True

    if config['onchangeonly']:
        LAST_STATUS = cpu_percent

    if send_beacon:
        ret.append({'min': config['min'], 'max': config['max'], 'actual': cpu_percent})

    return ret
