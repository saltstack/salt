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
import salt.utils.mac_utils
from salt.exceptions import CommandExecutionError

__virtualname__ = 'timezone'


def __virtual__():
    '''
    Only for Mac OS X
    '''
    if not salt.utils.is_darwin():
        return (False, 'The mac_timezone module could not be loaded: '
                       'module only works on Mac OS X systems.')

    return __virtualname__


def _get_date_time_format(dt_string):
    '''
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


def get_date():
    '''
    Displays the current date

    Returns: the system date

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_date
    '''
    ret = salt.utils.mac_utils.execute_return_result('systemsetup -getdate')
    return salt.utils.mac_utils.parse_return(ret)


def set_date(date):
    '''
    Set the current month, day, and year

    :param str date: The date to set. Valid date formats are:
    - %m:%d:%y
    - %m:%d:%Y
    - %m/%d/%y
    - %m/%d/%Y

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_date 1/13/2016
    '''
    date_format = _get_date_time_format(date)
    dt_obj = datetime.strptime(date, date_format)

    cmd = 'systemsetup -setdate {0}'.format(dt_obj.strftime('%m:%d:%Y'))
    salt.utils.mac_utils.execute_return_success(cmd)

    new_date = get_date()
    date_format = _get_date_time_format(new_date)
    new_dt_obj = datetime.strptime(new_date, date_format)

    return dt_obj.strftime('%m:%d:%Y') == new_dt_obj.strftime('%m:%d:%Y')


def get_time():
    '''
    Get the current system time.

    :return: The current time in 24 hour format
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_time
    '''
    ret = salt.utils.mac_utils.execute_return_result('systemsetup -gettime')
    return salt.utils.mac_utils.parse_return(ret)


def set_time(time):
    '''
    Sets the current time. Must be in 24 hour format.

    :param str time: The time to set in 24 hour format.
    The value must be double quoted.

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_time '"17:34"'
    '''
    # time must be double quoted '"17:46"'
    time_format = _get_date_time_format(time)
    dt_obj = datetime.strptime(time, time_format)

    cmd = 'systemsetup -settime {0}'.format(dt_obj.strftime('%H:%M:%S'))
    salt.utils.mac_utils.execute_return_success(cmd)

    new_time = get_time()
    time_format = _get_date_time_format(new_time)
    new_dt_obj = datetime.strptime(new_time, time_format)

    return dt_obj.strftime('%H:%M:%S') == new_dt_obj.strftime('%H:%M:%S')


def get_zone():
    '''
    Displays the current time zone

    :return: The current time zone
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zone
    '''
    ret = salt.utils.mac_utils.execute_return_result('systemsetup -gettimezone')
    return salt.utils.mac_utils.parse_return(ret)


def get_zonecode():
    '''
    Displays the current time zone abbreviated code

    :return: The current time zone code
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zonecode
    '''
    return salt.utils.mac_utils.execute_return_result('date +%Z')


def get_offset():
    '''
    Displays the current time zone offset

    :return: The current time zone offset
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_offset
    '''
    return salt.utils.mac_utils.execute_return_result('date +%z')


def list_zones():
    '''
    Displays a list of available time zones. Use this list when setting a
    time zone using ``timezone.set_zone``

    :return: a string containing a list of time zones
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.list_zones
    '''
    ret = salt.utils.mac_utils.execute_return_result('systemsetup -listtimezones')
    return salt.utils.mac_utils.parse_return(ret)


def set_zone(time_zone):
    '''
    Set the local time zone. Use ``timezone.list_zones`` to list valid time_zone
    arguments

    :param str time_zone: The time zone to apply

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_zone America/Denver
    '''
    if time_zone not in list_zones():
        return (False, 'Not a valid timezone. '
                       'Use list_time_zones to find a valid time zone.')

    salt.utils.mac_utils.execute_return_success('systemsetup -settimezone {0}'.format(time_zone))

    return time_zone in get_zone()


def zone_compare(time_zone):
    '''
    Compares the given timezone name with the system timezone name.

    :return: True if they are the same, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.zone_compare America/Boise
    '''
    current = get_zone()

    if current != time_zone:
        return False

    return True


def get_using_network_time():
    '''
    Display whether network time is on or off

    :return: True if network time is on, False if off
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_using_network_time
    '''
    ret = salt.utils.mac_utils.execute_return_result('systemsetup -getusingnetworktime')
    return salt.utils.mac_utils.validate_enabled(salt.utils.mac_utils.parse_return(ret)) == 'on'


def set_using_network_time(enable):
    '''
    Set whether network time is on or off.

    :param enable: True to enable, False to disable. Can also use 'on' or 'off'
    :type: str bool

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_using_network_time True
    '''
    state = salt.utils.mac_utils.validate_enabled(enable)

    cmd = 'systemsetup -setusingnetworktime {0}'.format(state)
    salt.utils.mac_utils.execute_return_success(cmd)

    return state == salt.utils.mac_utils.validate_enabled(get_using_network_time())


def get_time_server():
    '''
    Display the currently set network time server.

    :return: the network time server
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_time_server
    '''
    ret = salt.utils.mac_utils.execute_return_result('systemsetup -getnetworktimeserver')
    return salt.utils.mac_utils.parse_return(ret)


def set_time_server(time_server='time.apple.com'):
    '''
    Designates a network time server. Enter the IP address or DNS name for the
    network time server.

    :param time_server: IP or DNS name of the network time server. If nothing is
    passed the time server will be set to the OS X default of 'time.apple.com'
    :type: str

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_time_server time.acme.com
    '''
    cmd = 'systemsetup -setnetworktimeserver {0}'.format(time_server)
    salt.utils.mac_utils.execute_return_success(cmd)

    return time_server in get_time_server()
