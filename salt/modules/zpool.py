# -*- coding: utf-8 -*-
'''
Module for running ZFS zpool command

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>
'''
from __future__ import absolute_import

# Import Python libs
import os
import stat
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

__func_alias__ = {
    'import_': 'import',
    'list_': 'list',
}


@decorators.memoize
def _check_zpool():
    '''
    Looks to see if zpool is present on the system
    '''
    return salt.utils.which('zpool')


@decorators.memoize
def _check_features():
    '''
    Looks to see if zpool-features is available
    '''
    # get man location
    man = salt.utils.which('man')
    if not man:
        return False

    cmd = '{man} zpool-features'.format(
        man=man
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    return res['retcode'] == 0


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
    return (False, "Module zpool: zpool not found")


def healthy():
    '''
    .. versionadded:: Boron

    Check if all zpools are healthy

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.healthy
    '''
    zpool_cmd = _check_zpool()

    cmd = '{zpool_cmd} status -x'.format(
        zpool_cmd=zpool_cmd
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    return res['stdout'] == 'all pools are healthy'


def status(zpool=None):
    '''
    .. versionchanged:: Boron

    Return the status of the named zpool

    zpool : string
        optional name of zpool to list

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.status myzpool
    '''
    ret = OrderedDict()

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} status{zpool}'.format(
        zpool_cmd=zpool_cmd,
        zpool=' {0}'.format(zpool) if zpool else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # parse zpool status data
    zp_data = {}
    current_pool = None
    current_prop = None
    for zpd in res['stdout'].splitlines():
        if zpd.strip() == '':
            continue
        if ':' in zpd:
            prop = zpd.split(':')[0].strip()
            value = zpd.split(':')[1].strip()
            if prop == 'pool' and current_pool != value:
                current_pool = value
                zp_data[current_pool] = {}
            if prop != 'pool':
                zp_data[current_pool][prop] = value

            current_prop = prop
        else:
            zp_data[current_pool][current_prop] = "{0}\n{1}".format(
                zp_data[current_pool][current_prop],
                zpd
            )

    # parse zpool config data
    for pool in zp_data:
        if 'config' not in zp_data[pool]:
            continue
        header = None
        root_vdev = None
        vdev = None
        dev = None
        config = zp_data[pool]['config']
        config_data = OrderedDict()
        for line in config.splitlines():
            if not header:
                header = line.strip().lower()
                header = [x for x in header.split(' ') if x not in ['']]
                continue

            if line[0:1] == "\t":
                line = line[1:]

            stat_data = OrderedDict()
            stats = [x for x in line.strip().split(' ') if x not in ['']]
            for prop in header:
                if prop == 'name':
                    continue
                if header.index(prop) < len(stats):
                    stat_data[prop] = stats[header.index(prop)]

            dev = line.strip().split()[0]

            if line[0:4] != '    ':
                if line[0:2] == '  ':
                    vdev = line.strip().split()[0]
                    dev = None
                else:
                    root_vdev = line.strip().split()[0]
                    vdev = None
                    dev = None

            if root_vdev:
                if root_vdev not in config_data:
                    config_data[root_vdev] = {}
                    if len(stat_data) > 0:
                        config_data[root_vdev] = stat_data
                if vdev:
                    if vdev not in config_data[root_vdev]:
                        config_data[root_vdev][vdev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev] = stat_data
                    if dev and dev not in config_data[root_vdev][vdev]:
                        config_data[root_vdev][vdev][dev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev][dev] = stat_data

        zp_data[pool]['config'] = config_data

    return zp_data


def iostat(zpool=None, sample_time=0):
    '''
    .. versionchanged:: Boron

    Display I/O statistics for the given pools

    zpool : string
        optional name of zpool to list
    sample_time : int
        seconds to capture data before output

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.iostat myzpool
    '''
    ret = OrderedDict()

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} iostat -v{zpool}{sample_time}'.format(
        zpool_cmd=zpool_cmd,
        zpool=' {0}'.format(zpool) if zpool else '',
        sample_time=' {0} 2'.format(sample_time) if sample_time else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # note: hardcoded header fields, the double header is hard to parse
    #                                capacity     operations    bandwidth
    #pool                         alloc   free   read  write   read  write
    header = [
        'pool',
        'capacity-alloc',
        'capacity-free',
        'operations-read',
        'operations-write',
        'bandwith-read',
        'bandwith-write'
    ]
    root_vdev = None
    vdev = None
    dev = None
    config_data = None
    current_pool = None
    for line in res['stdout'].splitlines():
        if line.strip() == '':
            continue

        # ignore header
        if line.startswith('pool') and line.endswith('write'):
            continue
        if line.endswith('bandwidth'):
            continue

        if line.startswith('-') and line.endswith('-'):
            if config_data:
                ret[current_pool] = config_data
            config_data = OrderedDict()
            current_pool = None
        else:
            if not isinstance(config_data, salt.utils.odict.OrderedDict):
                continue

            stat_data = OrderedDict()
            stats = [x for x in line.strip().split(' ') if x not in ['']]
            for prop in header:
                if header.index(prop) < len(stats):
                    if prop == 'pool':
                        if not current_pool:
                            current_pool = stats[header.index(prop)]
                        continue
                    if stats[header.index(prop)] == '-':
                        continue
                    stat_data[prop] = stats[header.index(prop)]

            dev = line.strip().split()[0]

            if line[0:4] != '    ':
                if line[0:2] == '  ':
                    vdev = line.strip().split()[0]
                    dev = None
                else:
                    root_vdev = line.strip().split()[0]
                    vdev = None
                    dev = None

            if root_vdev:
                if root_vdev not in config_data:
                    config_data[root_vdev] = {}
                    if len(stat_data) > 0:
                        config_data[root_vdev] = stat_data
                if vdev:
                    if vdev not in config_data[root_vdev]:
                        config_data[root_vdev][vdev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev] = stat_data
                    if dev and dev not in config_data[root_vdev][vdev]:
                        config_data[root_vdev][vdev][dev] = {}
                        if len(stat_data) > 0:
                            config_data[root_vdev][vdev][dev] = stat_data

    return ret


