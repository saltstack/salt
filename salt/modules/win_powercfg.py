# -*- coding: utf-8 -*-
'''
This module allows you to control the power settings of a windows minion via
powercfg.

.. versionadded:: 2015.8.0

.. code-block:: bash

    # Set monitor to never turn off
    salt '*' powercfg.set_monitor_timeout 0 power=dc
    # Set disk timeout to 120 minutes
    salt '*' powercfg.set_disk_timeout 7200 power=ac
'''

# Import Python Libs
from __future__ import absolute_import
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
    Set the monitor timeout in seconds for the given power scheme

    Args:
        timeout (int):
            The amount of time in seconds before the monitor will timeout

        power (str):
            Set the value for AC or DC (battery). Valid options are:
            - ``ac`` (AC Power)
            - ``dc`` (Battery)
            Default is ``ac``

        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        str: The stdout of the powercfg command

    CLI Example:

    .. code-block:: bash

        # Sets the monitor timeout to 30 minutes
        salt '*' powercfg.set_monitor_timeout 1800
    '''
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_VIDEO",
        setting_guid="VIDEOIDLE",
        power=power,
        value=timeout)


def get_monitor_timeout(scheme=None):
    '''
    Get the current monitor timeout of the given scheme

    Args:
        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_monitor_timeout
    '''
    return _get_powercfg_minute_values(
        scheme=scheme,
        guid="SUB_VIDEO",
        subguid="VIDEOIDLE",
        safe_name="Turn off display after")


def set_disk_timeout(timeout, power="ac", scheme=None):
    '''
    Set the disk timeout in seconds for the given power scheme

    Args:
        timeout (int):
            The amount of time in seconds before the disk will timeout

        power (str):
            Set the value for AC or DC (battery). Valid options are:
            - ``ac`` (AC Power)
            - ``dc`` (Battery)
            Default is ``ac``

        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        str: The stdout of the powercfg command

    CLI Example:

    .. code-block:: bash

        # Sets the disk timeout to 30 minutes on battery
        salt '*' powercfg.set_disk_timeout 1800 power=dc
    '''
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_DISK",
        setting_guid="DISKIDLE",
        power=power,
        value=timeout)


def get_disk_timeout(scheme=None):
    '''
    Get the current disk timeout of the given scheme

    Args:
        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_disk_timeout
    '''
    return _get_powercfg_minute_values(
        scheme=scheme,
        guid="SUB_DISK",
        subguid="DISKIDLE",
        safe_name="Turn off hard disk after")


def set_standby_timeout(timeout, power="ac", scheme=None):
    '''
    Set the standby timeout in seconds for the given power scheme

    Args:
        timeout (int):
            The amount of time in seconds before the computer sleeps

        power (str):
            Set the value for AC or DC (battery). Valid options are:
            - ``ac`` (AC Power)
            - ``dc`` (Battery)
            Default is ``ac``

        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        str: The stdout of the powercfg command

    CLI Example:

    .. code-block:: bash

        # Sets the system standby timeout to 30 minutes on Battery
        salt '*' powercfg.set_standby_timeout 1800 power=dc
    '''
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_SLEEP",
        setting_guid="STANDBYIDLE",
        power=power,
        value=timeout)


def get_standby_timeout(scheme=None):
    '''
    Get the current standby timeout of the given scheme

    Args:
        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_standby_timeout
    '''
    return _get_powercfg_minute_values(
        scheme=scheme,
        guid="SUB_SLEEP",
        subguid="STANDBYIDLE",
        safe_name="Sleep after")


def set_hibernate_timeout(timeout, power="ac", scheme=None):
    '''
    Set the hibernate timeout in seconds for the given power scheme

    Args:
        timeout (int):
            The amount of time in seconds before the computer hibernates

        power (str):
            Set the value for AC or DC (battery). Valid options are:
            - ``ac`` (AC Power)
            - ``dc`` (Battery)
            Default is ``ac``

        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        str: The stdout of the powercfg command

    CLI Example:

    .. code-block:: bash

        # Sets the hibernate timeout to 30 minutes on Battery
        salt '*' powercfg.set_hibernate_timeout 1800 power=dc
    '''
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_SLEEP",
        setting_guid="HIBERNATEIDLE",
        power=power,
        value=timeout)


def get_hibernate_timeout(scheme=None):
    '''
    Get the current hibernate timeout of the given scheme

    Args:
        scheme (str):
            The scheme to use, leave as None to use the current. Default is
            ``None``

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_hibernate_timeout
    '''
    return _get_powercfg_minute_values(
        scheme=scheme,
        guid="SUB_SLEEP",
        subguid="HIBERNATEIDLE",
        safe_name="Hibernate after")
