# -*- coding: utf-8 -*-
'''
Module for running ZFS zpool command

:codeauthor:    Nitin Madhok <nmadhok@clemson.edu>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs
:platform:      illumos,freebsd,linux
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import os
import stat
import logging

# Import Salt libs
import salt.utils.decorators
import salt.utils.decorators.path
import salt.utils.path
from salt.utils.odict import OrderedDict
from salt.modules.zfs import _conform_value

log = logging.getLogger(__name__)

__virtualname__ = 'zpool'
__func_alias__ = {
    'import_': 'import',
    'list_': 'list',
}


def __virtual__():
    '''
    Only load when the platform has zfs support
    '''
    if __grains__['zfs_support']:
        return __virtualname__
    else:
        return (False, "The zpool module cannot be loaded: zfs not supported")


def healthy():
    '''
    .. versionadded:: 2016.3.0

    Check if all zpools are healthy

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.healthy
    '''
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='status',
            flags=['-x'],
        ),
        python_shell=False,
    )
    return res['stdout'] == 'all pools are healthy'


def status(zpool=None):
    '''
    .. versionchanged:: 2016.3.0

    Return the status of the named zpool

    zpool : string
        optional name of storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.status myzpool
    '''
    ret = OrderedDict()

    # get zpool list data
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='status',
            target=zpool,
        ),
        python_shell=False,
    )
    if res['retcode'] != 0:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']
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
            value = ":".join(zpd.split(':')[1:]).strip()
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


def iostat(zpool=None, sample_time=5):
    '''
    .. versionchanged:: 2016.3.0

    Display I/O statistics for the given pools

    zpool : string
        optional name of storage pool
    sample_time : int
        seconds to capture data before output
        default a sample of 5 seconds is used

        .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.iostat myzpool
    '''
    ret = OrderedDict()

    # get zpool list data
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='iostat',
            flags=['-v'],
            target=[zpool, sample_time, 2]
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']
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
                if not config_data.get(root_vdev):
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


def list_(properties='size,alloc,free,cap,frag,health', zpool=None, parsable=False):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Oxygen

    Return information about (all) storage pools

    zpool : string
        optional name of storage pool
    properties : string
        comma-separated list of properties to display
    parsable : boolean
        display numbers in parsable (exact) values
        .. versionadded:: Oxygen

    .. note::
        the 'name' property will always be included, the 'frag' property will get removed if not available

    zpool : string
        optional zpool

    .. note::
        multiple storage pool can be provded as a space separated list

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.list
        salt '*' zpool.list zpool=tank
        salt '*' zpool.list 'size,free'
        salt '*' zpool.list 'size,free' tank
    '''
    ret = OrderedDict()

    # remove 'frag' property if not available
    if not isinstance(properties, list):
        properties = properties.split(',')
    while 'name' in properties:
        properties.remove('name')
    properties.insert(0, 'name')
    if not __utils__['zfs.has_feature_flags']():
        while 'frag' in properties:
            properties.remove('frag')

    # get zpool list data
    ## FIXME: we now always get parsable output... handle this during parsing instead
    ##        !! fix test input also !!
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='list',
            flags=['-H', '-p'],
            opts={'-o': ','.join(properties)},
            target=zpool
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # parse zpool list data
    for zp in res['stdout'].splitlines():
        zp = zp.split("\t")
        zp_data = {}

        for prop in properties:
            zp_data[prop] = _conform_value(zp[properties.index(prop)])

        ret[zp_data['name']] = zp_data
        del ret[zp_data['name']]['name']

    return ret


def get(zpool, prop=None, show_source=False, parsable=False):
    '''
    .. versionadded:: 2016.3.0
    .. versionchanged: Oxygen

    Retrieves the given list of properties

    zpool : string
        name of storage pool
    prop : string
        optional name of property to retrieve
    show_source : boolean
        show source of property
    parsable : boolean
        display numbers in parsable (exact) values
        .. versionadded:: Oxygen

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.get myzpool
    '''
    ret = OrderedDict()
    ret[zpool] = OrderedDict()
    value_properties = ['property', 'value', 'source']

    # get zpool list data
    ## FIXME: we now always get parsable output... handle this during parsing instead
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='get',
            flags=['-H', '-p'],
            opts={'-o': ','.join(value_properties)},
            property_name=prop if prop else 'all',
            target=zpool,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']
        return ret

    # parse zpool list data
    for zp in res['stdout'].splitlines():
        zp = zp.split("\t")
        zp_data = {}

        for prop in value_properties:
            zp_data[prop] = _conform_value(zp[value_properties.index(prop)])

        if show_source:
            ret[zpool][zp_data['property']] = zp_data
            del ret[zpool][zp_data['property']]['property']
        else:
            ret[zpool][zp_data['property']] = zp_data['value']

    return ret


