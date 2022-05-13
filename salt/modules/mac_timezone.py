"""
Module for editing date/time settings on macOS

 .. versionadded:: 2016.3.0
"""

from datetime import datetime

import salt.utils.mac_utils
import salt.utils.platform
from salt.exceptions import SaltInvocationError

__virtualname__ = "timezone"


def __virtual__():
    """
    Only for macOS
    """
    if not salt.utils.platform.is_darwin():
        return (
            False,
            "The mac_timezone module could not be loaded: "
            "module only works on macOS systems.",
        )

    return __virtualname__


def _get_date_time_format(dt_string):
    """
    Function that detects the date/time format for the string passed.

    :param str dt_string:
        A date/time string

    :return: The format of the passed dt_string
    :rtype: str

    :raises: SaltInvocationError on Invalid Date/Time string
    """
    valid_formats = [
        "%H:%M",
        "%H:%M:%S",
        "%m:%d:%y",
        "%m:%d:%Y",
        "%m/%d/%y",
        "%m/%d/%Y",
    ]
    for dt_format in valid_formats:
        try:
            datetime.strptime(dt_string, dt_format)
            return dt_format
        except ValueError:
            continue
    msg = "Invalid Date/Time Format: {}".format(dt_string)
    raise SaltInvocationError(msg)


def get_date():
    """
    Displays the current date

    :return: the system date
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_date
    """
    ret = salt.utils.mac_utils.execute_return_result("systemsetup -getdate")
    return salt.utils.mac_utils.parse_return(ret)


def set_date(date):
    """
    Set the current month, day, and year

    :param str date: The date to set. Valid date formats are:

        - %m:%d:%y
        - %m:%d:%Y
        - %m/%d/%y
        - %m/%d/%Y

    :return: True if successful, False if not
    :rtype: bool

    :raises: SaltInvocationError on Invalid Date format
    :raises: CommandExecutionError on failure

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_date 1/13/2016
    """
    date_format = _get_date_time_format(date)
    dt_obj = datetime.strptime(date, date_format)

    cmd = "systemsetup -setdate {}".format(dt_obj.strftime("%m:%d:%Y"))
    return salt.utils.mac_utils.execute_return_success(cmd)


def get_time():
    """
    Get the current system time.

    :return: The current time in 24 hour format
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_time
    """
    ret = salt.utils.mac_utils.execute_return_result("systemsetup -gettime")
    return salt.utils.mac_utils.parse_return(ret)


def set_time(time):
    """
    Sets the current time. Must be in 24 hour format.

    :param str time: The time to set in 24 hour format.  The value must be
        double quoted. ie: '"17:46"'

    :return: True if successful, False if not
    :rtype: bool

    :raises: SaltInvocationError on Invalid Time format
    :raises: CommandExecutionError on failure

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_time '"17:34"'
    """
    # time must be double quoted '"17:46"'
    time_format = _get_date_time_format(time)
    dt_obj = datetime.strptime(time, time_format)

    cmd = "systemsetup -settime {}".format(dt_obj.strftime("%H:%M:%S"))
    return salt.utils.mac_utils.execute_return_success(cmd)


def get_zone():
    """
    Displays the current time zone

    :return: The current time zone
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zone
    """
    ret = salt.utils.mac_utils.execute_return_result("systemsetup -gettimezone")
    return salt.utils.mac_utils.parse_return(ret)


def get_zonecode():
    """
    Displays the current time zone abbreviated code

    :return: The current time zone code
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zonecode
    """
    return salt.utils.mac_utils.execute_return_result("date +%Z")


def get_offset():
    """
    Displays the current time zone offset

    :return: The current time zone offset
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_offset
    """
    return salt.utils.mac_utils.execute_return_result("date +%z")


def list_zones():
    """
    Displays a list of available time zones. Use this list when setting a
    time zone using ``timezone.set_zone``

    :return: a list of time zones
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.list_zones
    """
    ret = salt.utils.mac_utils.execute_return_result("systemsetup -listtimezones")
    zones = salt.utils.mac_utils.parse_return(ret)

    return [x.strip() for x in zones.splitlines()]


def set_zone(time_zone):
    """
    Set the local time zone. Use ``timezone.list_zones`` to list valid time_zone
    arguments

    :param str time_zone: The time zone to apply

    :return: True if successful, False if not
    :rtype: bool

    :raises: SaltInvocationError on Invalid Timezone
    :raises: CommandExecutionError on failure

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_zone America/Denver
    """
    if time_zone not in list_zones():
        raise SaltInvocationError("Invalid Timezone: {}".format(time_zone))

    salt.utils.mac_utils.execute_return_success(
        "systemsetup -settimezone {}".format(time_zone)
    )

    return time_zone in get_zone()


def zone_compare(time_zone):
    """
    Compares the given timezone name with the system timezone name.

    :return: True if they are the same, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.zone_compare America/Boise
    """
    return time_zone == get_zone()


def get_using_network_time():
    """
    Display whether network time is on or off

    :return: True if network time is on, False if off
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_using_network_time
    """
    ret = salt.utils.mac_utils.execute_return_result("systemsetup -getusingnetworktime")

    return (
        salt.utils.mac_utils.validate_enabled(salt.utils.mac_utils.parse_return(ret))
        == "on"
    )


def set_using_network_time(enable):
    """
    Set whether network time is on or off.

    :param enable: True to enable, False to disable. Can also use 'on' or 'off'
    :type: str bool

    :return: True if successful, False if not
    :rtype: bool

    :raises: CommandExecutionError on failure

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_using_network_time True
    """
    state = salt.utils.mac_utils.validate_enabled(enable)

    cmd = "systemsetup -setusingnetworktime {}".format(state)
    salt.utils.mac_utils.execute_return_success(cmd)

    return state == salt.utils.mac_utils.validate_enabled(get_using_network_time())


def get_time_server():
    """
    Display the currently set network time server.

    :return: the network time server
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_time_server
    """
    ret = salt.utils.mac_utils.execute_return_result(
        "systemsetup -getnetworktimeserver"
    )
    return salt.utils.mac_utils.parse_return(ret)


def set_time_server(time_server="time.apple.com"):
    """
    Designates a network time server. Enter the IP address or DNS name for the
    network time server.

    :param time_server: IP or DNS name of the network time server. If nothing
        is passed the time server will be set to the macOS default of
        'time.apple.com'
    :type: str

    :return: True if successful, False if not
    :rtype: bool

    :raises: CommandExecutionError on failure

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_time_server time.acme.com
    """
    cmd = "systemsetup -setnetworktimeserver {}".format(time_server)
    salt.utils.mac_utils.execute_return_success(cmd)

    return time_server in get_time_server()


def get_hwclock():
    """
    Get current hardware clock setting (UTC or localtime)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_hwclock
    """
    # Need to search for a way to figure it out ...
    return False


def set_hwclock(clock):
    """
    Sets the hardware clock to be either UTC or localtime

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_hwclock UTC
    """
    # Need to search for a way to figure it out ...
    return False
