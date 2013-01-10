'''
Support for Eix

'''

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

    CLI Example::

        salt '*' eix.sync
    '''
    cmd = 'eix-sync -q'
    return __salt__['cmd.retcode'](cmd) == 0


def update():
    '''
    Update the eix database

    CLI Example::

        salt '*' eix.update
    '''
    cmd = 'eix-update --quiet'
    return __salt__['cmd.retcode'](cmd) == 0
