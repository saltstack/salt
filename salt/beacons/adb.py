# -*- coding: utf-8 -*-
'''
Beacon to emit adb device state changes for Android devices

.. versionadded:: 2016.3.0
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import logging

# Salt libs
import salt.utils.path
from salt.ext.six.moves import map

log = logging.getLogger(__name__)

__virtualname__ = 'adb'

last_state = {}
last_state_extra = {'value': False, 'no_devices': False}


def __virtual__():
    which_result = salt.utils.path.which('adb')
    if which_result is None:
        return False
    else:
        return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for adb beacon should be a dictionary with states array
    if not isinstance(config, list):
        log.info('Configuration for adb beacon must be a list.')
        return False, ('Configuration for adb beacon must be a list.')

    _config = {}
    list(map(_config.update, config))

    if 'states' not in _config:
        log.info('Configuration for adb beacon must include a states array.')
        return False, ('Configuration for adb beacon must include a states array.')
    else:
        if not isinstance(_config['states'], list):
            log.info('Configuration for adb beacon must include a states array.')
            return False, ('Configuration for adb beacon must include a states array.')
        else:
            states = ['offline', 'bootloader', 'device', 'host',
                      'recovery', 'no permissions',
                      'sideload', 'unauthorized', 'unknown', 'missing']
            if any(s not in states for s in _config['states']):
                log.info('Need a one of the following adb '
                         'states: %s', ', '.join(states))
                return False, ('Need a one of the following adb '
                               'states: {0}'.format(', '.join(states)))
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Emit the status of all devices returned by adb

    Specify the device states that should emit an event,
    there will be an event for each device with the
    event type and device specified.

    .. code-block:: yaml

        beacons:
          adb:
            - states:
                - offline
                - unauthorized
                - missing
            - no_devices_event: True
            - battery_low: 25

    '''

    log.trace('adb beacon starting')
    ret = []

    _config = {}
    list(map(_config.update, config))

    out = __salt__['cmd.run']('adb devices', runas=_config.get('user', None))

    lines = out.split('\n')[1:]
    last_state_devices = list(last_state.keys())
    found_devices = []

    for line in lines:
        try:
            device, state = line.split('\t')
            found_devices.append(device)
            if device not in last_state_devices or \
                    ('state' in last_state[device] and last_state[device]['state'] != state):
                if state in _config['states']:
                    ret.append({'device': device, 'state': state, 'tag': state})
                    last_state[device] = {'state': state}

            if 'battery_low' in _config:
                val = last_state.get(device, {})
                cmd = 'adb -s {0} shell cat /sys/class/power_supply/*/capacity'.format(device)
                battery_levels = __salt__['cmd.run'](cmd, runas=_config.get('user', None)).split('\n')

                for l in battery_levels:
                    battery_level = int(l)
                    if 0 < battery_level < 100:
                        if 'battery' not in val or battery_level != val['battery']:
                            if ('battery' not in val or val['battery'] > _config['battery_low']) and \
                                            battery_level <= _config['battery_low']:
                                ret.append({'device': device, 'battery_level': battery_level, 'tag': 'battery_low'})

                        if device not in last_state:
                            last_state[device] = {}

                        last_state[device].update({'battery': battery_level})

        except ValueError:
            continue

    # Find missing devices and remove them / send an event
    for device in last_state_devices:
        if device not in found_devices:
            if 'missing' in _config['states']:
                ret.append({'device': device, 'state': 'missing', 'tag': 'missing'})

            del last_state[device]

    # Maybe send an event if we don't have any devices
    if 'no_devices_event' in _config and _config['no_devices_event'] is True:
        if len(found_devices) == 0 and not last_state_extra['no_devices']:
            ret.append({'tag': 'no_devices'})

    # Did we have no devices listed this time around?

    last_state_extra['no_devices'] = len(found_devices) == 0

    return ret
