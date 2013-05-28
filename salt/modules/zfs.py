'''
Module for running ZFS command
'''

# Import Python libs
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list'
}

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
    Makes sure that ZFS is available.
    '''
    if _check_zfs( ):
        return 'zfs'
    return False


def list_(*args):
    '''
    List all filesystems and volumes properties. If 'snapshot' given : list
    snapshots
    
    CLI Example::

        salt '*' zfs.list [snapshot] 
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
