# -*- coding: utf-8 -*-
'''
Beacon to emit system load averages
'''

# Import Python libs
from __future__ import absolute_import
import logging
import psutil
import os

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
Emits load levels based on the parameters below.
Tested and working in:
-Windows Server 2012r2
-CentOS 6

Units in seconds [interval] and percent [min, max].
Reports below min or above max. Set both to 0 for reports every interval.
Set percpu for percpu percentages, instead of the overall number.
Failing to provide min/max data will result in defaults that cause the response
to be sent every time (so to always send, just leave those out).

beacons
  load:
    interval: 30
    min: 1
    max: 70
    percpu:
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
        config['max'] = -1
    if 'min' not in config:
        config['min'] = 101
    cpu_percent = psutil.cpu_percent(interval=1)
    log.trace(cpu_percent)
    send_beacon = False
    ret = dict()

    global LAST_STATUS
    if LAST_STATUS < 0:
        send_beacon = True
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
        send_beacon = LAST_STATUS == cpu_percent
        LAST_STATUS = cpu_percent

    if send_beacon:
        ret['min'] = config['min']
        ret['max'] = config['max']
        if 'percpu' in config:
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        ret['load'] = cpu_percent
        if 'queue' in config:
            ret['processorqueue'] = getProcessorQueueLength()
    log.trace(ret)

    return [ret]

def getProcessorQueueLength():
    if salt.utils.is_windows():
        return getWindowsProcessorQueueLength()
    else:
        return getUnixProcessorQueueLength()

def getWindowsProcessorQueueLength():
    return os.system('wmic path Win32_PerfFormattedData_PerfOS_System get ProcessorQueueLength')

def getUnixProcessorQueueLength():
    processIterator = psutil.process_iter
    count = 0
    for p in processIterator():
        if p.status() == 'running':
            count += 1
    return count