def zpool_list():
    '''
    .. deprecated:: 2014.7.0
       Use :py:func:`~salt.modules.zpool.list_` instead.

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
    return list_()


def list_(properties='size,alloc,free,cap,frag,health', zpool=None):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Return information about (all) zpools

    zpool : string
        optional name of zpool to list
    properties : string
        comma-separated list of properties to list

    .. note::
        the 'name' property will always be included, the 'frag' property will get removed if not available

    zpool : string
        optional zpool

    .. note::
        multiple zpools can be provded as a space seperated list

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.list
    '''
    ret = OrderedDict()

    # remove 'frag' property if not available
    properties = properties.split(',')
    if 'name' in properties:
        properties.remove('name')
    properties.insert(0, 'name')
    if not _check_features() and 'frag' in properties:
        properties.remove('frag')

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} list -H -o {properties}{zpool}'.format(
        zpool_cmd=zpool_cmd,
        properties=','.join(properties),
        zpool=' {0}'.format(zpool) if zpool else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # parse zpool list data
    for zp in res['stdout'].splitlines():
        zp = zp.split("\t")
        zp_data = {}

        for prop in properties:
            zp_data[prop] = zp[properties.index(prop)]

        ret[zp_data['name']] = zp_data
        del ret[zp_data['name']]['name']

    return ret


