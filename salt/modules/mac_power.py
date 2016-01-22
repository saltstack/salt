# -*- coding: utf-8 -*-
'''
Module for editing power settings on Mac OS X

 .. versionadded:: Boron
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = 'power'


def __virtual__():
    '''
    Only for Mac OS X
    '''
    if not salt.utils.is_darwin():
        return (False, 'The mac_power module could not be loaded: '
                       'module only works on Mac OS X systems.')

    return __virtualname__


def _execute_return_success(cmd):
    '''
    Helper function to execute the command
    Returns: bool
    '''
    ret = __salt__['cmd.run_all'](cmd)

    if 'not supported' in ret['stdout'].lower():
        return 'Not supported on this machine'

    if ret['retcode'] != 0:
        msg = 'Command Failed: {0}\n'.format(cmd)
        msg += 'Return Code: {0}\n'.format(ret['retcode'])
        msg += 'Output: {0}\n'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return True


def _execute_return_result(cmd):
    ret = __salt__['cmd.run_all'](cmd)

    if ret['retcode'] != 0:
        msg = 'Command failed: {0}'.format(ret['stderr'])
        raise CommandExecutionError(msg)

    return ret['stdout']


def _parse_return(data):
    '''
    Parse a return in the format:
    ``Time Zone: America/Denver``
    to return only:
    ``America/Denver``

    Returns: The value portion of a return
    '''

    if ': ' in data:
        return data.split(': ')[1]
    if ':\n' in data:
        return data.split(':\n')[1]
    else:
        return data


def _validate_sleep(minutes):
    # Must be a value between 1 and 180 or Never/Off
    if isinstance(minutes, str):
        if minutes.lower() in ['never']:
            return minutes.lower()
        else:
            msg = '\nMac Power: Invalid String Value for Minutes.\n' \
                  'String values must be "Never" or "Off".\n' \
                  'Passed: {0}'.format(minutes)
            raise SaltInvocationError(msg)
    elif isinstance(minutes, bool):
        if minutes:
            msg = '\nMac Power: Invalid Boolean Value for Minutes.\n' \
                  'Boolean value "On" or "True" is not allowed.\n' \
                  'Salt CLI converts "On" to boolean True.\n' \
                  'Passed: {0}'.format(minutes)
            raise SaltInvocationError(msg)
        else:
            return 'never'
    elif isinstance(minutes, int):
        if minutes in range(1, 181):
            return minutes
        else:
            msg = '\nMac Power: Invalid Integer Value for Minutes.\n' \
                  'Integer values must be between 1 and 180.\n' \
                  'Passed: {0}'.format(minutes)
            raise SaltInvocationError(msg)
    else:
        msg = '\nMac Power: Unknown Variable Type Passed for Minutes.\n' \
              'Passed: {0}'.format(minutes)
        raise SaltInvocationError(msg)


def _validate_enabled(enabled):
    if isinstance(enabled, bool):
        if enabled:
            return 'on'
        else:
            return 'off'
    elif isinstance(enabled, str):
        if enabled.lower() in ['on', 'off']:
            return enabled.lower()
        else:
            msg = '\nMac Power: Invalid String Value for Enabled.\n' \
                  'String values must be "On" or "Off".\n' \
                  'Passed: {0}'.format(enabled)
            raise SaltInvocationError(msg)
    elif isinstance(enabled, int):
        if enabled in [1, 0]:
            if enabled == 1:
                return 'on'
            else:
                return 'off'
        else:
            msg = '\nMac Power: Invalid Integer Value for Enabled.\n' \
                  'Integer values must be 1 or 0.\n' \
                  'Passed: {0}'.format(enabled)
            raise SaltInvocationError(msg)
    else:
        msg = '\nMac Power: Unknown Variable Type Passed for Enabled.\n' \
              'Passed: {0}'.format(enabled)
        raise SaltInvocationError(msg)


def get_sleep():
    return {'Computer': get_computer_sleep(),
            'Display': get_display_sleep(),
            'Hard Disk': get_harddisk_sleep()}


def set_sleep(minutes):
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setsleep {0}'.format(value)
    return _execute_return_success(cmd)


def get_computer_sleep():
    ret = _execute_return_result('systemsetup -getcomputersleep')
    return _parse_return(ret)


def set_computer_sleep(minutes):
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setcomputersleep {0}'.format(value)
    return _execute_return_success(cmd)


def get_display_sleep():
    ret = _execute_return_result('systemsetup -getdisplaysleep')
    return _parse_return(ret)


def set_display_sleep(minutes):
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setdisplaysleep {0}'.format(value)
    return _execute_return_success(cmd)


def get_harddisk_sleep():
    ret = _execute_return_result('systemsetup -getharddisksleep')
    return _parse_return(ret)


def set_harddisk_sleep(minutes):
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setharddisksleep {0}'.format(value)
    return _execute_return_success(cmd)


def get_wake_on_modem():
    ret = _execute_return_result('systemsetup -getwakeonmodem')
    return _parse_return(ret)


def set_wake_on_modem(enabled):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setwakeonmodem {0}'.format(state)
    return _execute_return_success(cmd)


def get_wake_on_network():
    ret = _execute_return_result('systemsetup -getwakeonnetworkaccess')
    return _parse_return(ret)


def set_wake_on_network(enabled):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setwakeonnetworkaccess {0}'.format(state)
    return _execute_return_success(cmd)


def get_restart_power_failure():
    ret = _execute_return_result('systemsetup -getrestartpowerfailure')
    return _parse_return(ret)


def set_restart_power_failure(enabled):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setrestartpowerfailure {0}'.format(state)
    return _execute_return_success(cmd)


def get_restart_freeze():
    ret = _execute_return_result('systemsetup -getrestartfreeze')
    return _parse_return(ret)


def set_restart_freeze(enabled):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setrestartfreeze {0}'.format(state)
    return _execute_return_success(cmd)


def get_sleep_on_power_button():
    ret = _execute_return_result('systemsetup -getallowpowerbuttontosleepcomputer')
    return _parse_return(ret)


def set_sleep_on_power_button(enabled):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setallowpowerbuttontosleepcomputer {0}'.format(state)
    return _execute_return_success(cmd)
