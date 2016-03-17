# -*- coding: utf-8 -*-
'''
Helper functions for use by mac modules
.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import Python Libraries
import logging
import subprocess
import os

# Import Third Party Libs

# Import Salt Libs
import salt.utils
import salt.utils.timed_subprocess
import salt.grains.extra
from salt.exceptions import CommandExecutionError, SaltInvocationError,\
    TimedProcTimeoutError

DEFAULT_SHELL = salt.grains.extra.shell()['shell']

# Set up logging
log = logging.getLogger(__name__)

__virtualname__ = 'mac_utils'


def __virtual__():
    '''
    Load only on Mac OS
    '''
    if not salt.utils.is_darwin():
        return (False, 'The mac_utils utility could not be loaded: '
                       'utility only works on MacOS systems.')

    return __virtualname__


def _run_all(cmd):
    '''

    Args:
        cmd:

    Returns:

    '''

    run_env = os.environ.copy()

    kwargs = {'cwd': None,
              'shell': DEFAULT_SHELL,
              'env': run_env,
              'stdin': None,
              'stdout': subprocess.PIPE,
              'stderr': subprocess.PIPE,
              'with_communicate': True,
              'timeout': None,
              'bg': False,
              }

    try:
        proc = salt.utils.timed_subprocess.TimedProc(cmd, **kwargs)

    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            'Unable to run command \'{0}\' with the context \'{1}\', '
            'reason: {2}'.format(cmd, kwargs, exc)
        )

    ret = {}

    try:
        proc.run()
    except TimedProcTimeoutError as exc:
        ret['stdout'] = str(exc)
        ret['stderr'] = ''
        ret['retcode'] = 1
        ret['pid'] = proc.process.pid
        return ret

    out, err = proc.stdout, proc.stderr

    if out is not None:
        out = salt.utils.to_str(out).rstrip()
    if err is not None:
        err = salt.utils.to_str(err).rstrip()

    ret['pid'] = proc.process.pid
    ret['retcode'] = proc.process.returncode
    ret['stdout'] = out
    ret['stderr'] = err

    return ret


def execute_return_success(cmd):
    '''
    Executes the passed command. Returns True if successful

    :param str cmd: The command to run

    :return: True if successful, otherwise False
    :rtype: bool
    '''

    ret = _run_all(cmd)

    if 'not supported' in ret['stdout'].lower():
        return 'Not supported on this machine'

    if ret['retcode'] != 0:
        msg = 'Command Failed: {0}\n'.format(cmd)
        msg += 'Return Code: {0}\n'.format(ret['retcode'])
        msg += 'Output: {0}\n'.format(ret['stdout'])
        raise CommandExecutionError(msg)

    return True


def execute_return_result(cmd):
    '''
    Executes the passed command. Returns the standard out if successful

    :param str cmd: The command to run

    :return: The standard out of the command if successful, otherwise returns
    an error
    :rtype: str
    '''
    ret = _run_all(cmd)

    if ret['retcode'] != 0:
        msg = 'Command failed: {0}'.format(ret['stderr'])
        raise CommandExecutionError(msg)

    return ret['stdout']


def parse_return(data):
    '''
    Returns the data portion of a string that is colon separated.

    :param str data: The string that contains the data to be parsed. Usually the
    standard out from a command

    For example:
    ``Time Zone: America/Denver``
    will return:
    ``America/Denver``
    '''

    if ': ' in data:
        return data.split(': ')[1]
    if ':\n' in data:
        return data.split(':\n')[1]
    else:
        return data


def validate_enabled(enabled):
    '''
    Helper function to validate the enabled parameter. Boolean values are
    converted to "on" and "off". String values are checked to make sure they are
    either "on" or "off". Integer ``0`` will return "off". All other integers
    will return "on"

    :param enabled: Enabled can be boolean True or False, Integers, or string
    values "on" and "off".
    :type: str, int, bool

    :return: "on" or "off" or errors
    :rtype: str
    '''
    if isinstance(enabled, str):
        if enabled.lower() not in ['on', 'off']:
            msg = '\nMac Power: Invalid String Value for Enabled.\n' \
                  'String values must be \'on\' or \'off\'.\n' \
                  'Passed: {0}'.format(enabled)
            raise SaltInvocationError(msg)

        return enabled.lower()

    return 'on' if bool(enabled) else 'off'
