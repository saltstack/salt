'''
Support for Layman

'''

import salt.utils

def __virtual__():
    '''
    Only work on Gentoo systems with layman installed
    '''
    if __grains__['os'] == 'Gentoo' and salt.utils.which('layman'):
        return 'layman'
    return False

def add(overlay):
    '''
    Add the given overlay from the caced remote list to your locally
    installed overlays. Specify 'ALL' to add all overlays from the
    remote list.

    CLI Example::

        salt '*' layman.add <overlay name>
    '''
    cmd = 'layman --quietness=0 --add {0}'.format(overlay)
    return __salt__['cmd.retcode'](cmd) == 0

def delete(overlay):
    '''
    Remove the given overlay from the your locally installed overlays.
    Specify 'ALL' to remove all overlays.

    CLI Example::

        salt '*' layman.delete <overlay name>
    '''
    cmd = 'layman --quietness=0 --delete {0}'.format(overlay)
    return __salt__['cmd.retcode'](cmd) == 0

def sync(overlay='ALL'):
    '''
    Update the specified overlay. Use 'ALL' to synchronize all overlays.
    This is the default if no overlay is specified.

    overlay
        Name of the overlay to sync. (Defaults to 'ALL')

    CLI Example::

        salt '*' layman.sync
    '''
    cmd = 'layman --quietness=0 --sync {0}'.format(overlay)
    return __salt__['cmd.retcode'](cmd) == 0

def list_local():
    '''
    List the locally installed overlays.

    Return a list of installed overlays:

    CLI Example::

        salt '*' layman.list_local
    '''
    cmd = 'layman --quietness=1 --list-local --nocolor'
    out = __salt__['cmd.run'](cmd).split('\n')
    ret = [line.split()[1] for line in out]
    return ret
