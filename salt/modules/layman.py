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

    Return a list of the new overlay(s) added:

    CLI Example::

        salt '*' layman.add <overlay name>
    '''
    ret = list()
    old_overlays = list_local()
    cmd = 'layman --quietness=0 --add {0}'.format(overlay)
    __salt__['cmd.retcode'](cmd)
    new_overlays = list_local()

    ret = [overlay for overlay in new_overlays if overlay not in old_overlays]
    return ret


def delete(overlay):
    '''
    Remove the given overlay from the your locally installed overlays.
    Specify 'ALL' to remove all overlays.

    Return a list of the overlays(s) that were removed:

    CLI Example::

        salt '*' layman.delete <overlay name>
    '''
    ret = list()
    old_overlays = list_local()
    cmd = 'layman --quietness=0 --delete {0}'.format(overlay)
    __salt__['cmd.retcode'](cmd)
    new_overlays = list_local()

    ret = [overlay for overlay in old_overlays if overlay not in new_overlays]
    return ret

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
    ret = [line.split()[1] for line in out if len(line.split()) > 2]
    return ret
