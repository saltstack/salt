# -*- coding: utf-8 -*-
"""
System module for sleeping, restarting, and shutting down the system on Mac OS X

.. versionadded:: 2016.3.0

.. warning::
    Using this module will enable ``atrun`` on the system if it is disabled.
"""
from __future__ import absolute_import, print_function, unicode_literals

import getpass

# Import salt libs
import salt.utils.platform
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import python libs
try:  # python 3
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:  # python 2
    from pipes import quote as _cmd_quote


__virtualname__ = "system"


def __virtual__():
    """
    Only for MacOS with atrun enabled
    """
    if not salt.utils.platform.is_darwin():
        return (
            False,
            "The mac_system module could not be loaded: "
            "module only works on MacOS systems.",
        )

    if getpass.getuser() != "root":
        return False, "The mac_system module is not useful for non-root users."

    if not _atrun_enabled():
        if not _enable_atrun():
            return False, "atrun could not be enabled on this system"

    return __virtualname__


def _atrun_enabled():
    """
    Check to see if atrun is running and enabled on the system
    """
    try:
        return __salt__["service.list"]("com.apple.atrun")
    except CommandExecutionError:
        return False


def _enable_atrun():
    """
    Enable and start the atrun daemon
    """
    name = "com.apple.atrun"
    try:
        __salt__["service.enable"](name)
        __salt__["service.start"](name)
    except CommandExecutionError:
        return False
    return _atrun_enabled()


def _execute_command(cmd, at_time=None):
    """
    Helper function to execute the command

    :param str cmd: the command to run

    :param str at_time: If passed, the cmd will be scheduled.

    Returns: bool
    """
    if at_time:
        cmd = "echo '{0}' | at {1}".format(cmd, _cmd_quote(at_time))
    return not bool(__salt__["cmd.retcode"](cmd, python_shell=True))


def halt(at_time=None):
    """
    Halt a running system

    :param str at_time: Any valid `at` expression. For example, some valid at
        expressions could be:

        - noon
        - midnight
        - fri
        - 9:00 AM
        - 2:30 PM tomorrow
        - now + 10 minutes

    .. note::
        If you pass a time only, with no 'AM/PM' designation, you have to
        double quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
        salt '*' system.halt 'now + 10 minutes'
    """
    cmd = "shutdown -h now"
    return _execute_command(cmd, at_time)


def sleep(at_time=None):
    """
    Sleep the system. If a user is active on the system it will likely fail to
    sleep.

    :param str at_time: Any valid `at` expression. For example, some valid at
        expressions could be:

        - noon
        - midnight
        - fri
        - 9:00 AM
        - 2:30 PM tomorrow
        - now + 10 minutes

    .. note::
        If you pass a time only, with no 'AM/PM' designation, you have to
        double quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.sleep
        salt '*' system.sleep '10:00 PM'
    """
    cmd = "shutdown -s now"
    return _execute_command(cmd, at_time)


def restart(at_time=None):
    """
    Restart the system

    :param str at_time: Any valid `at` expression. For example, some valid at
        expressions could be:

        - noon
        - midnight
        - fri
        - 9:00 AM
        - 2:30 PM tomorrow
        - now + 10 minutes

    .. note::
        If you pass a time only, with no 'AM/PM' designation, you have to
        double quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.restart
        salt '*' system.restart '12:00 PM fri'
    """
    cmd = "shutdown -r now"
    return _execute_command(cmd, at_time)


def shutdown(at_time=None):
    """
    Shutdown the system

    :param str at_time: Any valid `at` expression. For example, some valid at
        expressions could be:

        - noon
        - midnight
        - fri
        - 9:00 AM
        - 2:30 PM tomorrow
        - now + 10 minutes

    .. note::
        If you pass a time only, with no 'AM/PM' designation, you have to
        double quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown
        salt '*' system.shutdown 'now + 1 hour'
    """
    return halt(at_time)


def get_remote_login():
    """
    Displays whether remote login (SSH) is on or off.

    :return: True if remote login is on, False if off
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_remote_login
    """
    ret = __utils__["mac_utils.execute_return_result"]("systemsetup -getremotelogin")

    enabled = __utils__["mac_utils.validate_enabled"](
        __utils__["mac_utils.parse_return"](ret)
    )

    return enabled == "on"


