'''
zfs support.

Assumes FreeBSD

requires: mkfile
'''
import os

def __virtual__():
    '''
    FreeBSD only for now
    '''
    return 'zfs' if __grains__['os'] == 'FreeBSD' else False

def list_installed():
    '''
    returns a list of installed packages
    '''
    installed = []
    pkgs = __salt__['cmd.run']('pkg info')
    for p in pkgs.split('\n'):
        installed.append(p)
    return installed


def pool_exists(pool_name):
    '''Check if a zfs storage pool is active'''
    current_pools = zpool_list()
    for p in current_pools['pools']:
        if pool_name in p:
            return True
    return None


def zpool_list():
    '''list zpool's size and usage'''

    res = __salt__['cmd.run']('zpool list')
    pool_list = [ l for l in res.split('\n') ]
    return { 'pools' : pool_list }



def _check_mkfile():
    '''Checks if mkfile is installed if not install'''
    if 'mkfile' not in list_installed():
        # install mkfile
        __salt__['cmd.run']('make -C /usr/ports/sysutils/mkfile install \
                clean')
        return 0


def create_file_vdevice(size, *names):
    '''
    creates file based ``virtual devices`` for a zpool

    *names is a list of full paths for mkfile to create

    CLI Example::

        salt '*' zfs.create_file_vdevice 7g /disk1 /disk2

        Depending on file size this may take a while to return
    '''
    ret = {}
    # Insure mkfile is installed
    _check_mkfile()
    l = []
    # Get file names to create
    for name in names:
        # check if file is present if not add it
        if os.path.isfile(name):
            ret[name] = "File: {0} already present".format(name)
        else:
            l.append(name)

    devs = ' '.join(l)
    cmd = 'mkfile {0} {1}'.format(size, devs)
    res = __salt__['cmd.run'](cmd)

    # Makesure the files are there
    for name in names:
        if not os.path.isfile(name):
            ret[name] = "Not installed but weird it should be"
    ret['status'] = True
    ret[cmd] = cmd
    return ret


def zpool_create(pool_name, *disks):
    '''
    Create a simple storage pool

    CLI Example::

        salt '*' zfs.zpool_create myzpool /disk1 /disk2
    '''
    ret = {}
    l = []

    # Check if the pool_name is already being used
    if pool_exists(pool_name):
        ret['Error'] = "Storage Pool `{0}` already exists meow".format(pool_name)
        return ret

    # make sure files are present on filesystem
    for disk in disks:
        if not os.path.isfile(disk):
            # File is not there error and return
            ret[disk] = "{0} not present on filesystem".format(disk)
            return ret
        else:
            l.append(disk)

    devs = ' '.join(l)
    cmd = "zpool create {0} {1}".format(pool_name, devs)

    # Create storage pool
    __salt__['cmd.run'](cmd)

    # Check and see if the pools is available
    if pool_exists(pool_name):
        ret[pool_name] = "created"
        return ret
    else:
        ret['Error'] = "Unable to create storage pool {0}".format(pool_name)

    return ret


def zpool_status(name=None):
    ret = []
    res = __salt__['cmd.run']('zpool status')
    for line in res.split('\n'):
        ret.append(line)
    return ret


def zpool_destory(pool_name):
    '''
    Destorys a storage pool

    CLI Example::

        salt '*' zfs.zpool_destory myzpool
    '''
    ret = {}
    if pool_exists(pool_name):
        cmd = 'zpool destroy {0}'.format(pool_name)
        res = __salt__['cmd.run'](cmd)
        if not pool_exists(pool_name):
            ret[pool_name] = "Deleted"
            return ret
    else:
        ret['Error'] = "Storage pool {0} does not exists".format(pool_name)


def zpool_detach(zpool, device):
    '''
    Detach a device from a storage pool

    CLI Example::

        salt '*' zfs.detach myzpool /disk1
    '''
    pass


def add(pool_name, vdisk):
    '''
    Add a single device to mirror

    CLI Example::

        salt '*' zfs.add myzpool /disk2
    '''
    ret = {}
    # check for pool
    if not pool_exists(pool_name):
        ret['Error'] = 'Cant add {0} to {1} pool is not avalable'.format(pool_name, vdisk)
        return ret

    # check device is a file
    if not os.path.isfile(vdisk):
        ret['Error'] = '{0} not on filesystem'.format(vdisk)
        return ret

    # try and add watchout for mismatched replicaion levels
    cmd = 'zpool add {0} {1}'.format(pool_name, vdisk)
    res = __salt__['cmd.run'](cmd)
    if not 'errors' in res.split('\n'):
        ret['Added'] = '{0} to {1}'.format(vdisk, pool_name)
        return ret
    ret['Error'] = 'Something went wrong add {0} to {1}'.format(vdisk, pool_name)


def replace(pool_name, old, new):
    '''
    Replace a disk in a pool with another disk.

    CLI Example::

        salt '*' zfs.replace myzpool /disk1 /disk2
    '''
    ret = {}
    # Make sure pools there
    if not pool_exists(pool_name):
        ret['Error'] = '{0}: pool does not exists.'.formate(pool_name)
        return ret

    # make sure old, new disks are on filesystem
    if not os.path.isfile(old):
        ret['Error'] = '{0}: is not on the file system.'.format(old)
        return ret
    if not os.path.isfile(new):
        ret['Error'] = '{0}: is not on the file system.'.format(new)
        return ret

    # Replace disks
    cmd = "zpool replace {0} {1} {2}".format(pool_name, old, new)
    __salt__['cmd.run'](cmd)

    # check for new disk in pool
    res = zpool_status(name=pool_name)
    for line in res:
        if new in line:
            ret['replaced'] = '{0} with {1}'.format(old,new)
            return ret
    ret['Error'] = 'Does not look like devies where swaped check status'
    return ret



