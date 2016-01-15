# -*- coding: utf-8 -*-
'''
Module for editing date/time settings on Mac OS X

 .. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

__virtualname__ = 'timezone'


def __virtual__():
    '''
    Only for MacOS
    '''
    if not salt.utils.is_darwin():
        return (False, 'The mac_timezone module could not be loaded: '
                       'module only works on MacOS systems.')

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


def get_date():
    cmd = 'systemsetup -getdate'
    ret = _execute_return_result(cmd)

    return _parse_return(ret)


def set_date(date):
    cmd = 'systemsetup -setdate {0}'.format(date)
    return _execute_return_success(cmd)


def get_time():
    cmd = 'systemsetup -gettime'
    ret = _execute_return_result(cmd)

    return _parse_return(ret)


def set_time(time):
    cmd = 'systemsetup -settime {0}'.format(time)
    return _execute_return_success(cmd)


def get_zone():
    cmd = 'systemsetup -gettimezone'
    ret = _execute_return_result(cmd)

    return _parse_return(ret)


def get_zonecode():
    cmd = 'date +%Z'
    return _execute_return_result(cmd)


def get_offset():
    cmd = 'date +%z'
    return _execute_return_result(cmd)


def list_zones():
    cmd = 'systemsetup -listtimezones'
    ret = _execute_return_result(cmd)

    return _parse_return(ret)


def set_zone(time_zone):
    if time_zone not in list_zones():
        return (False, 'Not a valid timezone. '
                       'Use list_time_zones to find a valid time zone.')
    cmd = 'systemsetup -settimezone {0}'.format(time_zone)

    return _execute_return_success(cmd)


def zone_compare(time_zone):
    current = get_zone()

    if current != time_zone:
        return False

    return True


def get_using_network_time():
    cmd = 'systemsetup -getusingnetworktime'
    return _execute_return_result(cmd)


def set_using_network_time(enable):
    if not isinstance(enable, bool):
        msg = 'Must pass a boolean value. Passed: {0}'.format(enable)
        raise CommandExecutionError(msg)

    if enable:
        enable = 'on'
    else:
        enable = 'off'
    cmd = 'systemsetup -setusingnetworktime {0}'.format(enable)

    return _execute_return_success(cmd)


def get_time_server():
    cmd = 'systemsetup -getnetworktimeserver'
    return _execute_return_result(cmd)


def set_time_server(time_server):
    cmd = 'systemsetup -setnetworktimeserver {0}'.format(time_server)
    return _execute_return_success(cmd)


def get_hwclock():
    '''
    Returns: Always returns 'UTC' because OS X Hardware clock is always UTC
    '''
    return 'UTC'


def set_hwclock():
    '''
    Setting not editable in Mac
    '''
    pass