def set_remote_login(enable):
    """
    Set the remote login (SSH) to either on or off.

    :param bool enable: True to enable, False to disable. "On" and "Off" are
        also acceptable values. Additionally you can pass 1 and 0 to represent
        True and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_remote_login True
    """
    state = __utils__["mac_utils.validate_enabled"](enable)

    cmd = "systemsetup -f -setremotelogin {0}".format(state)
    __utils__["mac_utils.execute_return_success"](cmd)

    return __utils__["mac_utils.confirm_updated"](
        state, get_remote_login, normalize_ret=True
    )


def get_remote_events():
    """
    Displays whether remote apple events are on or off.

    :return: True if remote apple events are on, False if off
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_remote_events
    """
    ret = __utils__["mac_utils.execute_return_result"](
        "systemsetup -getremoteappleevents"
    )

    enabled = __utils__["mac_utils.validate_enabled"](
        __utils__["mac_utils.parse_return"](ret)
    )

    return enabled == "on"


def set_remote_events(enable):
    """
    Set whether the server responds to events sent by other computers (such as
    AppleScripts)

    :param bool enable: True to enable, False to disable. "On" and "Off" are
        also acceptable values. Additionally you can pass 1 and 0 to represent
        True and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_remote_events On
    """
    state = __utils__["mac_utils.validate_enabled"](enable)

    cmd = "systemsetup -setremoteappleevents {0}".format(state)
    __utils__["mac_utils.execute_return_success"](cmd)

    return __utils__["mac_utils.confirm_updated"](
        state, get_remote_events, normalize_ret=True,
    )


def get_computer_name():
    """
    Gets the computer name

    :return: The computer name
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_computer_name
    """
    ret = __utils__["mac_utils.execute_return_result"]("scutil --get ComputerName")

    return __utils__["mac_utils.parse_return"](ret)


def set_computer_name(name):
    """
    Set the computer name

    :param str name: The new computer name

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_computer_name "Mike's Mac"
    """
    cmd = 'scutil --set ComputerName "{0}"'.format(name)
    __utils__["mac_utils.execute_return_success"](cmd)

    return __utils__["mac_utils.confirm_updated"](name, get_computer_name,)


def get_subnet_name():
    """
    Gets the local subnet name

    :return: The local subnet name
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_subnet_name
    """
    ret = __utils__["mac_utils.execute_return_result"](
        "systemsetup -getlocalsubnetname"
    )

    return __utils__["mac_utils.parse_return"](ret)


def set_subnet_name(name):
    """
    Set the local subnet name

    :param str name: The new local subnet name

    .. note::
       Spaces are changed to dashes. Other special characters are removed.

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        The following will be set as 'Mikes-Mac'
        salt '*' system.set_subnet_name "Mike's Mac"
    """
    cmd = 'systemsetup -setlocalsubnetname "{0}"'.format(name)
    __utils__["mac_utils.execute_return_success"](cmd)

    return __utils__["mac_utils.confirm_updated"](name, get_subnet_name,)


def get_startup_disk():
    """
    Displays the current startup disk

    :return: The current startup disk
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_startup_disk
    """
    ret = __utils__["mac_utils.execute_return_result"]("systemsetup -getstartupdisk")

    return __utils__["mac_utils.parse_return"](ret)


def list_startup_disks():
    """
    List all valid startup disks on the system.

    :return: A list of valid startup disks
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' system.list_startup_disks
    """
    ret = __utils__["mac_utils.execute_return_result"]("systemsetup -liststartupdisks")

    return ret.splitlines()


def set_startup_disk(path):
    """
    Set the current startup disk to the indicated path. Use
    ``system.list_startup_disks`` to find valid startup disks on the system.

    :param str path: The valid startup disk path

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_startup_disk /System/Library/CoreServices
    """
    if path not in list_startup_disks():
        msg = (
            "Invalid value passed for path.\n"
            "Must be a valid startup disk as found in "
            "system.list_startup_disks.\n"
            "Passed: {0}".format(path)
        )
        raise SaltInvocationError(msg)

    cmd = "systemsetup -setstartupdisk {0}".format(path)
    __utils__["mac_utils.execute_return_result"](cmd)

    return __utils__["mac_utils.confirm_updated"](path, get_startup_disk,)


