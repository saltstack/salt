# -*- coding: utf-8 -*-
'''
Support for Eix
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only work on Gentoo systems with eix installed
    '''
    if __grains__['os'] == 'Gentoo' and salt.utils.which('eix'):
        return 'eix'
    return False


def sync():
    '''
    Sync portage/overlay trees and update the eix database

    CLI Example:

    .. code-block:: bash

        salt '*' eix.sync
    '''
    cmd = 'eix-sync -q -C "--ask" -C "n"'
    if 'makeconf.features_contains'in __salt__ and __salt__['makeconf.features_contains']('webrsync-gpg'):
        # GPG sign verify is supported only for "webrsync"
        if salt.utils.which('emerge-delta-webrsync'):  # We prefer 'delta-webrsync' to 'webrsync'
            cmd += ' -W'
        else:
            cmd += ' -w'
        return __salt__['cmd.retcode'](cmd) == 0
    else:
        if __salt__['cmd.retcode'](cmd) == 0:
            return True
        # We fall back to "webrsync" if "rsync" fails for some reason
        if salt.utils.which('emerge-delta-webrsync'):  # We prefer 'delta-webrsync' to 'webrsync'
            cmd += ' -W'
        else:
            cmd += ' -w'
        return __salt__['cmd.retcode'](cmd) == 0


def update():
    '''
    Update the eix database

    CLI Example:

    .. code-block:: bash

        salt '*' eix.update
    '''
    cmd = 'eix-update --quiet'
    return __salt__['cmd.retcode'](cmd) == 0
