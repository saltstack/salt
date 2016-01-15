# -*- coding: utf-8 -*-
'''
Module for editing date/time settings on Mac OS X

 .. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import python libs
from datetime import datetime

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


def _get_date_time_format(dt_string):
    '''
    Copied from win_system.py (_get_date_time_format)

    Function that detects the date/time format for the string passed.

    :param str dt_string:
        A date/time string

    :return: The format of the passed dt_string
    :rtype: str
    '''
    valid_formats = [
        '%H:%M',
        '%H:%M:%S',
        '%m:%d:%y',
        '%m:%d:%Y',
        '%m/%d/%y',
        '%m/%d/%Y'
    ]
    for dt_format in valid_formats:
        try:
            datetime.strptime(dt_string, dt_format)
            return dt_format
        except ValueError:
            continue
    msg = 'Invalid Date/Time Format: {0}'.format(dt_string)
    raise CommandExecutionError(msg)


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
    date_format = _get_date_time_format(date)
    dt_obj = datetime.strptime(date, date_format)

    cmd = 'systemsetup -setdate {0}'.format(dt_obj.strftime('%m:%d:%Y'))
    _execute_return_success(cmd)

    new_date = get_date()
    date_format = _get_date_time_format(new_date)
    new_dt_obj = datetime.strptime(new_date, date_format)

    return dt_obj.strftime('%m:%d:%Y') == new_dt_obj.strftime('%m:%d:%Y')


def get_time():
    cmd = 'systemsetup -gettime'
    ret = _execute_return_result(cmd)

    return _parse_return(ret)


def set_time(time):
    time_format = _get_date_time_format(time)
    dt_obj = datetime.strptime(time, time_format)

    cmd = 'systemsetup -settime {0}'.format(dt_obj.strftime('%H:%M:%S'))
    _execute_return_success(cmd)

    new_time = get_time()
    time_format = _get_date_time_format(new_time)
    new_dt_obj = datetime.strptime(new_time, time_format)

    return dt_obj.strftime('%H:%M:%S') == new_dt_obj.strftime('%H:%M:%S')


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

    _execute_return_success(cmd)

    return time_zone in get_zone()


def zone_compare(time_zone):
    current = get_zone()

    if current != time_zone:
        return False

    return True


def get_using_network_time():
    cmd = 'systemsetup -getusingnetworktime'
    ret = _execute_return_result(cmd)

    if _parse_return(ret) == 'On':
        return True
    else:
        return False


def set_using_network_time(enable):
    if enable not in ['On', 'on', 'Off', 'off', True, False]:
        msg = 'Must pass a boolean value. Passed: {0}'.format(enable)
        raise CommandExecutionError(msg)

    if enable in ['On', 'on', True]:
        enable = 'on'
        expect = True
    else:
        enable = 'off'
        expect = False
    cmd = 'systemsetup -setusingnetworktime {0}'.format(enable)

    _execute_return_success(cmd)

    return expect == get_using_network_time()


def get_time_server():
    cmd = 'systemsetup -getnetworktimeserver'
    ret = _execute_return_result(cmd)

    return _parse_return(ret)


def set_time_server(time_server):
    if time_server.lower() == 'default':
        time_server = 'time.apple.com'
    cmd = 'systemsetup -setnetworktimeserver {0}'.format(time_server)
    _execute_return_success(cmd)

    return time_server in get_time_server()


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