def set(zpool, prop, value):
    '''
    .. versionadded:: 2016.3.0

    Sets the given property on the specified pool

    zpool : string
        name of storage pool
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

    # make sure value is what zfs expects
    value = _conform_value(value)

    # get zpool list data
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='set',
            property_name=prop,
            property_value=value,
            target=zpool,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[zpool][prop] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool][prop] = value
    return ret


def exists(zpool):
    '''
    Check if a ZFS storage pool is active

    zpool : string
        name of storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.exists myzpool
    '''
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='list',
            target=zpool,
        ),
        python_shell=False,
        ignore_retcode=True,
    )
    if res['retcode'] != 0:
        return False
    return True


def destroy(zpool, force=False):
    '''
    .. versionchanged:: 2016.3.0

    Destroys a storage pool

    zpool : string
        name of storage pool
    force : boolean
        force destroy of pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.destroy myzpool
    '''
    ret = {}
    ret[zpool] = {}
    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exist'
    else:
        res = __salt__['cmd.run_all'](
            __utils__['zfs.zpool_command'](
                command='destroy',
                flags=['-f'] if force else None,
                target=zpool,
            ),
            python_shell=False,
        )

        if res['retcode'] != 0:
            ret[zpool] = 'error destroying storage pool'
            if 'stderr' in res and res['stderr'] != '':
                ret[zpool] = res['stderr']
        else:
            ret[zpool] = 'destroyed'

    return ret


def scrub(zpool, stop=False, pause=False):
    '''
    .. versionchanged:: 2016.3.0

    Scrub a storage pool

    zpool : string
        name of storage pool
    stop : boolean
        if true, cancel ongoing scrub
    pause : boolean
        if true, pause ongoing scrub
        .. versionadded:: Oxygen

        .. note::

            If both pause and stop are true, stop will win.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.scrub myzpool
    '''
    ret = {}
    ret[zpool] = {}
    if __salt__['zpool.exists'](zpool):
        action = []
        if stop:
            action.append('-s')
        elif pause:
            # NOTE: https://github.com/openzfs/openzfs/pull/407
            action.append('-p')
        res = __salt__['cmd.run_all'](
            __utils__['zfs.zpool_command'](
                command='scrub',
                flags=action,
                target=zpool,
            ),
            python_shell=False,
        )
        ret[zpool] = {}
        if res['retcode'] != 0:
            ret[zpool]['scrubbing'] = False
            if 'stderr' in res:
                if 'currently scrubbing' in res['stderr']:
                    ret[zpool]['scrubbing'] = True
                elif 'no active scrub' not in res['stderr']:
                    ret[zpool]['error'] = res['stderr']
            else:
                ret[zpool]['error'] = res['stdout']
        else:
            if stop:
                ret[zpool]['scrubbing'] = False
            elif pause:
                ret[zpool]['scrubbing'] = False
            else:
                ret[zpool]['scrubbing'] = True
    else:
        ret[zpool] = 'storage pool does not exist'

    return ret


def create(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2016.3.0

    Create a simple zpool, a mirrored zpool, a zpool having nested VDEVs, a hybrid zpool with cache, spare and log drives or a zpool with RAIDZ-1, RAIDZ-2 or RAIDZ-3

    zpool : string
        name of storage pool
    *vdevs : string
        one or move devices
    force : boolean
        forces use of vdevs, even if they appear in use or specify a conflicting replication level.
    mountpoint : string
        sets the mount point for the root dataset
    altroot : string
        equivalent to "-o cachefile=none,altroot=root"
    properties : dict
        additional pool properties
    filesystem_properties : dict
        additional filesystem properties
    createboot : boolean
        ..versionadded:: Oxygen
        create a boot partition

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

    # Check if the pool_name is already being used
    if __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool already exists'
        return ret

    if not vdevs:
        ret[zpool] = 'no devices specified'
        return ret

    # Initialize defaults
    flags = []
    opts = {}
    target = []

    # Set pool and fs properties
    pool_properties = kwargs.get('properties', None)
    filesystem_properties = kwargs.get('filesystem_properties', None)

    if kwargs.get('force', False):
        flags.append('-f')
    if kwargs.get('createboot', False) or 'bootsize' in pool_properties:
        flags.append('-B')
    if kwargs.get('altroot', False):
        opts['-R'] = kwargs.get('altroot')
    if kwargs.get('mountpoint', False):
        opts['-m'] = kwargs.get('mountpoint')
    target.append(zpool)
    target.extend(vdevs)

    # Create storage pool
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='create',
            flags=flags,
            opts=opts,
            pool_properties=pool_properties,
            filesystem_properties=filesystem_properties,
            target=target,
        ),
        python_shell=False,
    )

    # Check and see if the pools is available
    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = 'created with {0}'.format(' '.join(vdevs))

    return ret


def add(zpool, *vdevs, **kwargs):
    '''
    .. versionchanged:: 2016.3.0

    Add the specified vdev\'s to the given storage pool

    zpool : string
        name of storage pool
    *vdevs : string
        one or more devices
    force : boolean
        forces use of device

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.add myzpool /path/to/vdev1 /path/to/vdev2 [...]
    '''
    ret = {}

    # validate parameters
    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exist'
        return ret

    if not vdevs:
        ret[zpool] = 'no devices specified'
        return ret

    # try and add vdev
    # NOTE: watch out for mismatched replication levels
    flags = []
    target = []

    if kwargs.get('force', False):
        flags.append('-f')
    target.append(zpool)
    target.extend(vdevs)

    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='add',
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = 'added {0}'.format(' '.join(vdevs))

    return ret


def attach(zpool, device, new_device, force=False):
    '''
    .. versionchanged:: 2016.3.0

    Attach specified device to zpool

    zpool : string
        name of storage pool
    device : string
        device to attach too
    new_device : string
        device to attach
    force : boolean
        forces use of device

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.attach myzpool /path/to/vdev1 /path/to/vdev2 [...]
    '''
    ret = {}
    dlist = []

    # check for pool
    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exist'
        return ret

    # check devices
    ret[zpool] = {}
    if not os.path.exists(device):
        ret[zpool][device] = 'not present on filesystem'
    else:
        mode = os.stat(device).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            ret[zpool][device] = 'not a block device, a file vdev or character special device'
    if not os.path.exists(new_device):
        ret[zpool][new_device] = 'not present on filesystem'
    else:
        mode = os.stat(new_device).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
            ret[zpool][new_device] = 'not a block device, a file vdev or character special device'

    if len(ret[zpool]) > 0:
        return ret

    # try and attach
    # NOTE: watch out for mismatched replication levels
    flags = []
    target = []

    if force:
        flags.append('-f')
    target.append(zpool)
    target.append(device)
    target.append(new_device)

    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='attach',
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = {}
        ret[zpool][new_device] = 'attached'

    return ret


def detach(zpool, device):
    '''
    .. versionchanged:: 2016.3.0

    Detach specified device to zpool

    zpool : string
        name of storage pool
    device : string
        device to detach

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.detach myzpool /path/to/vdev1
    '''
    ret = {}
    dlist = []

    # check for pool
    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exist'
        return ret

    # try and detach
    # NOTE: watch out for mismatched replication levels
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='detach',
            target=[zpool, device],
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = {}
        ret[zpool][device] = 'detached'

    return ret


def split(zpool, newzpool, **kwargs):
    '''
    .. versionadded:: Oxygen

    Splits devices off pool creating newpool.

    .. note::

        All vdevs in pool must be mirrors.  At the time of the split,
        newpool will be a replica of pool.

    zpool : string
        name of storage pool
    newzpool : string
        name of new storage pool
    mountpoint : string
        sets the mount point for the root dataset
    altroot : string
        sets altroot for newzpool
    properties : dict
        additional pool properties for newzpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.split datamirror databackup
        salt '*' zpool.split datamirror databackup altroot=/backup

    .. note::

        Zpool properties can be specified at the time of creation of the pool by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

        Example:

        .. code-block:: bash

            salt '*' zpool.split datamirror databackup properties="{'readonly': 'on'}"
    '''
    ret = {}

    # Check if the pool_name is already being used
    if __salt__['zpool.exists'](newzpool):
        ret[newzpool] = 'storage pool already exists'
        return ret

    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exists'
        return ret

    opts = {}
    pool_properties = kwargs.get('properties', None)
    if kwargs.get('altroot', False):
        opts['-R'] = kwargs.get('altroot')

    # Create storage pool
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='split',
            opts=opts,
            pool_properties=pool_properties,
            target=[zpool, newzpool],
        ),
        python_shell=False,
    )

    # Check and see if the pools is available
    if res['retcode'] != 0:
        ret[newzpool] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[newzpool] = 'split off from {}'.format(zpool)

    return ret


def replace(zpool, old_device, new_device=None, force=False):
    '''
    .. versionchanged:: 2016.3.0

    Replaces old_device with new_device.

    .. note::
        This is equivalent to attaching new_device,
        waiting for it to resilver, and then detaching old_device.

        The size of new_device must be greater than or equal to the minimum
        size of all the devices in a mirror or raidz configuration.

    zpool : string
        name of storage pool
    old_device : string
        old device to replace
    new_device : string
        optional new device
    force : boolean
        Forces use of new_device, even if its appears to be in use.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.replace myzpool /path/to/vdev1 /path/to/vdev2
    '''
    ret = {}
    # Make sure pool is there
    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exist'
        return ret

    # check devices
    ret[zpool] = {}
    if not new_device:  # if we have a new device, old_device is probably missing!
        if not os.path.exists(old_device):
            ret[zpool][old_device] = 'not present on filesystem'
        else:
            mode = os.stat(old_device).st_mode
            if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
                ret[zpool][old_device] = 'not a block device, a file vdev or character special device'

    if new_device:  # if we are replacing a device in the same slot, new device can be None
        if not os.path.exists(new_device):
            ret[zpool][new_device] = 'not present on filesystem'
        else:
            mode = os.stat(new_device).st_mode
            if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode):
                ret[zpool][new_device] = 'not a block device, a file vdev or character special device'

    if len(ret[zpool]) > 0:
        return ret

    # Replace vdevs
    flags = []
    target = []

    if force:
        flags.append('-f')
    target.append(zpool)
    target.append(old_device)
    if new_device:
        target.append(new_device)

    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='replace',
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
    elif new_device:
        ret[zpool] = 'replaced {0} with {1}'.format(old_device, new_device)
    else:
        ret[zpool] = 'replaced {0}'.format(old_device)

    return ret


@salt.utils.decorators.path.which('mkfile')
def create_file_vdev(size, *vdevs):
    '''
    .. versionchanged:: 2016.3.0

    Creates file based ``virtual devices`` for a zpool

    ``*vdevs`` is a list of full paths for mkfile to create

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create_file_vdev 7G /path/to/vdev1 [/path/to/vdev2] [...]

    .. note::

        Depending on file size, the above command may take a while to return.
    '''
    ret = {}
    dlist = []
    # Get file names to create
    for vdev in vdevs:
        # check if file is present if not add it
        if os.path.isfile(vdev):
            ret[vdev] = 'existed'
        else:
            dlist.append(vdev)

    _mkfile_cmd = salt.utils.path.which('mkfile')
    for vdev in dlist:
        res = __salt__['cmd.run_all'](
            '{mkfile} {size} {vdev}'.format(
                mkfile=_mkfile_cmd,
                size=size,
                vdev=vdev,
            ),
            python_shell=False,
        )
        ret[vdev] = 'failed'
        if res['retcode'] != 0:
            if 'stderr' in res and ':' in res['stderr']:
                ret[vdev] = 'failed: {reason}'.format(
                    reason=res['stderr'].split(': ')[-1],
                )
        elif os.path.isfile(vdev):
            ret[vdev] = 'created'

    return ret


def export(*pools, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2016.3.0

    Export storage pools

    *pools : string
        one or more storage pools to export
    force : boolean
        force export of storage pools

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.export myzpool ... [force=True|False]
        salt '*' zpool.export myzpool2 myzpool2 ... [force=True|False]
    '''
    ret = {}
    pool_present = []
    if not pools:
        ret['error'] = 'atleast one storage pool must be specified'
        return ret

    for pool in pools:
        if not __salt__['zpool.exists'](pool):
            ret[pool] = 'storage pool does not exist'
        else:
            pool_present.append(pool)

    flags = []

    if kwargs.get('force', False):
        flags.append('-f')

    for pool in pool_present:
        res = __salt__['cmd.run_all'](
            __utils__['zfs.zpool_command'](
                command='export',
                flags=flags,
                target=pool,
            ),
            python_shell=False,
        )
        if res['retcode'] != 0:
            ret[pool] = res['stderr'] if 'stderr' in res else res['stdout']
        else:
            ret[pool] = 'exported'

    return ret


