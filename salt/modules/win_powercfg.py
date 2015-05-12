# -*- coding: utf-8 -*-
'''
This module allows you to control the power settings of a windows minion via
powercfg

.. code-block:: bash

    salt '*' powercfg.set_monitor_timeout 0 power=dc
    salt '*' powercfg.set_disk_timeout 120 power=ac
'''

# Import python libs
import re
import logging

# Import salt libs

log = logging.getLogger(__name__)

__virtualname__ = "powercfg"


def __virtual__():
    '''
    Only work on Windows
    '''
    if __grains__['os'] == 'Windows':
        return __virtualname__
    return False


def _get_current_scheme():
    cmd = "powercfg /getactivescheme"
    out =  __salt__['cmd.run'](cmd, python_shell=False)
    matches = re.search(r"GUID: (.*) \(", out)
    return matches.groups()[0].strip()


def _get_powercfg_minute_values(scheme, guid, subguid):
    '''
    Returns the AC/DC values in an array for a guid and subguid for a the given scheme
    '''
    cmd = "powercfg /q {0} {1} {2}".format(scheme, guid, subguid)
    out = __salt__['cmd.run'](cmd, python_shell=False)
    raw_settings =  re.findall(r"Power Setting Index: ([0-9a-fx]+)", out)
    return {"ac": int(raw_settings[0], 0) / 60, "dc": int(raw_settings[1], 0) / 60}


def _set_powercfg_value(setting, power, value):
    '''
    Sets the value of a setting with a given power (ac/dc) to
    the current scheme
    '''
    cmd = "powercfg /x {0}-{1} {2}".format(setting, power, value)
    return __salt__['cmd.run'](cmd, python_shell=False)


def set_monitor_timeout(timeout, power="ac"):
    '''
    Set the monitor timeout in minutes for the current power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_monitor_timeout 30 power=ac

    timeout
        The amount of time in minutes before the monitor will timeout

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    '''
    return _set_powercfg_value("monitor-timeout", power, timeout)


def get_monitor_timeout():
    '''
    Get the current monitor timeout of the current scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_monitor_timeout
    '''
    return _get_powercfg_minute_values(_get_current_scheme(), "SUB_VIDEO", "VIDEOIDLE")


def set_disk_timeout(timeout, power="ac"):
    '''
    Set the disk timeout in minutes for the current power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_disk_timeout 30 power=dc

    timeout
        The amount of time in minutes before the disk will timeout

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    '''
    return _set_powercfg_value("disk-timeout", power, timeout)


def get_disk_timeout():
    '''
    Get the current disk timeout of the current scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_disk_timeout
    '''
    return _get_powercfg_minute_values(_get_current_scheme(), "SUB_DISK", "DISKIDLE")


def set_standby_timeout(timeout, power="ac"):
    '''
    Set the standby timeout in minutes for the current power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_standby_timeout 30 power=dc

    timeout
        The amount of time in minutes before the computer sleeps

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    '''
    return _set_powercfg_value("standby-timeout", power, timeout)


def get_standby_timeout():
    '''
    Get the current standby timeout of the current scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_standby_timeout
    '''
    return _get_powercfg_minute_values(_get_current_scheme(), "SUB_SLEEP", "STANDBYIDLE")


def set_hibernate_timeout(timeout, power="ac"):
    '''
    Set the hibernate timeout in minutes for the current power scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.set_hibernate_timeout 30 power=pc

    timeout
        The amount of time in minutes before the computer hibernates

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.

    '''
    return _set_powercfg_value("hibernate-timeout", power, timeout)


def get_hibernate_timeout():
    '''
    Get the current hibernate timeout of the current scheme

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_hibernate_timeout
    '''
    return _get_powercfg_minute_values(_get_current_scheme(), "SUB_SLEEP", "HIBERNATEIDLE")