def get(zpool, prop=None, show_source=False):
    '''
    .. versionadded:: Boron

    Retrieves the given list of properties

    zpool : string
        name of zpool to list
    prop : string
        optional name of property to retrieve
    show_source : boolean
        show source of propery

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.get myzpool
    '''
    ret = OrderedDict()
    ret[zpool] = OrderedDict()

    properties = 'property,value,source'.split(',')

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} get -H -o {properties} {prop} {zpool}'.format(
        zpool_cmd=zpool_cmd,
        properties=','.join(properties),
        prop=prop if prop else 'all',
        zpool=zpool
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # parse zpool list data
    for zp in res['stdout'].splitlines():
        zp = zp.split("\t")
        zp_data = {}

        for prop in properties:
            zp_data[prop] = zp[properties.index(prop)]

        if show_source:
            ret[zpool][zp_data['property']] = zp_data
            del ret[zpool][zp_data['property']]['property']
        else:
            ret[zpool][zp_data['property']] = zp_data['value']

    return ret


def set(zpool, prop, value):
    '''
    .. versionadded:: Boron

    Sets the given property on the specified pool

    zpool : string
        name of zpool to list
    prop : string
        name of property
    value : string
        value to set property to

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.set myzpool readonly yes
    '''
    ret = {}
    ret[zpool] = {}
    if isinstance(value, bool):
        value = 'on' if value else 'off'
    elif ' ' in value:
        value = "'{0}'".format(value)

    # get zpool list data
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} set {prop}={value} {zpool}'.format(
        zpool_cmd=zpool_cmd,
        prop=prop,
        value=value,
        zpool=zpool
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool][prop] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool][prop] = value
    return ret


def exists(zpool):
    '''
    Check if a ZFS storage pool is active

    zpool : string
        name of zpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.exists myzpool
    '''
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} list {zpool}'.format(
        zpool_cmd=zpool_cmd,
        zpool=zpool
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        return False
    return True


def destroy(zpool):
    '''
    .. versionchanged:: Boron

    Destroys a storage pool

    zpool : string
        name of zpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.destroy myzpool
    '''
    ret = {}
    ret[zpool] = {}
    if not exists(zpool):
        ret[zpool]['error'] = 'storage pool does not exist'
    else:
        zpool_cmd = _check_zpool()
        cmd = '{zpool_cmd} destroy {zpool}'.format(
            zpool_cmd=zpool_cmd,
            zpool=zpool
        )
        res = __salt__['cmd.run_all'](cmd, python_shell=False)
        if exists(zpool):
            ret[zpool]['destroyed'] = False
            if 'stderr' in res and res['stderr'] != '':
                ret[zpool]['error'] = res['stderr']
        else:
            ret[zpool]['destroyed'] = True

    return ret


def scrub(zpool, stop=False):
    '''
    .. versionchanged:: Boron

    Scrub a zpool

    zpool : string
        name of zpool
    stop : boolean
        if true, cancel ongoing scrub

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.scrub myzpool
    '''
    ret = {}
    ret[zpool] = {}
    if exists(zpool):
        zpool_cmd = _check_zpool()
        cmd = '{zpool_cmd} scrub {stop}{zpool}'.format(
            zpool_cmd=zpool_cmd,
            stop='-s ' if stop else '',
            zpool=zpool
        )
        res = __salt__['cmd.run_all'](cmd, python_shell=False)
        ret[zpool] = {}
        if res['retcode'] != 0:
            if 'stderr' in res:
                if 'currently scrubbing' in res['stderr']:
                    ret[zpool]['scrubbing'] = True
                elif 'no active scrub' in res['stderr']:
                    ret[zpool]['scrubbing'] = False
                else:
                    ret[zpool]['scrubbing'] = False
                    ret[zpool]['error'] = res['stderr']
        else:
            ret[zpool]['scrubbing'] = True if not stop else False
    else:
        ret[zpool]['error'] = 'storage pool does not exist'

    return ret


