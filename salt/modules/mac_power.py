# -*- coding: utf-8 -*-
'''
Module for editing power settings on Mac OS X

 .. versionadded:: Boron
'''
from __future__ import absolute_import

# Import python libs
from datetime import datetime

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

    if ret['retcode'] != 0:
        msg = 'Command failed: {0}'.format(ret['stderr'])
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


def get_sleep():
    ret = _execute_return_result('systemsetup -getsleep')
    return _parse_return(ret)


def set_sleep(minutes):
    # Validate Input
    # Must be a value between 1 and 180 or Never/Off
    if isinstance(minutes, int):
        if minutes not in range(1, 180):
            msg = 'Mac Power: Invalid Integer Value for Minutes. ' \
                  'Integer values must be between 1 and 180'
            raise SaltInvocationError(msg)
    elif isinstance(minutes, str):
        if minutes not in ['Never', 'never', 'Off', 'off']:
            msg = 'Mac Power: Invalid String Value for Minutes. ' \
                  'String values must be "Never" or "Off"'
            raise SaltInvocationError(msg)
    else:
        msg = 'Mac Power: Unknown Variable Type Passed for Minutes. ' \
              'Passed: {0}'.format(minutes)
        raise SaltInvocationError(msg)
    cmd = 'systemsetup -setsleep {0}'.format(minutes)
    _execute_return_success(cmd)

    return minutes.lower() == get_sleep().lower()
