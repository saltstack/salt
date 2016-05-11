# -*- coding: utf-8 -*-
'''
Support for Advanced Policy Firewall (APF)
==========================================
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
    Only load if apf exists on the system
    '''
    if salt.utils.which('apf') is None:
        return (False,
                'The apf execution module cannot be loaded: apf unavailable.')
    else:
        return True


def __apf_cmd(cmd):
    '''
    Return the apf location
    '''
    apf_cmd = '{0} {1}'.format(salt.utils.which('apf'), cmd)
    out = __salt__['cmd.run_all'](apf_cmd)

    if out['retcode'] != 0:
        if not out['stderr']:
            msg = out['stdout']
        else:
            msg = out['stderr']
        raise CommandExecutionError(
            'apf failed: {0}'.format(msg)
        )
    return out['stdout']


def _status_apf():
    '''
    Return True if apf is running otherwise return False
    '''
    cmd = '{0} -L -n | grep -iom1 sanity | wc -l'.format(salt.utils.which('iptables'))
    status = __salt__['cmd.run_stdout'](cmd, python_shell=True)
    return True if status == '1' else False


def running():
    '''
    Check apf status
    CLI Example:
    .. code-block:: bash
        salt '*' apf.running
    '''
    return True if _status_apf() else False


def disable():
    '''
    Stop (flush) all firewall rules
    CLI Example:
    .. code-block:: bash
        salt '*' apf.disable
    '''
    if _status_apf():
        return __apf_cmd('-f')


def enable():
    '''
    Load all firewall rules
    CLI Example:
    .. code-block:: bash
        salt '*' apf.enable
    '''
    if not _status_apf():
        return __apf_cmd('-s')


def reload():
    '''
    Stop (flush) & reload firewall rules
    CLI Example:
    .. code-block:: bash
        salt '*' apf.reload
    '''
    if not _status_apf():
        return __apf_cmd('-r')


def refresh():
    '''
    Refresh & resolve dns names in trust rules
    CLI Example:
    .. code-block:: bash
        salt '*' apf.refresh
    '''
    return __apf_cmd('-e')


def allow(ip, port=None):
    '''
    Add host (IP/FQDN) to allow_hosts.rules and immediately load new rule into firewall
    CLI Example:
    .. code-block:: bash
        salt '*' apf.allow 127.0.0.1
    '''
    if port is None:
        return __apf_cmd('-a {0}'.format(ip))


def deny(ip):
    '''
    Add host (IP/FQDN) to deny_hosts.rules and immediately load new rule into firewall
    CLI Example:
    .. code-block:: bash
        salt '*' apf.deny 1.2.3.4
    '''
    return __apf_cmd('-d {0}'.format(ip))


def remove(ip):
    '''
    Remove host from [glob]*_hosts.rules and immediately remove rule from firewall
    CLI Example:
    .. code-block:: bash
        salt '*' apf.remove 1.2.3.4
    '''
    return __apf_cmd('-u {0}'.format(ip))
