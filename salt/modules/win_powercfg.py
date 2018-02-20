# -*- coding: utf-8 -*-
'''
This module allows you to control the power settings of a windows minion via
powercfg.

.. versionadded:: 2015.8.0

.. code-block:: bash

    salt '*' powercfg.set_monitor_timeout 0 power=dc
    salt '*' powercfg.set_disk_timeout 120 power=ac
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import re
import logging

log = logging.getLogger(__name__)

__virtualname__ = "powercfg"


def __virtual__():
    '''
    Only work on Windows
    '''
    if __grains__['os'] == 'Windows':
        return __virtualname__
    return (False, 'Module only works on Windows.')


def _get_current_scheme():
    cmd = "powercfg /getactivescheme"
    out = __salt__['cmd.run'](cmd, python_shell=False)
    matches = re.search(r"GUID: (.*) \(", out)
    return matches.groups()[0].strip()


def _get_powercfg_minute_values(scheme, guid, subguid, safe_name):
    '''
    Returns the AC/DC values in an array for a guid and subguid for a the given scheme
    '''
    if scheme is None:
        scheme = _get_current_scheme()

    if __grains__['osrelease'] == '7':
        cmd = "powercfg /q {0} {1}".format(scheme, guid)
    else:
        cmd = "powercfg /q {0} {1} {2}".format(scheme, guid, subguid)
    out = __salt__['cmd.run'](cmd, python_shell=False)

    split = out.split("\r\n\r\n")
    if len(split) > 1:
        for s in split:
            if safe_name in s or subguid in s:
                out = s
                break
    else:
        out = split[0]

    raw_settings = re.findall(r"Power Setting Index: ([0-9a-fx]+)", out)
    return {"ac": int(raw_settings[0], 0) / 60, "dc": int(raw_settings[1], 0) / 60}


def _set_powercfg_value(scheme, sub_group, setting_guid, power, value):
    '''
    Sets the value of a setting with a given power (ac/dc) to
    the given scheme
    '''
    if scheme is None:
        scheme = _get_current_scheme()

    cmd = "powercfg /set{0}valueindex {1} {2} {3} {4}".format(power, scheme, sub_group, setting_guid, value)
    return __salt__['cmd.run'](cmd, python_shell=False)


def set_monitor_timeout(timeout, power="ac", scheme=None):
    '''
    Set the monitor timeout in minutes for the given power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_monitor_timeout 30 power=ac

    timeout
        The amount of time in minutes before the monitor will timeout

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    scheme
        The scheme to use, leave as None to use the current.

    '''
    return _set_powercfg_value(scheme, "SUB_VIDEO", "VIDEOIDLE", power, timeout)


def get_monitor_timeout(scheme=None):
    '''
    Get the current monitor timeout of the given scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_monitor_timeout

    scheme
        The scheme to use, leave as None to use the current.
    '''
    return _get_powercfg_minute_values(scheme, "SUB_VIDEO", "VIDEOIDLE", "Turn off display after")


def set_disk_timeout(timeout, power="ac", scheme=None):
    '''
    Set the disk timeout in minutes for the given power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_disk_timeout 30 power=dc

    timeout
        The amount of time in minutes before the disk will timeout

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    scheme
        The scheme to use, leave as None to use the current.

    '''
    return _set_powercfg_value(scheme, "SUB_DISK", "DISKIDLE", power, timeout)


def get_disk_timeout(scheme=None):
    '''
    Get the current disk timeout of the given scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_disk_timeout

    scheme
        The scheme to use, leave as None to use the current.
    '''
    return _get_powercfg_minute_values(scheme, "SUB_DISK", "DISKIDLE", "Turn off hard disk after")


def set_standby_timeout(timeout, power="ac", scheme=None):
    '''
    Set the standby timeout in minutes for the given power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_standby_timeout 30 power=dc

    timeout
        The amount of time in minutes before the computer sleeps

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    scheme
        The scheme to use, leave as None to use the current.

    '''
    return _set_powercfg_value(scheme, "SUB_SLEEP", "STANDBYIDLE", power, timeout)


def get_standby_timeout(scheme=None):
    '''
    Get the current standby timeout of the given scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_standby_timeout

    scheme
        The scheme to use, leave as None to use the current.
    '''
    return _get_powercfg_minute_values(scheme, "SUB_SLEEP", "STANDBYIDLE", "Sleep after")


def set_hibernate_timeout(timeout, power="ac", scheme=None):
    '''
    Set the hibernate timeout in minutes for the given power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_hibernate_timeout 30 power=pc

    timeout
        The amount of time in minutes before the computer hibernates

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    scheme
        The scheme to use, leave as None to use the current.
    '''
    return _set_powercfg_value(scheme, "SUB_SLEEP", "HIBERNATEIDLE", power, timeout)


def get_hibernate_timeout(scheme=None):
    '''
    Get the current hibernate timeout of the given scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_hibernate_timeout

    scheme
        The scheme to use, leave as None to use the current.
    '''
    return _get_powercfg_minute_values(scheme, "SUB_SLEEP", "HIBERNATEIDLE", "Hibernate after")
