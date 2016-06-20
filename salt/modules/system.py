# -*- coding: utf-8 -*-
'''
Support for reboot, shutdown, etc
'''
from __future__ import absolute_import

# Import python libs
from datetime import datetime
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError


__virtualname__ = 'system'


def __virtual__():
    '''
    Only supported on POSIX-like systems
    Windows, Solaris, and Mac have their own modules
    '''
    if salt.utils.is_windows():
        return (False, 'This module is not available on windows')

    if salt.utils.is_darwin():
        return (False, 'This module is not available on Mac OS')

    if salt.utils.is_sunos():
        return (False, 'This module is not available on SunOS')

    return __virtualname__


def halt():
    '''
    Halt a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
    '''
    cmd = ['halt']
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems

    CLI Example:

    .. code-block:: bash

        salt '*' system.init 3
    '''
    cmd = ['init', '{0}'.format(runlevel)]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def poweroff():
    '''
    Poweroff a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff
    '''
    cmd = ['poweroff']
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def reboot(at_time=None):
    '''
    Reboot the system

    at_time
        The wait time in minutes before the system will be rebooted.

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot
    '''
    cmd = ['shutdown', '-r', ('{0}'.format(at_time) if at_time else 'now')]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def shutdown(at_time=None):
    '''
    Shutdown a running system

    at_time
        The wait time in minutes before the system will be shutdown.

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown 5
    '''
    cmd = ['shutdown', '-h', ('{0}'.format(at_time) if at_time else 'now')]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def _linux_set_datetime(new_time, utc=None):
    '''set the system date/time on linux'''
    # Modified version of: http://stackoverflow.com/a/12292874
    import ctypes
    import ctypes.util
    import time

    # Temporarily set the TZ environment variable
    # This must be done before loading the external library
    if utc is True:
        save_timezone = os.environ.get('TZ', None)
        os.environ['TZ'] = 'UTC0'

    class timespec(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long),
                    ("tv_nsec", ctypes.c_long)]

    CLOCK_REALTIME = 0
    nano_per_micro = 1000
    librt = ctypes.CDLL(ctypes.util.find_library("rt"))

    # seperate the microseconds part from the seconds part
    secs_part = datetime(*new_time.timetuple()[:6]).timetuple()
    micro_part = new_time.timetuple()[6]

    ts = timespec()
    ts.tv_sec = int(time.mktime(secs_part))
    ts.tv_nsec = micro_part * nano_per_micro

    # Attempt to set the clock
    result = not bool(librt.clock_settime(CLOCK_REALTIME, ctypes.byref(ts)))

    # Reset TZ environment variable
    if utc is True:
        if save_timezone is not None:
            os.environ['TZ'] = save_timezone
        else:
            del os.environ['TZ']

    return result


def _posix_set_datetime(new_date, utc=None):
    '''
    set the system date/time using the date command

    Note using a posix date binary we can only set the date up to the minute
    '''
    cmd = 'date'
    if utc is True:
        cmd += ' -u'
    # the date can be set in the following format:
    # date mmddhhmm[[cc]yy]
    cmd += " {1:02}{2:02}{3:02}{4:02}{0:04}".format(*new_date.timetuple())

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    if ret['retcode'] != 0:
        msg = 'date failed: {0}'.format(ret['stderr'])
        raise CommandExecutionError(msg)

    return True


def _try_parse_datetime(time_str, fmts):
    '''
    Attempts to parse the input time_str as a date.

    :param str time_str: A string representing the time
    :param list fmts: A list of date format strings.

    :return: Returns a datetime object if parsed properly. Otherwise None
    :rtype datetime:
    '''
    result = None
    for fmt in fmts:
        try:
            result = datetime.strptime(time_str, fmt)
            break
        except ValueError, e:
            pass
    return result


def get_system_time(utc=None):
    '''
    Get the system time.

    :param bool utc: A Boolean that indicates if the output timezone is UTC.
    :return: Returns the system time in HH:MM AM/PM format.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_time
    '''
    if utc is True:
        t = datetime.utcnow()
    else:
        t = datetime.now()
    return datetime.strftime(t, "%I:%M %p")


def set_system_time(newtime, utc=None, posix=None):
    '''
    Set the system time.

    :param str newtime:
        The time to set. Can be any of the following formats.
        - HH:MM:SS AM/PM
        - HH:MM AM/PM
        - HH:MM:SS (24 hour)
        - HH:MM (24 hour)

        Note that the salt command line parser parses the date/time
        before we obtain the argument (preventing us from doing utc)
        Therefore the argument must be passed in as a string.
        Meaning you may have to quote the text twice from the command line.

    :return: Returns True if successful. Otherwise False.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_time "'11:20'"
    '''

    fmts = ['%I:%M:%S %p', '%I:%M %p', '%H:%M:%S', '%H:%M']
    dt_obj = _try_parse_datetime(newtime, fmts)
    if dt_obj is None:
        return False

    return set_system_date_time(hours=dt_obj.hour, minutes=dt_obj.minute,
                                seconds=dt_obj.second, utc=utc, posix=posix)


def get_system_date_time(utc=None):
    '''
    Get the system date/time.

    :param bool utc: A Boolean that indicates if the output timezone is UTC.
    :return: Returns the system time in YYYY-MM-DD hh:mm:ss format.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date_time utc=True
    '''
    if utc is True:
        t = datetime.utcnow()
    else:
        t = datetime.now()

    return datetime.strftime(t, "%Y-%m-%d %H:%M:%S")


def set_system_date_time(years=None,
                         months=None,
                         days=None,
                         hours=None,
                         minutes=None,
                         seconds=None,
                         utc=None,
                         posix=None):
    '''
    Set the system date and time. Each argument is an element of the date, but
    not required. If an element is not passed, the current system value for
    that element will be used. For example, if you don't pass the year, the
    current system year will be used. (Used by set_system_date and
    set_system_time)

    :param int years: Years digit, ie: 2015
    :param int months: Months digit: 1 - 12
    :param int days: Days digit: 1 - 31
    :param int hours: Hours digit: 0 - 23
    :param int minutes: Minutes digit: 0 - 59
    :param int seconds: Seconds digit: 0 - 59
    :param bool utc: A Boolean to specify input time is UTC.
    :param bool posix: A Boolean to specify to use the posix date backend

    :return: True if successful. Otherwise False.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date_time 2015 5 12 11 37 53
    '''
    # Get the current date/time
    if utc is True:
        date_time = datetime.utcnow()
    else:
        date_time = datetime.now()

    # Check for passed values. If not passed, use current values
    if years is None:
        years = date_time.year
    if months is None:
        months = date_time.month
    if days is None:
        days = date_time.day
    if hours is None:
        hours = date_time.hour
    if minutes is None:
        minutes = date_time.minute
    if seconds is None:
        seconds = date_time.second

    dt = datetime(years, months, days, hours, minutes, seconds)
    if posix is True:
        return _posix_set_datetime(dt, utc=utc)
    else:
        return _linux_set_datetime(dt, utc=utc)


def get_system_date(utc=None):
    '''
    Get the system date

    :param bool utc: A Boolean that indicates if the output timezone is UTC.
    :return: Returns the system date.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date
    '''

    if utc is True:
        t = datetime.utcnow()
    else:
        t = datetime.now()
    return datetime.strftime(t, "%a %m/%d/%Y")


def set_system_date(newdate, utc=None):
    '''
    Set the Windows system date. Use <mm-dd-yy> format for the date.

    :param str newdate:
        The date to set. Can be any of the following formats
        - YYYY-MM-DD
        - MM-DD-YYYY
        - MM-DD-YY
        - MM/DD/YYYY
        - MM/DD/YY
        - YYYY/MM/DD

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date '03-28-13'
    '''

    fmts = ['%Y-%m-%d', '%m-%d-%Y', '%m-%d-%y',
            '%m/%d/%Y', '%m/%d/%y', '%Y/%m/%d']

    # Get date/time object from newdate
    # dt_obj = salt.utils.date_cast(newdate)
    dt_obj = _try_parse_datetime(newdate, fmts)
    if dt_obj is None:
        return False

    # Set time using set_system_date_time()
    return set_system_date_time(years=dt_obj.year, months=dt_obj.month,
                                days=dt_obj.day, utc=utc)