def import_(zpool=None, new_name=None, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2016.3.0

    Import storage pools or list pools available for import

    zpool : string
        optional name of storage pool
    new_name : string
        optional new name for the storage pool
    mntopts : string
        comma-separated list of mount options to use when mounting datasets within the pool.
    force : boolean
        forces import, even if the pool appears to be potentially active.
    altroot : string
        equivalent to "-o cachefile=none,altroot=root"
    dir : string
        searches for devices or files in dir, multiple dirs can be specified as follows:: dir="dir1,dir2"
    no_mount : boolean
        import the pool without mounting any file systems.
    only_destroyed : boolean
        imports destroyed pools only. this also sets force=True.
    properties : dict
        additional pool properties

    .. note::

        Zpool properties can be specified at the time of creation of the pool by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.import [force=True|False]
        salt '*' zpool.import myzpool [mynewzpool] [force=True|False]
        salt '*' zpool.import myzpool dir='/tmp'
    '''
    ret = {}

    ## initialize defaults
    flags = []
    opts = {}
    target = []

    ## build flags and options
    if kwargs.get('force', False):
        flags.append('-f')
    if kwargs.get('no_mount', False):
        flags.append('-N')
    if kwargs.get('only_destroyed', False):
        if '-f' not in flags:
            flags.append('-f')
        flags.append('-D')
    if not zpool:
        flags.append('-a')
    else:
        target.append(zpool)
    if zpool and new_name:
        target.append(new_name)
    if kwargs.get('altroot', False):
        opts['-R'] = kwargs.get('altroot')
    if kwargs.get('mntopts', False):
        opts['-o'] = kwargs.get('mntopts')
    for d in kwargs.get('dir', '').split(','):
        if '-d' not in opts:
            opts['-d'] = []
        opts['-d'].append(d)

    ## pool properties
    pool_properties = kwargs.get('properties', None)

    ## execute import
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='import',
            flags=flags,
            opts=opts,
            pool_properties=pool_properties,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0 and res['stderr'] != '':
        if zpool:
            ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
        else:
            ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        if zpool:
            pool = new_name if zpool and new_name else zpool
            ret[pool] = 'imported' if __salt__['zpool.exists'](pool) else 'not found'
        else:
            ret = True
    return ret


def online(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2016.3.0

    Ensure that the specified devices are online

    zpool : string
        name of storage pool
    *vdevs : string
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
    dlist = []

    # Check if the pool_name exists
    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exist'
        return ret

    if not vdevs:
        ret[zpool] = 'no devices specified'
        return ret

    # default options
    flags = []
    target = []

    # set flags and options
    if kwargs.get('expand', False):
        flags.append('-e')
    target.append(zpool)
    if vdevs:
        target.extend(vdevs)

    # bring all specified devices online
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='online',
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = 'onlined {0}'.format(' '.join(vdevs))
    return ret


def offline(zpool, *vdevs, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2016.3.0

    Ensure that the specified devices are offline

    .. warning::

        By default, the OFFLINE state is persistent. The device remains offline when
        the system is rebooted. To temporarily take a device offline, use ``temporary=True``.

    zpool : string
        name of storage pool
    *vdevs : string
        one or more devices
    temporary : boolean
        enable temporarily offline

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.offline myzpool /path/to/vdev1 [...] [temporary=True|False]
    '''
    ret = {zpool: {}}

    # Check if the pool_name exists
    if not __salt__['zpool.exists'](zpool):
        ret[zpool] = 'storage pool does not exist'
        return ret

    if not vdevs or len(vdevs) <= 0:
        ret[zpool] = 'no devices specified'
        return ret

    # default options
    flags = []
    target = []

    # set flags and options
    if kwargs.get('temporary', False):
        flags.append('-t')
    target.append(zpool)
    if vdevs:
        target.extend(vdevs)

    # bring all specified devices offline
    # NOTE: we don't check if the device exists
    #       a device can be offlined until a replacement is available
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='offline',
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )
    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[zpool] = 'offlined {0}'.format(' '.join(vdevs))
    return ret


