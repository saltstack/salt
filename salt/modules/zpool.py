'''
Module for running ZFS zpool command
'''

# Import Python libs
import os
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

@salt.utils.memoize
def _check_zpool():
    '''
    Looks to see if zpool is present on the system
    '''
    return salt.utils.which('zpool')


@salt.utils.memoize
def _check_mkfile():
    '''
    Looks to see if mkfile is present on the system
    '''
    return salt.utils.which('mkfile')


def __virtual__():
    '''
    Provides zpool.
    '''
    if _check_zpool():
        return 'zpool'
    return False


def status(name=''):
    '''
    Return the status of the named zpool

    CLI Example::

        salt '*' zpool.status
    '''
    zpool = _check_zpool()
    res = __salt__['cmd.run']('{0} status {1}'.format(zpool, name))
    ret = res.splitlines()
    return ret


def iostat(name=''):
    '''
    Display I/O statistics for the given pools

    CLI Example::

        salt '*' zpool.iostat
    '''
    zpool = _check_zpool()
    res = __salt__['cmd.run']('{0} iostat -v {1}'.format(zpool, name))
    ret = res.splitlines()
    return ret


def zpool_list():
    '''
    Return a list of all pools in the system with health status and space usage

    CLI Example::

        salt '*' zpool.zpool_list
    '''
    zpool = _check_zpool()
    res = __salt__['cmd.run']('{0} list'.format(zpool))
    pool_list = [l for l in res.splitlines()]
    return {'pools': pool_list}


def exists(pool_name):
    '''
    Check if a ZFS storage pool is active

    CLI Example::

        salt '*' zpool.exists myzpool
    '''
    current_pools = zpool_list()
    for pool in current_pools['pools']:
        if pool_name in pool:
            return True
    return None


def destroy(pool_name):
    '''
    Destroys a storage pool

    CLI Example::

        salt '*' zpool.destroy myzpool
    '''
    ret = {}
    if exists(pool_name):
        zpool = _check_zpool()
        cmd = '{0} destroy {1}'.format(zpool, pool_name)
        __salt__['cmd.run'](cmd)
        if not exists(pool_name):
            ret[pool_name] = "Deleted"
            return ret
    else:
        ret['Error'] = 'Storage pool {0} does not exist'.format(pool_name)


def scrub(pool_name=None):
    '''
    Begin a scrub

    CLI Example::

        salt '*' zpool.scrub myzpool
    '''
    ret = {}
    if not pool_name:
        ret['Error'] = 'zpool name parameter is mandatory.'
        return ret
    if exists(pool_name):
        zpool = _check_zpool()
        cmd = '{0} scrub {1}'.format(zpool, pool_name)
        res = __salt__['cmd.run'](cmd)
        ret[pool_name] = res.splitlines()
        return ret
    else:
        ret['Error'] = 'Storage pool {0} does not exist'.format(pool_name)


def create(pool_name, *vdevs):
    '''
    Create a new storage pool

    CLI Example::

        salt '*' zpool.create myzpool /path/to/vdev1 [/path/to/vdev2] [...]
    '''
    ret = {}
    dlist = []

    # Check if the pool_name is already being used
    if exists(pool_name):
        ret['Error'] = 'Storage Pool `{0}` already exists'.format(pool_name)
        return ret

    # make sure files are present on filesystem
    for vdev in vdevs:
        if not os.path.isfile(vdev):
            # File is not there error and return
            ret[vdev] = '{0} not present on filesystem'.format(vdev)
            return ret
        else:
            dlist.append(vdev)

    devs = ' '.join(dlist)
    zpool = _check_zpool()
    cmd = '{0} create {1} {2}'.format(zpool, pool_name, devs)

    # Create storage pool
    __salt__['cmd.run'](cmd)

    # Check and see if the pools is available
    if exists(pool_name):
        ret[pool_name] = 'created'
        return ret
    else:
        ret['Error'] = 'Unable to create storage pool {0}'.format(pool_name)

    return ret


def add(pool_name, vdev):
    '''
    Add the specified vdev to the given pool

    CLI Example::

        salt '*' zpool.add myzpool /path/to/vdev
    '''
    ret = {}
    # check for pool
    if not exists(pool_name):
        ret['Error'] = 'Can\'t add {0} to {1} pool is not available'.format(
                pool_name,
                vdev)
        return ret

    # check device is a file
    if not os.path.isfile(vdev):
        ret['Error'] = '{0} not on filesystem'.format(vdev)
        return ret

    # try and add watch out for mismatched replication levels
    zpool = _check_zpool()
    cmd = '{0} add {1} {2}'.format(zpool, pool_name, vdev)
    res = __salt__['cmd.run'](cmd)
    if not 'errors' in res.splitlines():
        ret['Added'] = '{0} to {1}'.format(vdev, pool_name)
        return ret
    ret['Error'] = 'Something went wrong add {0} to {1}'.format(vdev, pool_name)


def replace(pool_name, old, new):
    '''
    Replaces old device with new device.

    CLI Example::

        salt '*' zpool.replace myzpool /path/to/vdev1 /path/to/vdev2
    '''
    ret = {}
    # Make sure pools there
    if not exists(pool_name):
        ret['Error'] = '{0}: pool does not exists.'.format(pool_name)
        return ret

    # make sure old, new vdevs are on filesystem
    if not os.path.isfile(old):
        ret['Error'] = '{0}: is not on the file system.'.format(old)
        return ret
    if not os.path.isfile(new):
        ret['Error'] = '{0}: is not on the file system.'.format(new)
        return ret

    # Replace vdevs
    zpool = _check_zpool()
    cmd = '{0} replace {1} {2} {3}'.format(zpool, pool_name, old, new)
    __salt__['cmd.run'](cmd)

    # check for new vdev in pool
    res = status(name=pool_name)
    for line in res:
        if new in line:
            ret['replaced'] = '{0} with {1}'.format(old, new)
            return ret
    ret['Error'] = 'Does not look like devices where swapped check status'
    return ret


def create_file_vdev(size, *vdevs):
    '''
    Creates file based ``virtual devices`` for a zpool

    ``*vdevs`` is a list of full paths for mkfile to create

    CLI Example::

        salt '*' zpool.create_file_vdev 7g /path/to/vdev1 [/path/to/vdev2] [...]

        Depending on file size this may take a while to return
    '''
    ret = {}
    if not _check_mkfile():
        return False
    dlist = []
    # Get file names to create
    for vdev in vdevs:
        # check if file is present if not add it
        if os.path.isfile(vdev):
            ret[vdev] = 'File: {0} already present'.format(vdev)
        else:
            dlist.append(vdev)

    devs = ' '.join(dlist)
    mkfile = _check_mkfile()
    cmd = '{0} {1} {2}'.format(mkfile, size, devs)
    __salt__['cmd.run'](cmd)

    # Makesure the files are there
    for vdev in vdevs:
        if not os.path.isfile(vdev):
            ret[vdev] = 'The vdev can\'t be created'
    ret['status'] = True
    ret[cmd] = cmd
    return ret
