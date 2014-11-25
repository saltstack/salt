# -*- coding: utf-8 -*-
'''
Module for running ZFS zpool command
'''
from __future__ import absolute_import

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


def list():
    '''
    Return a list of all pools in the system with health status and space usage

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.list
    '''
    zpool = _check_zpool()
    res = __salt__['cmd.run']('{0} list'.format(zpool))
    pool_list = [l for l in res.splitlines()]
    return {'pools': pool_list}


def zpool_list():
    '''
    .. deprecated:: 2014.7.0
       Use :py:func:`~salt.modules.zpool.list` instead.

    Return a list of all pools in the system with health status and space usage

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.zpool_list
    '''
    salt.utils.warn_until(
            'Boron',
            'The \'zpool_list()\' module function is being deprecated and is '
            'being renamed to \'list()\'. This function \'zpool_list()\' will be removed in '
            'Salt Boron.'
        )
    return list()


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

    .. note::

        Zpool properties can be specified at the time of creation of the pool by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

        Example:

        .. code-block:: bash

            salt '*' zpool.create myzpool /path/to/vdev1 [...] properties="{'property1': 'value1', 'property2': 'value2'}"
    '''
    ret = {}
    dlist = []

    # Check if the pool_name is already being used
    if exists(pool_name):
        ret['Error'] = 'Storage Pool `{0}` already exists'.format(pool_name)
        return ret

    if not vdevs:
        ret['Error'] = 'Missing vdev specification. Please specify vdevs.'
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
    properties = kwargs.get('properties', None)
    cmd = '{0} create'.format(zpool)

    if force:
        cmd = '{0} -f'.format(cmd)

    # if zpool properties specified, then
    # create "-o property=value" pairs
    if properties:
        optlist = []
        for property in properties:
            optlist.append('-o {0}={1}'.format(property, properties[property]))
        opts = ' '.join(optlist)
        cmd = '{0} {1}'.format(cmd, opts)
    cmd = '{0} {1} {2}'.format(cmd, pool_name, devs)

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


def export(*pools, **kwargs):
    '''
    Export storage pools

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.export myzpool ... [force=True|False]
        salt '*' zpool.export myzpool2 myzpool2 ... [force=True|False]
    '''
    ret = {}
    pool_list = []
    if not pools:
        ret['Error'] = 'zpool name parameter is mandatory'
        return ret

    for pool in pools:
        if not exists(pool):
            ret['Error'] = 'Storage pool {0} does not exist'.format(pool)
            return ret
        pool_list.append(pool)

    pools = ' '.join(pool_list)
    zpool = _check_zpool()
    force = kwargs.get('force', False)
    if force is True:
        cmd = '{0} export -f {1}'.format(zpool, pools)
    else:
        cmd = '{0} export {1}'.format(zpool, pools)
    res = __salt__['cmd.run'](cmd, ignore_retcode=True)
    if res:
        ret['Error'] = {}
        ret['Error']['Message'] = 'Import failed!'
        ret['Error']['Reason'] = res
    else:
        for pool in pool_list:
            ret[pool] = 'Exported'
    return ret


def import_(pool_name='', new_name='', **kwargs):
    '''
    Import storage pools or list pools available for import

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.import [all=True|False]
        salt '*' zpool.import myzpool [mynewzpool] [force=True|False]
    '''
    ret = {}
    zpool = _check_zpool()
    import_all = kwargs.get('all', False)
    force = kwargs.get('force', False)

    if not pool_name:
        if import_all is True:
            cmd = '{0} import -a'.format(zpool)
        else:
            cmd = '{0} import'.format(zpool)
        res = __salt__['cmd.run'](cmd, ignore_retcode=True)
        if not res and import_all is False:
            ret['Error'] = 'No pools available for import'
        elif import_all is False:
            pool_list = [l for l in res.splitlines()]
            ret['pools'] = pool_list
        else:
            ret['pools'] = 'Imported all pools'
        return ret

    if exists(pool_name) and not new_name:
        ret['Error'] = 'Storage pool {0} already exists. Import the pool under a different name instead'.format(pool_name)
    elif exists(new_name):
        ret['Error'] = 'Storage pool {0} already exists. Import the pool under a different name instead'.format(new_name)
    else:
        if force is True:
            cmd = '{0} import -f {1} {2}'.format(zpool, pool_name, new_name)
        else:
            cmd = '{0} import {1} {2}'.format(zpool, pool_name, new_name)
        res = __salt__['cmd.run'](cmd, ignore_retcode=True)
        if res:
            ret['Error'] = {}
            ret['Error']['Message'] = 'Import failed!'
            ret['Error']['Reason'] = res
        else:
            ret[pool_name] = 'Imported'
    return ret