def create(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Create a simple zpool, a mirrored zpool, a zpool having nested VDEVs, a hybrid zpool with cache, spare and log drives or a zpool with RAIDZ-1, RAIDZ-2 or RAIDZ-3

    zpool : string
        name of zpool
    * : string
        one or move devices
    force : boolean
        forces use of vdevs, even if they appear in use or specify a conflicting replication level.
    mountpoint : string
        sets the mount point for the root dataset
    altroot : string
        equivalent to "-o cachefile=none,altroot=root"

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create myzpool /path/to/vdev1 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 /path/to/vdev2 [...] [force=True|False]
        salt '*' zpool.create myzpool raidz1 /path/to/vdev1 /path/to/vdev2 raidz2 /path/to/vdev3 /path/to/vdev4 /path/to/vdev5 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 [...] mirror /path/to/vdev2 /path/to/vdev3 [...] [force=True|False]
        salt '*' zpool.create myhybridzpool mirror /tmp/file1 [...] log mirror /path/to/vdev1 [...] cache /path/to/vdev2 [...] spare /path/to/vdev3 [...] [force=True|False]

    .. note::

        Zpool properties can be specified at the time of creation of the pool by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

        Filesystem properties can be specified at the time of creation of the pool by
        passing an additional argument called "filesystem_properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            filesystem_properties="{'property1': 'value1', 'property2': 'value2'}"

        Example:

        .. code-block:: bash

            salt '*' zpool.create myzpool /path/to/vdev1 [...] properties="{'property1': 'value1', 'property2': 'value2'}"
    '''
    ret = {}
    dlist = []
    ret[zpool] = {}
    ret[zpool]['created'] = False

    # Check if the pool_name is already being used
    if exists(zpool):
        ret[zpool]['error'] = 'storage pool already exists'
        return ret

    if not vdevs:
        ret[zpool]['error'] = 'missing vdev specification'
        return ret

    # make sure files are present on filesystem
    for vdev in vdevs:
        if vdev not in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3', 'spare']:
            if not os.path.exists(vdev):
                if 'vdevs' not in ret[zpool]:
                    ret[zpool]['vdevs'] = {}
                ret[zpool]['vdevs'][vdev] = 'not present on filesystem'
                continue
            mode = os.stat(vdev).st_mode
            if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode) and not stat.S_ISCHR(mode):
                if 'vdevs' not in ret[zpool]:
                    ret[zpool]['vdevs'] = {}
                ret[zpool]['vdevs'][vdev] = 'not a block device, a file vdev or character special device'
                continue
        dlist.append(vdev)

    if 'vdevs' in ret[zpool]:
        return ret

    devs = ' '.join(dlist)
    zpool_cmd = _check_zpool()
    force = kwargs.get('force', False)
    altroot = kwargs.get('altroot', None)
    mountpoint = kwargs.get('mountpoint', None)
    properties = kwargs.get('properties', None)
    filesystem_properties = kwargs.get('filesystem_properties', None)
    cmd = '{0} create'.format(zpool_cmd)

    # apply extra arguments from kwargs
    if force:  # force creation
        cmd = '{0} -f'.format(cmd)
    if properties:  # create "-o property=value" pairs
        optlist = []
        for prop in properties:
            optlist.append('-o {0}={1}'.format(prop, properties[prop]))
        opts = ' '.join(optlist)
        cmd = '{0} {1}'.format(cmd, opts)
    if filesystem_properties:  # create "-O property=value" pairs
        optlist = []
        for prop in filesystem_properties:
            optlist.append('-O {0}={1}'.format(prop, filesystem_properties[prop]))
        opts = ' '.join(optlist)
        cmd = '{0} {1}'.format(cmd, opts)
    if mountpoint:  # set mountpoint
        cmd = '{0} -m {1}'.format(cmd, mountpoint)
    if altroot:  # set altroot
        cmd = '{0} -R {1}'.format(cmd, altroot)
    cmd = '{0} {1} {2}'.format(cmd, zpool, devs)

    # Create storage pool
    res = __salt__['cmd.run'](cmd, python_shell=False)

    # Check and see if the pools is available
    if exists(zpool):
        pvdev = None
        ret[zpool]['created'] = []
        for vdev in vdevs:
            if vdev not in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3', 'spare']:
                ret[zpool]['created'].append(vdev)
    else:
        ret[zpool]['created'] = False
        ret[zpool]['error'] = res

    return ret


def add(zpool, *vdevs, **kwargs):
    '''
    .. versionchanged:: Boron

    Add the specified vdev\'s to the given pool

    zpool : string
        name of zpool
    * : string
        one or move devices
    force : boolean
        forces use of vdevs

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.add myzpool /path/to/vdev1 /path/to/vdev2 [...]
    '''
    ret = {}
    ret[zpool] = {}
    dlist = []

    # check for pool
    if not exists(zpool):
        ret[zpool]['error'] = 'storage pool does not exist'
        return ret

    if not vdevs:
        ret[zpool]['error'] = 'missing vdev specification'
        return ret

    force = kwargs.get('force', False)

    # make sure files are present on filesystem
    for vdev in vdevs:
        if vdev not in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3', 'spare']:
            if not os.path.exists(vdev):
                if 'vdevs' not in ret[zpool]:
                    ret[zpool]['vdevs'] = {}
                ret[zpool]['vdevs'][vdev] = 'not present on filesystem'
                continue
            mode = os.stat(vdev).st_mode
            if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
                if 'vdevs' not in ret[zpool]:
                    ret[zpool]['vdevs'] = {}
                ret[zpool]['vdevs'][vdev] = 'not a block device, a file vdev or character special device'
                continue
        dlist.append(vdev)

    if 'vdevs' in ret[zpool]:
        return ret

    devs = ' '.join(dlist)

    # try and add watch out for mismatched replication levels
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} add {force}{zpool} {devs}'.format(
        zpool_cmd=zpool_cmd,
        force='-f ' if force else '',
        zpool=zpool,
        devs=devs
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool]['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        if zpool not in ret:
            ret[zpool] = {}
        ret[zpool]['added'] = dlist

    return ret


def attach(zpool, device, new_device, force=False):
    '''
    .. versionchanged:: Boron

    Attach specified device to zpool

    zpool : string
        name of zpool
    device : string
        device to attach too
    new_device : string
        device to attach
    force : boolean
        forces use of vdevs

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.attach myzpool /path/to/vdev1 /path/to/vdev2 [...]
    '''
    ret = {}
    ret[zpool] = {}
    dlist = []

    # check for pool
    if not exists(zpool):
        ret['error'] = 'storage pool does not exist'
        return ret

    # check devices
    if not os.path.exists(device):
        if 'vdevs' not in ret[zpool]:
            ret[zpool]['vdevs'] = {}
        ret[zpool]['vdevs'][device] = 'not present on filesystem'
    else:
        mode = os.stat(device).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][device] = 'not a block device, a file vdev or character special device'
    if not os.path.exists(new_device):
        if 'vdevs' not in ret[zpool]:
            ret[zpool]['vdevs'] = {}
        ret[zpool]['vdevs'][new_device] = 'not present on filesystem'
    else:
        mode = os.stat(new_device).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][new_device] = 'not a block device, a file vdev or character special device'

    if 'vdevs' in ret[zpool]:
        return ret

    # try and add watch out for mismatched replication levels
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} attach {force}{zpool} {device} {new_device}'.format(
        zpool_cmd=zpool_cmd,
        force='-f ' if force else '',
        zpool=zpool,
        device=device,
        new_device=new_device
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool]['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = {}
        ret[zpool]['attached'] = []
        ret[zpool]['attached'].append(new_device)

    return ret


def detach(zpool, device):
    '''
    .. versionchanged:: Boron

    Detach specified device to zpool

    zpool : string
        name of zpool
    device : string
        device to detach too

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.detach myzpool /path/to/vdev1
    '''
    ret = {}
    ret[zpool] = {}
    dlist = []

    # check for pool
    if not exists(zpool):
        ret[zpool]['error'] = 'storage pool does not exist'
        return ret

    # try and add watch out for mismatched replication levels
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} detach {zpool} {device}'.format(
        zpool_cmd=zpool_cmd,
        zpool=zpool,
        device=device
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool]['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = {}
        ret[zpool]['detached'] = []
        ret[zpool]['detached'].append(device)

    return ret


def replace(zpool, old_device, new_device=None, force=False):
    '''
    .. versionchanged:: Boron
    .. versionchanged:: Boron

    Replaces old_device with new_device.

    .. note::
        This is equivalent to attaching new_device,
        waiting for it to resilver, and then detaching old_device.

        The size of new_device must be greater than or equal to the minimum
        size of all the devices in a mirror or raidz configuration.

    zpool : string
        name of zpool
    old_device : string
        old device to be replaced
    new_device : string
        optional new device
    force : boolean
        Forces use of new_device, even if its appears to be in use.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.replace myzpool /path/to/vdev1 /path/to/vdev2
    '''
    ret = {}
    ret[zpool] = {}
    # Make sure pool is there
    if not exists(zpool):
        ret[zpool]['error'] = 'pool does not exists.'
        return ret

    # check devices
    if not os.path.exists(old_device):
        if 'vdevs' not in ret[zpool]:
            ret[zpool]['vdevs'] = {}
        ret[zpool]['vdevs'][old_device] = 'not present on filesystem'
    else:
        mode = os.stat(old_device).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][old_device] = 'not a block device, a file vdev or character special device'
    if not os.path.exists(new_device):
        if 'vdevs' not in ret[zpool]:
            ret[zpool]['vdevs'] = {}
        ret[zpool]['vdevs'][new_device] = 'not present on filesystem'
    else:
        mode = os.stat(new_device).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][new_device] = 'not a block device, a file vdev or character special device'

    if 'vdevs' in ret[zpool]:
        return ret

    # Replace vdevs
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} replace {force}{zpool} {old_device}{new_device}'.format(
        zpool_cmd=zpool_cmd,
        zpool=zpool,
        force='-f ' if force else '',
        old_device=old_device,
        new_device=' {0}'.format(new_device) if new_device else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool]['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool]['replaced'] = {}
        ret[zpool]['replaced'][old_device] = new_device

    return ret


@salt.utils.decorators.which('mkfile')
def create_file_vdev(size, *vdevs):
    '''
    .. versionchanged:: Boron
    .. versionchanged:: Boron

    Creates file based ``virtual devices`` for a zpool

    ``*vdevs`` is a list of full paths for mkfile to create

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create_file_vdev 7g /path/to/vdev1 [/path/to/vdev2] [...]

    .. note::

        Depending on file size, the above command may take a while to return.
    '''
    ret = {}
    dlist = []
    # Get file names to create
    for vdev in vdevs:
        # check if file is present if not add it
        if os.path.isfile(vdev):
            ret[vdev] = 'already present'
        else:
            dlist.append(vdev)

    mkfile = _check_mkfile()
    cmd = [mkfile, '{0}'.format(size)]
    cmd.extend(dlist)
    __salt__['cmd.run'](cmd, python_shell=False)

    # Makesure the files are there
    ret['status'] = True
    for vdev in vdevs:
        if not os.path.isfile(vdev):
            ret[vdev] = 'failed to create'
            ret['status'] = False
        else:
            if vdev not in ret:
                ret[vdev] = 'created'
    ret['cmd'] = ' '.join(cmd)
    return ret


def export(*pools, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Export storage pools

    * : string
        one or more zpools to export
    force : boolean
        force export of zpools

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.export myzpool ... [force=True|False]
        salt '*' zpool.export myzpool2 myzpool2 ... [force=True|False]
    '''
    ret = {}
    pool_present = []
    if not pools:
        ret['error'] = 'zpool name parameter is mandatory'
        return ret

    for pool in pools:
        if not exists(pool):
            ret[pool] = 'storage pool does not exist'
        else:
            pool_present.append(pool)

    zpool = _check_zpool()
    force = kwargs.get('force', False)
    for pool in pool_present:
        if force is True:
            cmd = '{0} export -f {1}'.format(zpool, pool)
        else:
            cmd = '{0} export {1}'.format(zpool, pool)
        res = __salt__['cmd.run'](cmd, ignore_retcode=True)
        if res:
            ret[pool] = res
        else:
            ret[pool] = 'exported'

    return ret


def import_(zpool=None, new_name=None, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Import storage pools or list pools available for import

    zpool : string
        optional name of zpool to import
    new_name : string
        optional new name for the zpool
    mntopts : string
        comma-separated list of mount options to use when mounting datasets within the pool.
    force : boolean
        forces import, even if the pool appears to be potentially active.
    altroot : string
        equivalent to "-o cachefile=none,altroot=root"

    .. note::

        Zpool properties can be specified at the time of creation of the pool by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.import [force=True|False]
        salt '*' zpool.import myzpool [mynewzpool] [force=True|False]
    '''
    ret = {}

    zpool_cmd = _check_zpool()
    force = kwargs.get('force', False)
    altroot = kwargs.get('altroot', None)
    mntopts = kwargs.get('mntopts', None)
    properties = kwargs.get('properties', None)
    cmd = '{0} import'.format(zpool_cmd)

    # apply extra arguments from kwargs
    if force:  # force creation
        cmd = '{0} -f'.format(cmd)
    if properties:  # create "-o property=value" pairs
        optlist = []
        for prop in properties:
            optlist.append('-o {0}={1}'.format(prop, properties[prop]))
        opts = ' '.join(optlist)
        cmd = '{0} {1}'.format(cmd, opts)
    if mntopts:  # set mountpoint
        cmd = '{0} -o {1}'.format(cmd, mntopts)
    if altroot:  # set altroot
        cmd = '{0} -R {1}'.format(cmd, altroot)

    cmd = '{cmd} {zpool}{new_name}'.format(
        cmd=cmd,
        zpool=' {0}'.format(zpool) if zpool else ' -a',
        new_name=' {0}'.format(new_name) if zpool and new_name else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0 and res['stderr'] != '':
        if zpool:
            ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
        else:
            ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        if zpool:
            ret[zpool if not new_name else new_name] = 'imported' if exists(zpool if not new_name else new_name) else 'not found'
        else:
            ret = True
    return ret


def online(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Ensure that the specified devices are online

    zpool : string
        name of zpool
    * : string
        one or more devices
    expand : boolean
        Expand the device to use all available space.

        .. note::
            If the device is part of a mirror or raidz then all devices must be
            expanded before the new space will become available to the pool.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.online myzpool /path/to/vdev1 [...]

    '''
    ret = {}
    ret[zpool] = {}
    dlist = []

    # Check if the pool_name exists
    if not exists(zpool):
        ret[zpool]['error'] = 'storage pool does not exist'

    if not vdevs:
        ret[zpool]['error'] = 'missing vdev specification'

    if 'error' in ret[zpool]:
        return ret

    # get expand option
    expand = kwargs.get('expand', False)

    # make sure files are present on filesystem
    for vdev in vdevs:
        if not os.path.exists(vdev):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][vdev] = 'not present on filesystem'
            continue
        mode = os.stat(vdev).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][vdev] = 'not a block device, a file vdev or character special device'
            continue
        dlist.append(vdev)

    if 'vdevs' in ret[zpool]:
        return ret

    devs = ' '.join(dlist)
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} online {expand}{zpool} {devs}'.format(
        zpool_cmd=zpool_cmd,
        expand='-e ' if expand else '',
        zpool=zpool,
        devs=devs
    )
    # Bring all specified devices online
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool]['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool]['onlined'] = dlist
    return ret


def offline(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Ensure that the specified devices are offline

    .. warning::

        By default, the OFFLINE state is persistent. The device remains offline when
        the system is rebooted. To temporarily take a device offline, use ``temporary=True``.

    zpool : string
        name of zpool
    * : string
        one or more devices
    temporary : boolean
        enable temporarily offline

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.offline myzpool /path/to/vdev1 [...] [temporary=True|False]
    '''
    ret = {}
    ret[zpool] = {}
    dlist = []

    # Check if the pool_name exists
    if not exists(zpool):
        ret[zpool]['error'] = 'storage pool does not exist'

    if not vdevs:
        ret[zpool]['error'] = 'missing vdev specification'

    if 'error' in ret[zpool]:
        return ret

    # make sure files are present on filesystem
    for vdev in vdevs:
        if not os.path.exists(vdev):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][vdev] = 'not present on filesystem'
            continue
        mode = os.stat(vdev).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            if 'vdevs' not in ret[zpool]:
                ret[zpool]['vdevs'] = {}
            ret[zpool]['vdevs'][vdev] = 'not a block device, a file vdev or character special device'
            continue
        dlist.append(vdev)

    if 'vdevs' in ret[zpool]:
        return ret

    devs = ' '.join(dlist)
    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} offline {temp}{zpool} {devs}'.format(
        zpool_cmd=zpool_cmd,
        temp='-t ' if kwargs.get('temporary', False) else '',
        zpool=zpool,
        devs=devs
    )
    # Bring all specified devices offline
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool]['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool]['offlined'] = dlist
    return ret


def reguid(zpool):
    '''
    .. verionadded:: Boron

    Generates a new unique identifier for the pool

    .. note::
        You must ensure that all devices in this pool are online
        and healthy before performing this action.

    zpool : string
        name of zpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.reguid myzpool
    '''
    ret = {}
    ret[zpool] = {}

    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} reguid {zpool}'.format(
        zpool_cmd=zpool_cmd,
        zpool=zpool
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
    else:
        ret[zpool] = 'reguided'
    return ret


def reopen(zpool):
    '''
    .. verionadded:: Boron

    Reopen all the vdevs associated with the pool

    zpool : string
        name of zpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.reopen myzpool
    '''
    ret = {}
    ret[zpool] = {}

    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} reopen {zpool}'.format(
        zpool_cmd=zpool_cmd,
        zpool=zpool
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
    else:
        ret[zpool] = 'reopened'
    return ret


def upgrade(zpool=None, version=None):
    '''
    .. verionadded:: Boron

    Enables all supported features on the given pool

    .. note::
        Once this is done, the pool will no longer be accessible on systems that do not
        support feature flags. See zpool-features(5) for details on compatibility with
        systems that support feature flags, but do not support all features enabled on the pool.

    zpool : string
        optional zpool, applies to all otherwize
    version : int
        version to upgrade to, if unspecified upgrade to the highest possible

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.upgrade myzpool
    '''
    ret = {}

    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} upgrade {version}{zpool}'.format(
        zpool_cmd=zpool_cmd,
        version='-V {0} '.format(version) if version else '',
        zpool=zpool if zpool else '-a'
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        if zpool:
            ret[zpool] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
        else:
            ret['error'] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
    else:
        if zpool:
            ret[zpool] = 'upgraded to {0}'.format('version {0}'.format(version) if version else 'the highest supported version')
        else:
            ret = 'all pools upgraded to {0}'.format('version {0}'.format(version) if version else 'the highest supported version')
    return ret


def history(zpool=None, internal=False, verbose=False):
    '''
    .. verionadded:: Boron

    Displays the command history of the specified pools or all pools if no pool is specified

    zpool : string
        optional zpool
    internal : boolean
        toggle display of internally logged ZFS events
    verbose : boolean
        toggle display of the user name, the hostname, and the zone in which the operation was performed

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.upgrade myzpool
    '''
    ret = {}

    zpool_cmd = _check_zpool()
    cmd = '{zpool_cmd} history {verbose}{internal}{zpool}'.format(
        zpool_cmd=zpool_cmd,
        verbose='-l ' if verbose else '',
        internal='-i ' if internal else '',
        zpool=zpool if zpool else ''
    )
    res = __salt__['cmd.run_all'](cmd, python_shell=False)
    if res['retcode'] != 0:
        if zpool:
            ret[zpool] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
        else:
            ret['error'] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
    else:
        pool = 'unknown'
        for line in res['stdout'].splitlines():
            if line.startswith('History for'):
                pool = line[13:-2]
                ret[pool] = []
            else:
                if line == '':
                    continue
                ret[pool].append(line)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
