# -*- coding: utf-8 -*-
'''
.. versionadded:: Boron

System module for sleeping, restarting, and shutting down the system on Mac OS
X.
'''
from __future__ import absolute_import

# Import python libs
import os
try:  # python 3
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:  # python 2
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

__virtualname__ = 'system'


def __virtual__():
    '''
    Only for MacOS with atrun enabled
    '''
    if not salt.utils.is_darwin():
        return (False, 'The mac_system module could not be loaded: '
                       'module only works on MacOS systems.')

    if not _atrun_enabled():
        if not _enable_atrun():
            return (False, 'atrun could not be enabled on this system')

    return __virtualname__


def _atrun_enabled():
    '''
    Check to see if atrun is enabled on the system
    '''
    cmd = ['launchctl list | grep atrun']
    return not bool(__salt__['cmd.retcode'](cmd, python_shell=True))


def _enable_atrun():
    '''
    Start and enable the atrun daemon
    '''
    cmd = 'launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist'
    __salt__['cmd.retcode'](cmd)
    return _atrun_enabled()


def _execute_command(cmd, at_time=None):
    '''
    Helper function to execute the command

    :param str cmd: the command to run

    :param str at_time: If passed, the cmd will be scheduled.

    Returns: bool
    '''
    if at_time:
        cmd = 'echo \'{0}\' | at {1}'.format(cmd, _cmd_quote(at_time))
    return not bool(__salt__['cmd.retcode'](cmd, python_shell=True))


def _execute_return_success(cmd):
    '''
    Helper function to execute the command
    Returns: bool
    '''
    ret = __salt__['cmd.run_all'](cmd)

    if 'not supported' in ret['stdout'].lower():
        return 'Not supported on this machine'

    if ret['retcode'] != 0:
        msg = 'Command Failed: {0}\n'.format(cmd)
        msg += 'Return Code: {0}\n'.format(ret['retcode'])
        msg += 'Output: {0}\n'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return True


def _execute_return_result(cmd):
    '''
    Helper function to execute the command
    Returns: the results of the command
    '''
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
        return dat


def _validate_enabled(enabled):
    '''
    Helper function to validate the enabled parameter. Boolean values are
    converted to "on" and "off". String values are checked to make sure they are
    either "on" or "off". All other values return an error.

    Returns: "on" or "off" or errors
    '''
    if isinstance(enabled, bool):
        if enabled:
            return 'on'
        else:
            return 'off'
    elif isinstance(enabled, int):
        if enabled in [1, 0]:
            if enabled == 1:
                return 'on'
            else:
                return 'off'
        else:
            msg = '\nMac Power: Invalid Integer Value for Enabled.\n' \
                  'Integer values must be 1 or 0.\n' \
                  'Passed: {0}'.format(enabled)
            raise SaltInvocationError(msg)
    else:
        msg = '\nMac Power: Unknown Variable Type Passed for Enabled.\n' \
              'Passed: {0}'.format(enabled)
        raise SaltInvocationError(msg)
a


def halt(at_time=None):
    '''
    Halt a running system

    :param str at_time: Any valid `at` expression. For example, some valid at
    expressions could be:
    - noon
    - midnight
    - fri
    - 9:00 AM
    - 2:30 PM tomorrow
    - now + 10 minutes

    Note::
    If you pass a time only, with no 'AM/PM' designation, you have to double
    quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
        salt '*' system.halt 'now + 10 minutes'
    '''
    cmd = 'shutdown -h now'
    return _execute_command(cmd, at_time)


def sleep(at_time=None):
    '''
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

    Note::
    If you pass a time only, with no 'AM/PM' designation, you have to double
    quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.sleep
        salt '*' system.sleep '10:00 PM'
    '''
    cmd = 'shutdown -s now'
    return _execute_command(cmd, at_time)


