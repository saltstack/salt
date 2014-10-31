# -*- coding: utf-8 -*-
'''
Module for running ZFS zpool command
'''

# Import Python libs
import os
import stat
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)

__func_alias__ = {
    'import_': 'import'
}


@decorators.memoize
def _check_zpool():
    '''
    Looks to see if zpool is present on the system
    '''
    return salt.utils.which('zpool')


@decorators.memoize
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

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.status
    '''
    zpool = _check_zpool()
    res = __salt__['cmd.run']('{0} status {1}'.format(zpool, name))
    ret = res.splitlines()
    return ret


def iostat(name=''):
    '''
    Display I/O statistics for the given pools

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.iostat
    '''
    zpool = _check_zpool()
    res = __salt__['cmd.run']('{0} iostat -v {1}'.format(zpool, name))
    ret = res.splitlines()
    return ret


def zpool_list():
    '''
    Return a list of all pools in the system with health status and space usage

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.zpool_list
    '''
    zpool = _check_zpool()
    res = __salt__['cmd.run']('{0} list'.format(zpool))
    pool_list = [l for l in res.splitlines()]
    return {'pools': pool_list}


def exists(pool_name):
    '''
    Check if a ZFS storage pool is active

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.exists myzpool
    '''
    zpool = _check_zpool()
    cmd = '{0} list {1}'.format(zpool, pool_name)
    res = __salt__['cmd.run'](cmd, ignore_retcode=True)
    if "no such pool" in res:
        return None
    return True


def destroy(pool_name):
    '''
    Destroys a storage pool

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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


def create(pool_name, *vdevs, **kwargs):
    '''
    Create a simple zpool, a mirrored zpool, a zpool having nested VDEVs, a hybrid zpool with cache and log drives or a zpool with RAIDZ-1, RAIDZ-2 or RAIDZ-3

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create myzpool /path/to/vdev1 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 /path/to/vdev2 [...] [force=True|False]
        salt '*' zpool.create myzpool raidz1 /path/to/vdev1 /path/to/vdev2 raidz2 /path/to/vdev3 /path/to/vdev4 /path/to/vdev5 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 [...] mirror /path/to/vdev2 /path/to/vdev3 [...] [force=True|False]
        salt '*' zpool.create myhybridzpool mirror /tmp/file1 [...] log mirror /path/to/vdev1 [...] cache /path/to/vdev2 [...] [force=True|False]
    '''
    ret = {}
    dlist = []

    # Check if the pool_name is already being used
    if exists(pool_name):
        ret['Error'] = 'Storage Pool `{0}` already exists'.format(pool_name)
        return ret

    # make sure files are present on filesystem
    for vdev in vdevs:
        if vdev not in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3']:
            if not os.path.exists(vdev):
                # Path doesn't exist so error and return
                ret[vdev] = '{0} not present on filesystem'.format(vdev)
                return ret
            mode = os.stat(vdev).st_mode
            if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
                # Not a block device or file vdev so error and return
                ret[vdev] = '{0} is not a block device or a file vdev'.format(vdev)
                return ret
        dlist.append(vdev)

    devs = ' '.join(dlist)
    zpool = _check_zpool()
    force = kwargs.get('force', False)
    if force is True:
        cmd = '{0} create -f {1} {2}'.format(zpool, pool_name, devs)
    else:
        cmd = '{0} create {1} {2}'.format(zpool, pool_name, devs)

    # Create storage pool
    res = __salt__['cmd.run'](cmd)

    # Check and see if the pools is available
    if exists(pool_name):
        ret[pool_name] = 'created'
        return ret
    else:
        ret['Error'] = {}
        ret['Error']['Messsage'] = 'Unable to create storage pool {0}'.format(pool_name)
        ret['Error']['Reason'] = res

    return ret


def add(pool_name, vdev):
    '''
    Add the specified vdev to the given pool

    CLI Example:

    .. code-block:: bash

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
    if 'errors' not in res.splitlines():
        ret['Added'] = '{0} to {1}'.format(vdev, pool_name)
        return ret
    ret['Error'] = 'Something went wrong add {0} to {1}'.format(vdev, pool_name)


def replace(pool_name, old, new):
    '''
    Replaces old device with new device.

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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


def export(pool_name='', force='false'):
    '''
    Export a storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.export myzpool [force=True|False]
    '''
    ret = {}
    if not pool_name:
        ret['Error'] = 'zpool name parameter is mandatory'
        return ret
    if exists(pool_name):
        zpool = _check_zpool()
        if force is True:
            cmd = '{0} export -f {1}'.format(zpool, pool_name)
        else:
            cmd = '{0} export {1}'.format(zpool, pool_name)
        __salt__['cmd.run'](cmd)
        ret[pool_name] = 'Exported'
    else:
        ret['Error'] = 'Storage pool {0} does not exist'.format(pool_name)
    return ret


def import_(pool_name='', force='false'):
    '''
    Import a storage pool or list pools available for import

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.import
        salt '*' zpool.import myzpool [force=True|False]
    '''
    ret = {}
    zpool = _check_zpool()
    if not pool_name:
        cmd = '{0} import'.format(zpool)
        res = __salt__['cmd.run'](cmd, ignore_retcode=True)
        if not res:
            ret['Error'] = 'No pools available for import'
        else:
            pool_list = [l for l in res.splitlines()]
            ret['pools'] = pool_list
        return ret
    if exists(pool_name):
        ret['Error'] = 'Storage pool {0} already exists. Import the pool under a different name instead'.format(pool_name)
    else:
        if force is True:
            cmd = '{0} import -f {1}'.format(zpool, pool_name)
        else:
            cmd = '{0} import {1}'.format(zpool, pool_name)
        res = __salt__['cmd.run'](cmd, ignore_retcode=True)
        if res:
            ret['Error'] = {}
            ret['Error']['Message'] = 'Import failed!'
            ret['Error']['Reason'] = res
        else:
            ret[pool_name] = 'Imported'
    return ret
