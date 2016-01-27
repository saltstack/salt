# -*- coding: utf-8 -*-
'''
.. versionadded:: Boron

System module for sleeping, restarting, and shutting down the system on Mac OS
X.
'''
from __future__ import absolute_import

# Import python libs
try:  # python 3
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:  # python 2
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils

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