def restart(at_time=None):
    '''
    Restart the system

    :param str at_time: Any valid `at` expression. For example, some valid at
    expressions could be:
    - noon
    - midnight
    - fri
    - 9:00 AM
    - 2:30 PM tomorrow
    - now + 10 minutes

    Note::
    If you pass a time only, with no 'AM/PM' designation, you have to double
    quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.restart
        salt '*' system.restart '12:00 PM fri'
    '''
    cmd = 'shutdown -r now'
    return _execute_command(cmd, at_time)


def shutdown(at_time=None):
    '''
    Shutdown the system

    :param str at_time: Any valid `at` expression. For example, some valid at
    expressions could be:
    - noon
    - midnight
    - fri
    - 9:00 AM
    - 2:30 PM tomorrow
    - now + 10 minutes

    Note::
    If you pass a time only, with no 'AM/PM' designation, you have to double
    quote the parameter on the command line. For example: '"14:00"'

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown
        salt '*' system.shutdown 'now + 1 hour'
    '''
    return halt(at_time)


def get_remote_login():
    ret = _execute_return_result('systemsetup -getremotelogin')
    return _parse_return(ret)


def set_remote_login(enable):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setremotelogin {0}'.format(state)
    return _execute_return_success(cmd)


def get_remote_events():
    ret = _execute_return_result('systemsetup -getremoteappleevents')
    return _parse_return(ret)


def set_remote_events(enable):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setremoteappleevents {0}'.format(state)
    return _execute_return_success(cmd)


def get_computer_name():
    ret = _execute_return_result('systemsetup -getcomputername')
    return _parse_return(ret)


def set_computer_name(name):
    cmd = 'systemsetup -setcomputername {0}'.format(name)
    return _execute_return_success(cmd)


def get_subnet_name():
    ret = _execute_return_result('systemsetup -getlocalsubnetname')
    return _parse_return(ret)


def set_subnet_name(name):
    cmd = 'systemsetup -setlocalsubnetname {0}'.format(name)
    return _execute_return_success(cmd)


def get_startup_disk():
    ret = _execute_return_result('systemsetup -getstartupdisk')
    return _parse_return(ret)


def list_startup_disks():
    ret = _execute_return_result('systemsetup -liststartupdisks')
    return ret.splitlines()


def set_startup_disk(path):
    # TODO Validate path
    if path not in list_startup_disks():
        msg = 'Invalid value passed for path.\n' \
              'Must be a valid startup disk as found in system.list_startup_disks. \n' \
              'Passed: {0}'.format(path)
        raise CommandExecutionError(msg)
    cmd = 'systemsetup -setstartupdisk {0}'.format(path)
    return _execute_return_success(cmd)


def get_restart_delay():
    ret = _execute_return_result('systemsetup -getwaitforstartupafterpowerfailure')
    return _parse_return(ret)


def set_restart_delay(seconds):
    if seconds % 30 != 0:
        msg = 'Invalid value passed for seconds.\n' \
              'Must be a multiple of 30.\n' \
              'Passed: {0}'.format(seconds)
        raise CommandExecutionError(msg)
    cmd = 'systemsetup -setwaitforstartupafterpowerfailure {0}'.format(seconds)
    return _execute_return_success(cmd)


def get_disable_keyboard_on_lock():
    ret = _execute_return_result('systemsetup -getdisablekeyboardwhenenclosurelockisengaged')
    return _parse_return(ret)


def set_disable_keyboard_on_lock(enable):
    state = _validate_enabled(enabled)
    cmd = 'systemsetup -setdisablekeyboardwhenenclosurelockisengaged {0}'.format(state)
    return _execute_return_success(cmd)


def get_boot_arch():
    ret = _execute_return_result('systemsetup -getkernelbootarchitecturesetting')
    return _parse_return(ret)


def set_boot_arch(arch='default'):
    if arch not in ['i386', 'x86_64', 'default']:
        msg = 'Invalid value passed for arch.\n' \
              'Must be i386, x86_64, or default.\n' \
              'Passed: {0}'.format(arch)
        raise CommandExecutionError(msg)
    cmd = 'systemsetup -setkernelbootarchitecturesetting {0}'.format(arch)
    return _execute_return_success(cmd)
