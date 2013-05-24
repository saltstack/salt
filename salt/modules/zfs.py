'''
Module for running ZFS command
'''

# Import Python libs
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

@salt.utils.memoize
def _check_zfs():
    '''
    Looks to see if zfs is present on the system
    '''
    return salt.utils.which('zfs')


def _exit_status(retcode):
    '''
    Translate exit status of zfs
    '''
    ret = { 0 : 'Successful completion.',
            1 : 'An error occurred.',
            2 : 'Usage error.'
          }[retcode]
    return ret


def __virtual__():
    '''
    Provides zfs only on supported OS
    '''
    supported = set(('Solaris', 'SmartOS', 'FreeBSD'))
    if __grains__['os'] in supported and _check_zfs():
        # Don't let this work on Solaris 9 since ZFS is not available on it.
        if __grains__['os'] == 'Solaris' and __grains__['kernelrelease'] == '5.9':
            return False
        return 'zfs'
    return False


def zfs_list(*args):
    '''
    List all filesystems and volumes properties. If 'snapshot' given : list
    snapshots
    
    CLI Example::

        salt '*' zfs.zfs_list [snapshot] 
    '''
    ret = {}
    zfs = _check_zfs()
    if len(args) == 1 and 'snapshot' in args:
        cmd = '{0} list -t snapshot'.format(zfs)
    else:
        cmd = '{0} list'.format(zfs)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    ret = res['stdout'].splitlines()
    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
