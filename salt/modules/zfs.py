# -*- coding: utf-8 -*-
'''
Module for running ZFS command

:codeauthor:    Nitin Madhok <nmadhok@clemson.edu>, Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs
:platform:      illumos,freebsd,linux

'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils.args
import salt.utils.path
import salt.modules.cmdmod
from salt.utils.odict import OrderedDict

__virtualname__ = 'zfs'
log = logging.getLogger(__name__)

# Function alias to set mapping.
__func_alias__ = {
    'list_': 'list',
}


def __virtual__():
    '''
    Only load when the platform has zfs support
    '''
    if __grains__['zfs_support']:
        return __virtualname__
    else:
        return (False, "The zfs module cannot be loaded: zfs not supported")


def exists(name, **kwargs):
    '''
    Check if a ZFS filesystem or volume or snapshot exists.

    name : string
        name of dataset
    type : string
        also check if dataset is of a certain type, valid choices are:
        filesystem, snapshot, volume, bookmark, or all.

    .. versionadded:: 2015.5.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.exists myzpool/mydataset
        salt '*' zfs.exists myzpool/myvolume type=volume
    '''
    ## Configure command
    # NOTE: initialize the defaults
    opts = {}

    # NOTE: set extra config from kwargs
    if kwargs.get('type', False):
        opts['-t'] = kwargs.get('type')

    ## Check if 'name' of 'type' exists
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='list',
            opts=opts,
            target=name,
        ),
        python_shell=False,
        ignore_retcode=True,
    )

    return res['retcode'] == 0


# TODO: cleanup code below this point
def create(name, **kwargs):
    '''
    Create a ZFS File System.

    name : string
        name of dataset or volume
    volume_size : string
        if specified, a zvol will be created instead of a dataset
    sparse : boolean
        create sparse volume
    create_parent : boolean
        creates all the non-existing parent datasets. any property specified on the
        command line using the -o option is ignored.
    properties : dict
        additional zfs properties (-o)

    .. note::

        ZFS properties can be specified at the time of creation of the filesystem by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

    .. versionadded:: 2015.5.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.create myzpool/mydataset [create_parent=True|False]
        salt '*' zfs.create myzpool/mydataset properties="{'mountpoint': '/export/zfs', 'sharenfs': 'on'}"
        salt '*' zfs.create myzpool/volume volume_size=1G [sparse=True|False]`
        salt '*' zfs.create myzpool/volume volume_size=1G properties="{'volblocksize': '512'}" [sparse=True|False]

    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    opts = {}

    # NOTE: push filesystem properties
    filesystem_properties = kwargs.get('properties', {})

    # NOTE: set extra config from kwargs
    if kwargs.get('create_parent', False):
        flags.append('-p')
    if kwargs.get('sparse', False) and kwargs.get('volume_size', None):
        flags.append('-s')
    if kwargs.get('volume_size', None):
        opts['-V'] = __utils__['zfs.to_size'](kwargs.get('volume_size'), convert_to_human=False)

    ## Create filesystem/volume
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='create',
            flags=flags,
            opts=opts,
            filesystem_properties=filesystem_properties,
            target=name,
        ),
        python_shell=False,
    )

    # Check and see if the dataset is available
    if res['retcode'] != 0:
        ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'created'

    return ret


def destroy(name, **kwargs):
    '''
    Destroy a ZFS File System.

    name : string
        name of dataset, volume, or snapshot
    force : boolean
        force an unmount of any file systems using the unmount -f command.
    recursive : boolean
        recursively destroy all children. (-r)
    recursive_all : boolean
        recursively destroy all dependents, including cloned file systems
        outside the target hierarchy. (-R)

    .. warning::
        watch out when using recursive and recursive_all

    .. versionadded:: 2015.5.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.destroy myzpool/mydataset [force=True|False]
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get('force', False):
        flags.append('-f')
    if kwargs.get('recursive_all', False):
        flags.append('-R')
    if kwargs.get('recursive', False):
        flags.append('-r')

    ## Destroy filesystem/volume/snapshot/...
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='destroy',
            flags=flags,
            target=name,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        if "operation does not apply to pools" in res['stderr']:
            ret[name] = '{0}, use zpool.destroy to destroy the pool'.format(res['stderr'].splitlines()[0])
        if "has children" in res['stderr']:
            ret[name] = '{0}, you can add the "recursive=True" parameter'.format(res['stderr'].splitlines()[0])
        else:
            ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'destroyed'

    return ret


def rename(name, new_name, **kwargs):
    '''
    Rename or Relocate a ZFS File System.

    name : string
        name of dataset, volume, or snapshot
    new_name : string
        new name of dataset, volume, or snapshot
    force : boolean
        force unmount any filesystems that need to be unmounted in the process.
    create_parent : boolean
        creates all the nonexistent parent datasets. Datasets created in
        this manner are automatically mounted according to the mountpoint
        property inherited from their parent.
    recursive : boolean
        recursively rename the snapshots of all descendent datasets.
        snapshots are the only dataset that can be renamed recursively.

    .. versionadded:: 2015.5.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.rename myzpool/mydataset myzpool/renameddataset
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config from kwargs
    if __utils__['zfs.is_snapshot'](name):
        if kwargs.get('create_parent', False):
            log.warning('zfs.rename - create_parent=True cannot be used with snapshots.')
        if kwargs.get('force', False):
            log.warning('zfs.rename - force=True cannot be used with snapshots.')
        if kwargs.get('recursive', False):
            flags.append('-r')
    else:
        if kwargs.get('create_parent', False):
            flags.append('-p')
        if kwargs.get('force', False):
            flags.append('-f')
        if kwargs.get('recursive', False):
            log.warning('zfs.rename - recursive=True can only be used with snapshots.')

    # NOTE: update target
    target.append(name)
    target.append(new_name)

    ## Rename filesystem/volume/snapshot/...
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='rename',
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'renamed to {0}'.format(new_name)

    return ret


def list_(name=None, **kwargs):
    '''
    Return a list of all datasets or a specified dataset on the system and the
    values of their used, available, referenced, and mountpoint properties.

    name : string
        name of dataset, volume, or snapshot
    recursive : boolean
        recursively list children
    depth : int
        limit recursion to depth
    properties : string
        comma-separated list of properties to list, the name property will always be added
    type : string
        comma-separated list of types to display, where type is one of
        filesystem, snapshot, volume, bookmark, or all.
    sort : string
        property to sort on (default = name)
    order : string [ascending|descending]
        sort order (default = ascending)
    parsable : boolean
        display numbers in parsable (exact) values
        .. versionadded:: Oxygen

    .. versionadded:: 2015.5.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.list
        salt '*' zfs.list myzpool/mydataset [recursive=True|False]
        salt '*' zfs.list myzpool/mydataset properties="sharenfs,mountpoint"
    '''
    ret = OrderedDict()

    ## update properties
    # NOTE: properties should be a list
    properties = kwargs.get('properties', 'used,avail,refer,mountpoint')
    if not isinstance(properties, list):
        properties = properties.split(',')

    # NOTE: name should be first property
    while 'name' in properties:
        properties.remove('name')
    properties.insert(0, 'name')

    ## Configure command
    # NOTE: initialize the defaults
    flags = ['-H', '-p']
    opts = {}

    # NOTE: set extra config from kwargs
    if kwargs.get('recursive', False):
        flags.append('-r')
    if kwargs.get('recursive', False) and kwargs.get('depth', False):
        opts['-d'] = kwargs.get('depth')
    if kwargs.get('type', False):
        opts['-t'] = kwargs.get('type')
    if kwargs.get('sort', False) and kwargs.get('sort') in properties:
        if kwargs.get('order', 'ascending').startswith('a'):
            opts['-s'] = kwargs.get('sort')
        else:
            opts['-S'] = kwargs.get('sort')
    if isinstance(properties, list):
        # NOTE: There can be only one -o and it takes a comma-seperated list
        opts['-o'] = ','.join(properties)
    else:
        opts['-o'] = properties

    ## parse zfs list
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='list',
            flags=flags,
            opts=opts,
            target=name,
        ),
        python_shell=False,
    )
    if res['retcode'] == 0:
        for ds in [l for l in res['stdout'].splitlines()]:
            ds = ds.split("\t")
            # NOTE: OrderedDict because we sort!
            ds_data = OrderedDict()

            for prop in properties:
                ds_data[prop] = __utils__['zfs.to_auto'](
                    prop,
                    ds[properties.index(prop)],
                    convert_to_human=not kwargs.get('parsable', True),
                )

            ret[ds_data['name']] = ds_data
            del ret[ds_data['name']]['name']
    else:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']

    return ret


## FIXME: also list mounted filesystems? (how to handle '-a' ?)
def mount(name=None, **kwargs):
    '''
    Mounts ZFS file systems

    name : string
        name of the filesystem, having this set to None will mount all filesystems. (this is the default)
    overlay : boolean
        perform an overlay mount.
    options : string
        optional comma-separated list of mount options to use temporarily for
        the duration of the mount.

    .. versionadded:: 2016.3.0
    .. versionchanged:: Fluorine

    .. warning::

            Passing '-a' as name is deprecated and will be removed 2 verions after Flourine.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.mount
        salt '*' zfs.mount myzpool/mydataset
        salt '*' zfs.mount myzpool/mydataset options=ro
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    opts = {}

    # NOTE: set extra config from kwargs
    if kwargs.get('overlay', False):
        flags.append('-O')
    if kwargs.get('options', False):
        opts['-o'] = kwargs.get('options')
    if name in [None, '-a']:
        # NOTE: still accept '-a' as name for backwards compatibility
        #       two versions after Flourine this should just simplify
        #       this to just set '-a' if name is not set.
        flags.append('-a')
        name = None

    ## Mount filesystem
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='mount',
            flags=flags,
            opts=opts,
            target=name,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'mounted'

    return ret


def unmount(name, **kwargs):
    '''
    Unmounts ZFS file systems

    name : string
        name of the filesystem, you can use None to unmount all mounted filesystems.
    force : boolean
        forcefully unmount the file system, even if it is currently in use.

    .. warning::

        Using ``-a`` for the name parameter will probably break your system, unless your rootfs is not on zfs.

    .. versionadded:: 2016.3.0
    .. versionchanged:: Fluorine

    .. warning::

            Passing '-a' as name is deprecated and will be removed 2 verions after Flourine.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.unmount myzpool/mydataset [force=True|False]
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get('force', False):
        flags.append('-f')
    if name in [None, '-a']:
        # NOTE: still accept '-a' as name for backwards compatibility
        #       two versions after Flourine this should just simplify
        #       this to just set '-a' if name is not set.
        flags.append('-a')
        name = None

    ## Unmount filesystem
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='unmount',
            flags=flags,
            target=name,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'unmounted'

    return ret


def inherit(prop, name, **kwargs):
    '''
    Clears the specified property

    prop : string
        name of property
    name : string
        name of the filesystem, volume, or snapshot
    recursive : boolean
        recursively inherit the given property for all children.
    revert : boolean
        revert the property to the received value if one exists; otherwise
        operate as if the -S option was not specified.

    .. versionadded:: 2016.3.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.inherit canmount myzpool/mydataset [recursive=True|False]
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get('recursive', False):
        flags.append('-r')
    if kwargs.get('revert', False):
        flags.append('-S')

    ## Inherit property
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='inherit',
            flags=flags,
            property_name=prop,
            target=name,
        ),
        python_shell=False,
    )

    ret[name] = {}
    if res['retcode'] != 0:
        ret[name][prop] = res['stderr'] if 'stderr' in res else res['stdout']
        if 'property cannot be inherited' in res['stderr']:
            ret[name][prop] = '{0}, {1}'.format(
                ret[name][prop],
                'use revert=True to try and reset it to it\'s default value.'
            )
    else:
        ret[name][prop] = 'cleared'
    return ret


def diff(name_a, name_b, **kwargs):
    '''
    Display the difference between a snapshot of a given filesystem and
    another snapshot of that filesystem from a later time or the current
    contents of the filesystem.

    name_a : string
        name of snapshot
    name_b : string
        name of snapshot or filesystem
    show_changetime : boolean
        display the path's inode change time as the first column of output. (default = False)
    show_indication : boolean
        display an indication of the type of file. (default = True)

    .. versionadded:: 2016.3.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.diff myzpool/mydataset@yesterday myzpool/mydataset
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = ['-H']
    target = []

    # NOTE: set extra config from kwargs
    if kwargs.get('show_changetime', False):
        flags.append('-t')
    if kwargs.get('show_indication', False):
        flags.append('-F')

    # NOTE: update target
    target.append(name_a)
    target.append(name_b)

    ## Diff filesystem/snapshot
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='diff',
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        # FIXME: parse timestamp if '-t'
        ret = []
        for line in res['stdout'].splitlines():
            ret.append(line)
    return ret


def rollback(name, **kwargs):
    '''
    Roll back the given dataset to a previous snapshot.

    name : string
        name of snapshot
    recursive : boolean
        destroy any snapshots and bookmarks more recent than the one
        specified.
    recursive_all : boolean
        destroy any more recent snapshots and bookmarks, as well as any
        clones of those snapshots.
    force : boolean
        used with the -R option to force an unmount of any clone file
        systems that are to be destroyed.

    .. warning::

        When a dataset is rolled back, all data that has changed since
        the snapshot is discarded, and the dataset reverts to the state
        at the time of the snapshot. By default, the command refuses to
        roll back to a snapshot other than the most recent one.

        In order to do so, all intermediate snapshots and bookmarks
        must be destroyed by specifying the -r option.

    .. versionadded:: 2016.3.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.rollback myzpool/mydataset@yesterday
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get('recursive_all', False):
        flags.append('-R')
    if kwargs.get('recursive', False):
        flags.append('-r')
    if kwargs.get('force', False):
        if kwargs.get('recursive_all', False) or kwargs.get('recursive', False):
            flags.append('-f')
        else:
            log.warning('zfs.rollback - force=True can only be used with recursive_all=True or recursive=True')

    ## Diff filesystem/snapshot
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='rollback',
            flags=flags,
            target=name,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[name[:name.index('@')]] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name[:name.index('@')]] = 'rolledback to snapshot: {0}'.format(name[name.index('@')+1:])
    return ret


def clone(name_a, name_b, **kwargs):
    '''
    Creates a clone of the given snapshot.

    name_a : string
        name of snapshot
    name_b : string
        name of filesystem or volume
    create_parent : boolean
        creates all the non-existing parent datasets. any property specified on the
        command line using the -o option is ignored.
    properties : dict
        additional zfs properties (-o)

    .. note::

        ZFS properties can be specified at the time of creation of the filesystem by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

    .. versionadded:: 2016.3.0
    .. versionchanged:: Fluorine

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.clone myzpool/mydataset@yesterday myzpool/mydataset_yesterday
    '''
    ret = OrderedDict()

    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: push filesystem properties
    filesystem_properties = kwargs.get('properties', {})

    # NOTE: set extra config from kwargs
    if kwargs.get('create_parent', False):
        flags.append('-p')

    # NOTE: update target
    target.append(name_a)
    target.append(name_b)

    ## Clone filesystem/volume
    res = __salt__['cmd.run_all'](
        __utils__['zfs.zfs_command'](
            command='clone',
            flags=flags,
            filesystem_properties=filesystem_properties,
            target=target,
        ),
        python_shell=False,
    )

    if res['retcode'] != 0:
        ret[name_b] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name_b] = 'cloned from {0}'.format(name_a)
    return ret


# TODO: switch to zfs_command below this point
def promote(name):
    '''
    .. versionadded:: 2016.3.0

    Promotes a clone file system to no longer be dependent on its "origin"
    snapshot.

    .. note::

        This makes it possible to destroy the file system that the
        clone was created from. The clone parent-child dependency relationship
        is reversed, so that the origin file system becomes a clone of the
        specified file system.

        The snapshot that was cloned, and any snapshots previous to this
        snapshot, are now owned by the promoted clone. The space they use moves
        from the origin file system to the promoted clone, so enough space must
        be available to accommodate these snapshots. No new space is consumed
        by this operation, but the space accounting is adjusted. The promoted
        clone must not have any conflicting snapshot names of its own. The
        rename subcommand can be used to rename any conflicting snapshots.

    name : string
        name of clone-filesystem

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.promote myzpool/myclone
    '''
    ret = {}

    zfs = salt.utils.path.which('zfs')

    res = __salt__['cmd.run_all']('{zfs} promote {name}'.format(
        zfs=zfs,
        name=__utils__['zfs.to_str'](name)
    ))

    if res['retcode'] != 0:
        ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'promoted'
    return ret


def bookmark(snapshot, bookmark):
    '''
    .. versionadded:: 2016.3.0

    Creates a bookmark of the given snapshot

    .. note::

        Bookmarks mark the point in time when the snapshot was created,
        and can be used as the incremental source for a zfs send command.

        This feature must be enabled to be used. See zpool-features(5) for
        details on ZFS feature flags and the bookmarks feature.

    snapshot : string
        name of snapshot to bookmark
    bookmark : string
        name of bookmark

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.bookmark myzpool/mydataset@yesterday myzpool/mydataset#complete
    '''
    ret = {}

    # abort if we do not have feature flags
    if not __utils__['zfs.has_feature_flags']():
        ret['error'] = 'bookmarks are not supported'
        return ret

    zfs = salt.utils.path.which('zfs')

    if '@' not in snapshot:
        ret[snapshot] = 'MUST be a snapshot'

    if '#' not in bookmark:
        ret[bookmark] = 'MUST be a bookmark'

    if len(ret) > 0:
        return ret

    res = __salt__['cmd.run_all']('{zfs} bookmark {snapshot} {bookmark}'.format(
        zfs=zfs,
        snapshot=__utils__['zfs.to_str'](snapshot),
        bookmark=__utils__['zfs.to_str'](bookmark)
    ))

    if res['retcode'] != 0:
        ret[snapshot] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[snapshot] = 'bookmarked as {0}'.format(bookmark)
    return ret


def holds(snapshot, **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Lists all existing user references for the given snapshot or snapshots.

    snapshot : string
        name of snapshot
    recursive : boolean
        lists the holds that are set on the named descendent snapshots also.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.holds myzpool/mydataset@baseline
    '''
    ret = {}

    if '@' not in snapshot:
        ret[snapshot] = 'MUST be a snapshot'
        return ret

    zfs = salt.utils.path.which('zfs')
    recursive = kwargs.get('recursive', False)

    res = __salt__['cmd.run_all']('{zfs} holds -H {recursive}{snapshot}'.format(
        zfs=zfs,
        recursive='-r ' if recursive else '',
        snapshot=__utils__['zfs.to_str'](snapshot)
    ))

    if res['retcode'] == 0:
        if res['stdout'] != '':
            properties = "name,tag,timestamp".split(",")
            for hold in [l for l in res['stdout'].splitlines()]:
                hold = hold.split("\t")
                hold_data = {}

                for prop in properties:
                    hold_data[prop] = hold[properties.index(prop)]

                if hold_data['name'] not in ret:
                    ret[hold_data['name']] = {}
                ret[hold_data['name']][hold_data['tag']] = hold_data['timestamp']
        else:
            ret[snapshot] = 'no holds'
    else:
        ret[snapshot] = res['stderr'] if 'stderr' in res else res['stdout']
    return ret


def hold(tag, *snapshot, **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Adds a single reference, named with the tag argument, to the specified
    snapshot or snapshots.

    .. note::

        Each snapshot has its own tag namespace, and tags must be unique within that space.

        If a hold exists on a snapshot, attempts to destroy that snapshot by
        using the zfs destroy command return EBUSY.

    tag : string
        name of tag
    *snapshot : string
        name of snapshot(s)
    recursive : boolean
        specifies that a hold with the given tag is applied recursively to
        the snapshots of all descendent file systems.

    .. note::

        A comma-separated list can be provided for the tag parameter to hold multiple tags.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.hold mytag myzpool/mydataset@mysnapshot [recursive=True]
        salt '*' zfs.hold mytag,myothertag myzpool/mydataset@mysnapshot
        salt '*' zfs.hold mytag myzpool/mydataset@mysnapshot myzpool/mydataset@myothersnapshot
    '''
    ret = {}

    zfs = salt.utils.path.which('zfs')
    recursive = kwargs.get('recursive', False)

    # verify snapshots
    if not snapshot:
        ret['error'] = 'one or more snapshots must be specified'

    for snap in snapshot:
        if '@' not in snap:
            ret[snap] = 'not a snapshot'

    if len(ret) > 0:
        return ret

    for csnap in snapshot:
        for ctag in tag.split(','):
            res = __salt__['cmd.run_all']('{zfs} hold {recursive}{tag} {snapshot}'.format(
                zfs=zfs,
                recursive='-r ' if recursive else '',
                tag=__utils__['zfs.to_str'](ctag),
                snapshot=__utils__['zfs.to_str'](csnap)
            ))

            if csnap not in ret:
                ret[csnap] = {}

            if res['retcode'] != 0:
                for err in res['stderr'].splitlines():
                    if err.startswith('cannot hold snapshot'):
                        ret[csnap][ctag] = err[err.index(':')+2:]
                    elif err.startswith('cannot open'):
                        ret[csnap][ctag] = err[err.index(':')+2:]
                    else:
                        # fallback in case we hit a weird error
                        if err == 'usage:':
                            break
                        ret[csnap][ctag] = res['stderr']
            else:
                ret[csnap][ctag] = 'held'

    return ret


def release(tag, *snapshot, **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Removes a single reference, named with the tag argument, from the
    specified snapshot or snapshots.

    .. note::

        The tag must already exist for each snapshot.
        If a hold exists on a snapshot, attempts to destroy that
        snapshot by using the zfs destroy command return EBUSY.

    tag : string
        name of tag
    *snapshot : string
        name of snapshot(s)
    recursive : boolean
        recursively releases a hold with the given tag on the snapshots of
        all descendent file systems.

    .. note::

        A comma-separated list can be provided for the tag parameter to release multiple tags.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.release mytag myzpool/mydataset@mysnapshot [recursive=True]
        salt '*' zfs.release mytag myzpool/mydataset@mysnapshot myzpool/mydataset@myothersnapshot
    '''
    ret = {}

    zfs = salt.utils.path.which('zfs')
    recursive = kwargs.get('recursive', False)

    # verify snapshots
    if not snapshot:
        ret['error'] = 'one or more snapshots must be specified'

    for snap in snapshot:
        if '@' not in snap:
            ret[snap] = 'not a snapshot'

    if len(ret) > 0:
        return ret

    for csnap in snapshot:
        for ctag in tag.split(','):
            res = __salt__['cmd.run_all']('{zfs} release {recursive}{tag} {snapshot}'.format(
                zfs=zfs,
                recursive='-r ' if recursive else '',
                tag=__utils__['zfs.to_str'](ctag),
                snapshot=__utils__['zfs.to_str'](csnap)
            ))

            if csnap not in ret:
                ret[csnap] = {}

            if res['retcode'] != 0:
                for err in res['stderr'].splitlines():
                    if err.startswith('cannot release hold from snapshot'):
                        ret[csnap][ctag] = err[err.index(':')+2:]
                    elif err.startswith('cannot open'):
                        ret[csnap][ctag] = err[err.index(':')+2:]
                    else:
                        # fallback in case we hit a weird error
                        if err == 'usage:':
                            break
                        ret[csnap][ctag] = res['stderr']
            else:
                ret[csnap][ctag] = 'released'

    return ret


def snapshot(*snapshot, **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Creates snapshots with the given names.

    *snapshot : string
        name of snapshot(s)
    recursive : boolean
        recursively create snapshots of all descendent datasets.
    properties : dict
        additional zfs properties (-o)

    .. note::

        ZFS properties can be specified at the time of creation of the filesystem by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.snapshot myzpool/mydataset@yesterday [recursive=True]
        salt '*' zfs.snapshot myzpool/mydataset@yesterday myzpool/myotherdataset@yesterday [recursive=True]
    '''
    ret = {}

    zfs = salt.utils.path.which('zfs')
    recursive = kwargs.get('recursive', False)
    properties = kwargs.get('properties', None)

    # verify snapshots
    if not snapshot:
        ret['error'] = 'one or more snapshots must be specified'

    for snap in snapshot:
        if '@' not in snap:
            ret[snap] = 'not a snapshot'

    # if zpool properties specified, then
    # create "-o property=value" pairs
    if properties:
        proplist = []
        for prop in properties:
            proplist.append('-o {0}={1}'.format(prop, __utils__['zfs.to_auto']((properties[prop]))))
        properties = ' '.join(proplist)

    for csnap in snapshot:
        if '@' not in csnap:
            continue

        res = __salt__['cmd.run_all']('{zfs} snapshot {recursive}{properties}{snapshot}'.format(
            zfs=zfs,
            recursive='-r ' if recursive else '',
            properties='{0} '.format(properties) if properties else '',
            snapshot=__utils__['zfs.to_str'](csnap)
        ))

        if res['retcode'] != 0:
            for err in res['stderr'].splitlines():
                if err.startswith('cannot create snapshot'):
                    ret[csnap] = err[err.index(':')+2:]
                elif err.startswith('cannot open'):
                    ret[csnap] = err[err.index(':')+2:]
                else:
                    # fallback in case we hit a weird error
                    if err == 'usage:':
                        break
                    ret[csnap] = res['stderr']
        else:
            ret[csnap] = 'snapshotted'
    return ret


def set(*dataset, **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Sets the property or list of properties to the given value(s) for each dataset.

    *dataset : string
        name of snapshot(s), filesystem(s), or volume(s)
    *properties : string
        additional zfs properties pairs

    .. note::

        properties are passed as key-value pairs. e.g.

            compression=off

    .. note::

        Only some properties can be edited.

        See the Properties section for more information on what properties
        can be set and acceptable values.

        Numeric values can be specified as exact values, or in a human-readable
        form with a suffix of B, K, M, G, T, P, E, Z (for bytes, kilobytes,
        megabytes, gigabytes, terabytes, petabytes, exabytes, or zettabytes,
        respectively).

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.set myzpool/mydataset compression=off
        salt '*' zfs.set myzpool/mydataset myzpool/myotherdataset compression=off
        salt '*' zfs.set myzpool/mydataset myzpool/myotherdataset compression=lz4 canmount=off
    '''
    ret = {}

    zfs = salt.utils.path.which('zfs')

    # verify snapshots
    if not dataset:
        ret['error'] = 'one or more snapshots must be specified'

    # clean kwargs
    properties = salt.utils.args.clean_kwargs(**kwargs)
    if len(properties) < 1:
        ret['error'] = '{0}one or more properties must be specified'.format(
            '{0},\n'.format(ret['error']) if 'error' in ret else ''
        )

    if len(ret) > 0:
        return ret

    # for better error handling we don't do one big set command
    for ds in dataset:
        for prop in properties:
            res = __salt__['cmd.run_all']('{zfs} set {prop}={value} {dataset}'.format(
                zfs=zfs,
                prop=prop,
                value=__utils__['zfs.to_auto'](properties[prop]),
                dataset=__utils__['zfs.to_str'](ds)
            ))
            if ds not in ret:
                ret[ds] = {}

            if res['retcode'] != 0:
                ret[ds][prop] = res['stderr'] if 'stderr' in res else res['stdout']
                if ':' in ret[ds][prop]:
                    ret[ds][prop] = ret[ds][prop][ret[ds][prop].index(':')+2:]
            else:
                ret[ds][prop] = 'set'

    return ret


def get(*dataset, **kwargs):
    '''
    .. versionadded:: 2016.3.0
    .. versionchanged:: Oxygen

    Displays properties for the given datasets.

    *dataset : string
        name of snapshot(s), filesystem(s), or volume(s)
    properties : string
        comma-separated list of properties to list, defaults to all
    recursive : boolean
        recursively list children
    depth : int
        recursively list children to depth
    fields : string
        comma-separated list of fields to include, the name and property field will always be added
    type : string
        comma-separated list of types to display, where type is one of
        filesystem, snapshot, volume, bookmark, or all.
    source : string
        comma-separated list of sources to display. Must be one of the following:
        local, default, inherited, temporary, and none. The default value is all sources.
    parsable : boolean
        display numbers in parsable (exact) values
        .. versionadded:: Oxygen

    .. note::

        If no datasets are specified, then the command displays properties
        for all datasets on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.get
        salt '*' zfs.get myzpool/mydataset [recursive=True|False]
        salt '*' zfs.get myzpool/mydataset properties="sharenfs,mountpoint" [recursive=True|False]
        salt '*' zfs.get myzpool/mydataset myzpool/myotherdataset properties=available fields=value depth=1
    '''
    ret = OrderedDict()
    zfs = salt.utils.path.which('zfs')
    properties = kwargs.get('properties', 'all')
    recursive = kwargs.get('recursive', False)
    depth = kwargs.get('depth', 0)
    fields = kwargs.get('fields', 'value,source')
    ltype = kwargs.get('type', None)
    source = kwargs.get('source', None)
    parsable = kwargs.get('parsable', False)
    cmd = '{0} get -H'.format(zfs)

    # parsable output
    if parsable:
        cmd = '{0} -p'.format(cmd)

    # recursively get
    if depth:
        cmd = '{0} -d {1}'.format(cmd, depth)
    elif recursive:
        cmd = '{0} -r'.format(cmd)

    # fields
    fields = fields.split(',')
    if 'name' in fields:  # ensure name is first
        fields.remove('name')
    if 'property' in fields:  # ensure property is second
        fields.remove('property')
    fields.insert(0, 'name')
    fields.insert(1, 'property')
    cmd = '{0} -o {1}'.format(cmd, ','.join(fields))

    # filter on type
    if source:
        cmd = '{0} -s {1}'.format(cmd, source)

    # filter on type
    if ltype:
        cmd = '{0} -t {1}'.format(cmd, ltype)

    # properties
    cmd = '{0} {1}'.format(cmd, properties)

    # datasets
    if dataset:
        dataset = [__utils__['zfs.to_str'](x) for x in dataset]
    cmd = '{0} {1}'.format(cmd, ' '.join(dataset))

    # parse output
    res = __salt__['cmd.run_all'](cmd)
    if res['retcode'] == 0:
        for ds in [l for l in res['stdout'].splitlines()]:
            ds = ds.split("\t")
            ds_data = {}

            for field in fields:
                ds_data[field] = __utils__['zfs.to_auto'](ds[fields.index(field)])

            ds_name = ds_data['name']
            ds_prop = ds_data['property']
            del ds_data['name']
            del ds_data['property']

            if ds_name not in ret:
                ret[ds_name] = {}

            ret[ds_name][ds_prop] = ds_data
    else:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
