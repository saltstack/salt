# -*- coding: utf-8 -*-
'''
Support for Eix
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.path


def __virtual__():
    '''
    Only work on Gentoo systems with eix installed
    '''
    if __grains__['os'] == 'Gentoo' and salt.utils.path.which('eix'):
        return 'eix'
    return (False, 'The eix execution module cannot be loaded: either the system is not Gentoo or the eix binary is not in the path.')


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
        if salt.utils.path.which('emerge-delta-webrsync'):  # We prefer 'delta-webrsync' to 'webrsync'
            cmd += ' -W'
        else:
            cmd += ' -w'
        return __salt__['cmd.retcode'](cmd) == 0
    else:
        if __salt__['cmd.retcode'](cmd) == 0:
            return True
        # We fall back to "webrsync" if "rsync" fails for some reason
        if salt.utils.path.which('emerge-delta-webrsync'):  # We prefer 'delta-webrsync' to 'webrsync'
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