def labelclear(device, force=False):
    '''
    .. versionadded:: Oxygen

    Removes ZFS label information from the specified device

    .. warning::

        The device must not be part of an active pool configuration.

    device : string
        device
    force : boolean
        treat exported or foreign devices as inactive

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.labelclear /path/to/dev
    '''
    ret = {}

    # clear label for all specified devices
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='labelclear',
            flags=['-f'] if force else None,
            target=device,
        ),
        python_shell=False,
    )
    if res['retcode'] != 0:
        ## NOTE: skip the "use '-f' hint"
        res['stderr'] = res['stderr'].split("\n")
        if len(res['stderr']) >= 1:
            if res['stderr'][0].startswith("use '-f'"):
                del res['stderr'][0]
        res['stderr'] = "\n".join(res['stderr'])
        ret[device] = res['stderr'] if 'stderr' in res and res['stderr'] else res['stdout']
    else:
        ret[device] = 'cleared'
    return ret


def reguid(zpool):
    '''
    .. versionadded:: 2016.3.0

    Generates a new unique identifier for the pool

    .. warning::
        You must ensure that all devices in this pool are online
        and healthy before performing this action.

    zpool : string
        name of storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.reguid myzpool
    '''
    ret = {zpool: {}}

    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='reguid',
            target=zpool,
        ),
        python_shell=False,
    )
    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
    else:
        ret[zpool] = 'reguided'
    return ret