def get_restart_delay():
    """
    Get the number of seconds after which the computer will start up after a
    power failure.

    :return: A string value representing the number of seconds the system will
        delay restart after power loss
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_restart_delay
    """
    ret = __utils__["mac_utils.execute_return_result"](
        "systemsetup -getwaitforstartupafterpowerfailure"
    )

    return __utils__["mac_utils.parse_return"](ret)


def set_restart_delay(seconds):
    """
    Set the number of seconds after which the computer will start up after a
    power failure.

    .. warning::

        This command fails with the following error:

        ``Error, IOServiceOpen returned 0x10000003``

        The setting is not updated. This is an apple bug. It seems like it may
        only work on certain versions of Mac Server X. This article explains the
        issue in more detail, though it is quite old.

        http://lists.apple.com/archives/macos-x-server/2006/Jul/msg00967.html

    :param int seconds: The number of seconds. Must be a multiple of 30

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_restart_delay 180
    """
    if seconds % 30 != 0:
        msg = (
            "Invalid value passed for seconds.\n"
            "Must be a multiple of 30.\n"
            "Passed: {0}".format(seconds)
        )
        raise SaltInvocationError(msg)

    cmd = "systemsetup -setwaitforstartupafterpowerfailure {0}".format(seconds)
    __utils__["mac_utils.execute_return_success"](cmd)

    return __utils__["mac_utils.confirm_updated"](seconds, get_restart_delay,)


def get_disable_keyboard_on_lock():
    """
    Get whether or not the keyboard should be disabled when the X Serve enclosure
    lock is engaged.

    :return: True if disable keyboard on lock is on, False if off
    :rtype: bool

    CLI Example:

    ..code-block:: bash

        salt '*' system.get_disable_keyboard_on_lock
    """
    ret = __utils__["mac_utils.execute_return_result"](
        "systemsetup -getdisablekeyboardwhenenclosurelockisengaged"
    )

    enabled = __utils__["mac_utils.validate_enabled"](
        __utils__["mac_utils.parse_return"](ret)
    )

    return enabled == "on"


def set_disable_keyboard_on_lock(enable):
    """
    Get whether or not the keyboard should be disabled when the X Serve
    enclosure lock is engaged.

    :param bool enable: True to enable, False to disable. "On" and "Off" are
        also acceptable values. Additionally you can pass 1 and 0 to represent
        True and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_disable_keyboard_on_lock False
    """
    state = __utils__["mac_utils.validate_enabled"](enable)

    cmd = "systemsetup -setdisablekeyboardwhenenclosurelockisengaged " "{0}".format(
        state
    )
    __utils__["mac_utils.execute_return_success"](cmd)

    return __utils__["mac_utils.confirm_updated"](
        state, get_disable_keyboard_on_lock, normalize_ret=True,
    )


def get_boot_arch():
    """
    Get the kernel architecture setting from ``com.apple.Boot.plist``

    :return: A string value representing the boot architecture setting
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_boot_arch
    """
    ret = __utils__["mac_utils.execute_return_result"](
        "systemsetup -getkernelbootarchitecturesetting"
    )

    arch = __utils__["mac_utils.parse_return"](ret)

    if "default" in arch:
        return "default"
    elif "i386" in arch:
        return "i386"
    elif "x86_64" in arch:
        return "x86_64"

    return "unknown"


def set_boot_arch(arch="default"):
    """
    Set the kernel to boot in 32 or 64 bit mode on next boot.

    .. note::
        When this function fails with the error ``changes to kernel
        architecture failed to save!``, then the boot arch is not updated.
        This is either an Apple bug, not available on the test system, or a
        result of system files being locked down in macOS (SIP Protection).

    :param str arch: A string representing the desired architecture. If no
        value is passed, default is assumed. Valid values include:

        - i386
        - x86_64
        - default

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_boot_arch i386
    """
    if arch not in ["i386", "x86_64", "default"]:
        msg = (
            "Invalid value passed for arch.\n"
            "Must be i386, x86_64, or default.\n"
            "Passed: {0}".format(arch)
        )
        raise SaltInvocationError(msg)

    cmd = "systemsetup -setkernelbootarchitecture {0}".format(arch)
    __utils__["mac_utils.execute_return_success"](cmd)

    return __utils__["mac_utils.confirm_updated"](arch, get_boot_arch,)
