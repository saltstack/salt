# -*- coding: utf-8 -*-
'''
Support for Config Server Firewall (CSF)
========================================
:maintainer: Mostafa Hussein <mostafa.hussein91@gmail.com>
:maturity: new
:platform: Linux
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.utils


def __virtual__():
    '''
    Only load if csf exists on the system
    '''
    if salt.utils.which('csf') is None:
        return (False,
                'The csf execution module cannot be loaded: csf unavailable.')
    else:
        return True


def __csf_cmd(cmd):
    '''
    Return the csf location
    '''
    csf_cmd = '{0} {1}'.format(salt.utils.which('csf'), cmd)
    out = __salt__['cmd.run_all'](csf_cmd)

    if out['retcode'] != 0:
        if not out['stderr']:
            msg = out['stdout']
        else:
            msg = out['stderr']
        raise CommandExecutionError(
            'csf failed: {0}'.format(msg)
        )
    return out['stdout']


def _status_csf():
    '''
    Return True if csf is running otherwise return False
    '''
    cmd = '{0} -l | grep Chain | grep LOCALOUTPUT |wc -l'.format(salt.utils.which('csf'))
    status = __salt__['cmd.run_stdout'](cmd, python_shell=True)
    return True if status == '1' else False


def running():
    '''
    Check csf status
    CLI Example:
    .. code-block:: bash
        salt '*' csf.running
    '''
    return True if _status_csf() else False


def disable():
    '''
    Disable csf permanently
    CLI Example:
    .. code-block:: bash
        salt '*' csf.disable
    '''
    if _status_csf():
        return __csf_cmd('-x')


def enable():
    '''
    Activate csf if not running
    CLI Example:
    .. code-block:: bash
        salt '*' csf.enable
    '''
    if not _status_csf():
        return __csf_cmd('-e')


def reload():
    '''
    Restart csf
    CLI Example:
    .. code-block:: bash
        salt '*' csf.reload
    '''
    if not _status_csf():
        return __csf_cmd('-r')


def allow(ip=None, port=None):
    '''
    Add an rule to csf allowed hosts
    1- Add an IP:
    CLI Example:
    .. code-block:: bash
        salt '*' csf.allow 127.0.0.1
    '''
    if _status_csf():
        if ip is not None and port is None:
            return __csf_cmd('-a {0}'.format(ip))