def reopen(zpool):
    '''
    .. versionadded:: 2016.3.0

    Reopen all the vdevs associated with the pool

    zpool : string
        name of storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.reopen myzpool
    '''
    ret = {zpool: {}}

    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='reopen',
            target=zpool,
        ),
        python_shell=False,
    )
    if res['retcode'] != 0:
        ret[zpool] = res['stderr'] if 'stderr' in res and res['stderr'] != '' else res['stdout']
    else:
        ret[zpool] = 'reopened'
    return ret


def upgrade(zpool=None, version=None):
    '''
    .. versionadded:: 2016.3.0

    Enables all supported features on the given pool

    .. warning::
        Once this is done, the pool will no longer be accessible on systems that do not
        support feature flags. See zpool-features(5) for details on compatibility with
        systems that support feature flags, but do not support all features enabled on the pool.

    zpool : string
        optional storage pool, applies to all otherwize
    version : int
        version to upgrade to, if unspecified upgrade to the highest possible

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.upgrade myzpool
    '''
    ret = {}

    flags = []
    opts = {}
    if version:
        opts['-V'] = version
    if not zpool:
        flags.append('-a')
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='upgrade',
            flags=flags,
            opts=opts,
            target=zpool,
        ),
        python_shell=False,
    )
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
    .. versionadded:: 2016.3.0

    Displays the command history of the specified pools or all pools if no pool is specified

    zpool : string
        optional storage pool
    internal : boolean
        toggle display of internally logged ZFS events
    verbose : boolean
        toggle display of the user name, the hostname, and the zone in which the operation was performed

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.upgrade myzpool
    '''
    ret = {}

    flags = []
    if verbose:
        flags.append('-l')
    if internal:
        flags.append('-i')
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zpool_command'](
            command='history',
            flags=flags,
            target=zpool,
        ),
        python_shell=False,
    )
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
