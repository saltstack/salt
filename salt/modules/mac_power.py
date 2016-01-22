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


def _command_success(ret, cmd):
    if ret['retcode'] != 0:
        if 'not supported' not in ret['stdout'].lower():
            msg = 'Command Failed {0}\n'.format(cmd)
            msg += 'Return Code: {0}\n'.format(ret['retcode'])
            msg += 'Error: {0}\n'.format(ret['stderr'])
            msg += 'Output: {0}\n'.format(ret['stdout'])
            raise CommandExecutionError(msg)

    return ret['stdout']


def _execute_return_success(cmd):
    '''
    Helper function to execute the command
    Returns: bool
    '''
    ret = __salt__['cmd.run_all'](cmd)
    _command_success(ret, cmd)
    return True


def _execute_return_result(cmd):
    '''
    Helper function to execute the command
    Returns: stdout of command
    '''
    ret = __salt__['cmd.run_all'](cmd)
    return _command_success(ret, cmd)


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
    if isinstance(minutes, int):
        if minutes not in range(1, 181):
            msg = 'Mac Power: Invalid Integer Value for Minutes. ' \
                  'Integer values must be between 1 and 180'
            raise SaltInvocationError(msg)
    elif isinstance(minutes, str):
        if minutes.lower() not in ['never', 'off']:
            msg = 'Mac Power: Invalid String Value for Minutes. ' \
                  'String values must be "Never" or "Off"'
            raise SaltInvocationError(msg)
    else:
        msg = 'Mac Power: Unknown Variable Type Passed for Minutes. ' \
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
            msg = 'Mac Power: Invalid String Value for Enabled. ' \
                  'String values must be "On" or "Off"'
            raise SaltInvocationError(msg)
    elif isinstance(enabled, int):
        if enabled in [1, 0]:
            if enabled == 1:
                return 'on'
            else:
                return 'off'
        else:
            msg = 'Mac Power: Invalid Integer Value for Enabled. ' \
                  'Integer values must be 1 or 0'
            raise SaltInvocationError(msg)
    else:
        msg = 'Mac Power: Unknown Variable Type Passed for Enabled. ' \
              'Passed: {0}'.format(enabled)
        raise SaltInvocationError(msg)


def get_sleep():
    results = {}

    results['Computer'] = get_computer_sleep()
    results['Display'] = get_display_sleep()
    results['Hard Disk'] = get_harddisk_sleep()

    return results


def set_sleep(minutes):
    _validate_sleep(minutes)
    cmd = 'systemsetup -setsleep {0}'.format(minutes)
    return _execute_return_success(cmd)


def get_computer_sleep():
    ret = _execute_return_result('systemsetup -getcomputersleep')
    return _parse_return(ret)


def set_computer_sleep(minutes):
    _validate_sleep(minutes)
    cmd = 'systemsetup -setcomputersleep {0}'.format(minutes)
    return _execute_return_success(cmd)


def get_display_sleep():
    ret = _execute_return_result('systemsetup -getdisplaysleep')
    return _parse_return(ret)


def set_display_sleep(minutes):
    _validate_sleep(minutes)
    cmd = 'systemsetup -setdisplaysleep {0}'.format(minutes)
    return _execute_return_success(cmd)


def get_harddisk_sleep():
    ret = _execute_return_result('systemsetup -getharddisksleep')
    return _parse_return(ret)


def set_harddisk_sleep(minutes):
    _validate_sleep(minutes)
    cmd = 'systemsetup -setharddisksleep {0}'.format(minutes)
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
    cmd = 'systemsetup -set allowpowerbuttontosleepcomputer {0}'.format(state)
    return _execute_return_success(cmd)
