"""
This module allows you to control the power settings of a windows minion via
powercfg.

.. versionadded:: 2015.8.0

.. code-block:: bash

    # Set monitor to never turn off on Battery power
    salt '*' powercfg.set_monitor_timeout 0 power=dc
    # Set disk timeout to 120 minutes on AC power
    salt '*' powercfg.set_disk_timeout 120 power=ac
"""

import logging
import re

import salt.utils.platform

log = logging.getLogger(__name__)

__virtualname__ = "powercfg"


def __virtual__():
    """
    Only work on Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "PowerCFG: Module only works on Windows"
    return __virtualname__


def _get_current_scheme():
    cmd = "powercfg /getactivescheme"
    out = __salt__["cmd.run"](cmd, python_shell=False)
    matches = re.search(r"GUID: (.*) \(", out)
    return matches.groups()[0].strip()


def _get_powercfg_minute_values(scheme, guid, subguid, safe_name):
    """
    Returns the AC/DC values in an dict for a guid and subguid for a the given
    scheme
    """
    if scheme is None:
        scheme = _get_current_scheme()

    if __grains__["osrelease"] == "7":
        cmd = f"powercfg /q {scheme} {guid}"
    else:
        cmd = f"powercfg /q {scheme} {guid} {subguid}"
    out = __salt__["cmd.run"](cmd, python_shell=False)

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
    """
    Sets the AC/DC values of a setting with the given power for the given scheme
    """
    if scheme is None:
        scheme = _get_current_scheme()

    cmd = "powercfg /set{}valueindex {} {} {} {}".format(
        power, scheme, sub_group, setting_guid, value * 60
    )
    return __salt__["cmd.retcode"](cmd, python_shell=False) == 0


def set_monitor_timeout(timeout, power="ac", scheme=None):
    """
    Set the monitor timeout in minutes for the given power scheme

    Args:
        timeout (int):
            The amount of time in minutes before the monitor will timeout

        power (str):
            Set the value for AC or DC power. Default is ``ac``. Valid options
            are:

                - ``ac`` (AC Power)
                - ``dc`` (Battery)

        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        # Sets the monitor timeout to 30 minutes
        salt '*' powercfg.set_monitor_timeout 30
    """
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_VIDEO",
        setting_guid="VIDEOIDLE",
        power=power,
        value=timeout,
    )


def get_monitor_timeout(scheme=None):
    """
    Get the current monitor timeout of the given scheme

    Args:
        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_monitor_timeout
    """
    return _get_powercfg_minute_values(
        scheme=scheme,
        guid="SUB_VIDEO",
        subguid="VIDEOIDLE",
        safe_name="Turn off display after",
    )


def set_disk_timeout(timeout, power="ac", scheme=None):
    """
    Set the disk timeout in minutes for the given power scheme

    Args:
        timeout (int):
            The amount of time in minutes before the disk will timeout

        power (str):
            Set the value for AC or DC power. Default is ``ac``. Valid options
            are:

                - ``ac`` (AC Power)
                - ``dc`` (Battery)

        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        # Sets the disk timeout to 30 minutes on battery
        salt '*' powercfg.set_disk_timeout 30 power=dc
    """
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_DISK",
        setting_guid="DISKIDLE",
        power=power,
        value=timeout,
    )


def get_disk_timeout(scheme=None):
    """
    Get the current disk timeout of the given scheme

    Args:
        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_disk_timeout
    """
    return _get_powercfg_minute_values(
        scheme=scheme,
        guid="SUB_DISK",
        subguid="DISKIDLE",
        safe_name="Turn off hard disk after",
    )


def set_standby_timeout(timeout, power="ac", scheme=None):
    """
    Set the standby timeout in minutes for the given power scheme

    Args:
        timeout (int):
            The amount of time in minutes before the computer sleeps

        power (str):
            Set the value for AC or DC power. Default is ``ac``. Valid options
            are:

                - ``ac`` (AC Power)
                - ``dc`` (Battery)

        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        # Sets the system standby timeout to 30 minutes on Battery
        salt '*' powercfg.set_standby_timeout 30 power=dc
    """
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_SLEEP",
        setting_guid="STANDBYIDLE",
        power=power,
        value=timeout,
    )


def get_standby_timeout(scheme=None):
    """
    Get the current standby timeout of the given scheme

        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_standby_timeout
    """
    return _get_powercfg_minute_values(
        scheme=scheme, guid="SUB_SLEEP", subguid="STANDBYIDLE", safe_name="Sleep after"
    )


def set_hibernate_timeout(timeout, power="ac", scheme=None):
    """
    Set the hibernate timeout in minutes for the given power scheme

    Args:
        timeout (int):
            The amount of time in minutes before the computer hibernates

        power (str):
            Set the value for AC or DC power. Default is ``ac``. Valid options
            are:

                - ``ac`` (AC Power)
                - ``dc`` (Battery)

        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        # Sets the hibernate timeout to 30 minutes on Battery
        salt '*' powercfg.set_hibernate_timeout 30 power=dc
    """
    return _set_powercfg_value(
        scheme=scheme,
        sub_group="SUB_SLEEP",
        setting_guid="HIBERNATEIDLE",
        power=power,
        value=timeout,
    )


def get_hibernate_timeout(scheme=None):
    """
    Get the current hibernate timeout of the given scheme

        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    Returns:
        dict: A dictionary of both the AC and DC settings

    CLI Example:

    .. code-block:: bash

        salt '*' powercfg.get_hibernate_timeout
    """
    return _get_powercfg_minute_values(
        scheme=scheme,
        guid="SUB_SLEEP",
        subguid="HIBERNATEIDLE",
        safe_name="Hibernate after",
    )
