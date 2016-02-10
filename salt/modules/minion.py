# -*- coding: utf-8 -*-
'''
Module to provide information about minions
'''
from __future__ import absolute_import

# Import Python libs
import os

# Import Salt libs
import salt.utils
import salt.key

# Don't shadow built-ins.
__func_alias__ = {
    'list_': 'list'
}


def list_():
    '''
    Return a list of accepted, denied, unaccepted and rejected keys.
    This is the same output as `salt-key -L`

    CLI Example:

    .. code-block:: bash

        salt 'master' minion.list
    '''
    pki_dir = __salt__['config.get']('pki_dir', '')
    transport = __salt__['config.get']('transport', '')

    # We have to replace the minion/master directories
    pki_dir = pki_dir.replace('minion', 'master')

    # The source code below is (nearly) a copy of salt.key.Key.list_keys

    # We have to differentiate between RaetKey._check_minions_directories
    # and Zeromq-Keys. Raet-Keys only have three states while ZeroMQ-keys
    # have an additional 'denied' state.
    if transport in ('zeromq', 'tcp'):
        key_dirs = _check_minions_directories(pki_dir)
    else:
        key_dirs = _check_minions_directories_raetkey(pki_dir)

    ret = {}

    for dir_ in key_dirs:
        ret[os.path.basename(dir_)] = []
        try:
            for fn_ in salt.utils.isorted(os.listdir(dir_)):
                if not fn_.startswith('.'):
                    if os.path.isfile(os.path.join(dir_, fn_)):
                        ret[os.path.basename(dir_)].append(fn_)
        except (OSError, IOError):
            # key dir kind is not created yet, just skip
            continue

    return ret


def _check_minions_directories(pki_dir):
    '''
    Return the minion keys directory paths.

    This function is a copy of salt.key.Key._check_minions_directories.
    '''
    minions_accepted = os.path.join(pki_dir, salt.key.Key.ACC)
    minions_pre = os.path.join(pki_dir, salt.key.Key.PEND)
    minions_rejected = os.path.join(pki_dir, salt.key.Key.REJ)
    minions_denied = os.path.join(pki_dir, salt.key.Key.DEN)

    return minions_accepted, minions_pre, minions_rejected, minions_denied


def _check_minions_directories_raetkey(pki_dir):
    '''
    Return the minion keys directory paths.

    This function is a copy of salt.key.RaetKey._check_minions_directories.
    '''
    accepted = os.path.join(pki_dir, salt.key.RaetKey.ACC)
    pre = os.path.join(pki_dir, salt.key.RaetKey.PEND)
    rejected = os.path.join(pki_dir, salt.key.RaetKey.REJ)

    return accepted, pre, rejected


def kill():
    '''
    Kill the salt minion.

    If you have a monitor that restarts ``salt-minion`` when it dies then this is
    a great way to restart after a minion upgrade.

    CLI example::

        >$ salt minion[12] minion.kill
        minion1:
            ----------
            killed:
                7874
        minion2:
            ----------
            killed:
                29071

    The result of the salt command shows the process ID of the minions that were
    successfully killed - in this case they were ``7874`` and ``29071``.
    '''
    pid = __grains__.get('pid')
    if pid:
        if 'ps.kill_pid' in __salt__:
            __salt__['ps.kill_pid'](pid)
        else:
            pid = None
    return {'killed': pid}
