"""
Module for running ZFS command

:codeauthor:    Nitin Madhok <nmadhok@clemson.edu>, Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs
:platform:      illumos,freebsd,linux

.. versionchanged:: 2018.3.1
  Big refactor to remove duplicate code, better type conversions and improved
  consistency in output.

"""

import logging

import salt.modules.cmdmod
import salt.utils.args
import salt.utils.path
import salt.utils.versions
from salt.ext.six.moves import zip
from salt.utils.odict import OrderedDict

__virtualname__ = "zfs"
log = logging.getLogger(__name__)

# Function alias to set mapping.
__func_alias__ = {
    "list_": "list",
}


def __virtual__():
    """
    Only load when the platform has zfs support
    """
    if __grains__.get("zfs_support"):
        return __virtualname__
    else:
        return False, "The zfs module cannot be loaded: zfs not supported"


def exists(name, **kwargs):
    """
    Check if a ZFS filesystem or volume or snapshot exists.

    name : string
        name of dataset
    type : string
        also check if dataset is of a certain type, valid choices are:
        filesystem, snapshot, volume, bookmark, or all.

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.exists myzpool/mydataset
        salt '*' zfs.exists myzpool/myvolume type=volume

    """
    ## Configure command
    # NOTE: initialize the defaults
    opts = {}

    # NOTE: set extra config from kwargs
    if kwargs.get("type", False):
        opts["-t"] = kwargs.get("type")

    ## Check if 'name' of 'type' exists
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="list", opts=opts, target=name,),
        python_shell=False,
        ignore_retcode=True,
    )

    return res["retcode"] == 0


def create(name, **kwargs):
    """
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

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.create myzpool/mydataset [create_parent=True|False]
        salt '*' zfs.create myzpool/mydataset properties="{'mountpoint': '/export/zfs', 'sharenfs': 'on'}"
        salt '*' zfs.create myzpool/volume volume_size=1G [sparse=True|False]`
        salt '*' zfs.create myzpool/volume volume_size=1G properties="{'volblocksize': '512'}" [sparse=True|False]

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    opts = {}

    # NOTE: push filesystem properties
    filesystem_properties = kwargs.get("properties", {})

    # NOTE: set extra config from kwargs
    if kwargs.get("create_parent", False):
        flags.append("-p")
    if kwargs.get("sparse", False) and kwargs.get("volume_size", None):
        flags.append("-s")
    if kwargs.get("volume_size", None):
        opts["-V"] = __utils__["zfs.to_size"](
            kwargs.get("volume_size"), convert_to_human=False
        )

    ## Create filesystem/volume
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="create",
            flags=flags,
            opts=opts,
            filesystem_properties=filesystem_properties,
            target=name,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "created")


def destroy(name, **kwargs):
    """
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

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.destroy myzpool/mydataset [force=True|False]

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get("force", False):
        flags.append("-f")
    if kwargs.get("recursive_all", False):
        flags.append("-R")
    if kwargs.get("recursive", False):
        flags.append("-r")

    ## Destroy filesystem/volume/snapshot/...
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="destroy", flags=flags, target=name,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "destroyed")


def rename(name, new_name, **kwargs):
    """
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

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.rename myzpool/mydataset myzpool/renameddataset

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config from kwargs
    if __utils__["zfs.is_snapshot"](name):
        if kwargs.get("create_parent", False):
            log.warning(
                "zfs.rename - create_parent=True cannot be used with snapshots."
            )
        if kwargs.get("force", False):
            log.warning("zfs.rename - force=True cannot be used with snapshots.")
        if kwargs.get("recursive", False):
            flags.append("-r")
    else:
        if kwargs.get("create_parent", False):
            flags.append("-p")
        if kwargs.get("force", False):
            flags.append("-f")
        if kwargs.get("recursive", False):
            log.warning("zfs.rename - recursive=True can only be used with snapshots.")

    # NOTE: update target
    target.append(name)
    target.append(new_name)

    ## Rename filesystem/volume/snapshot/...
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="rename", flags=flags, target=target,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "renamed")


def list_(name=None, **kwargs):
    """
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
        .. versionadded:: 2018.3.0

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.list
        salt '*' zfs.list myzpool/mydataset [recursive=True|False]
        salt '*' zfs.list myzpool/mydataset properties="sharenfs,mountpoint"

    """
    ret = OrderedDict()

    ## update properties
    # NOTE: properties should be a list
    properties = kwargs.get("properties", "used,avail,refer,mountpoint")
    if not isinstance(properties, list):
        properties = properties.split(",")

    # NOTE: name should be first property
    #       we loop here because there 'name' can be in the list
    #       multiple times.
    while "name" in properties:
        properties.remove("name")
    properties.insert(0, "name")

    ## Configure command
    # NOTE: initialize the defaults
    flags = ["-H"]
    opts = {}

    # NOTE: set extra config from kwargs
    if kwargs.get("recursive", False):
        flags.append("-r")
    if kwargs.get("recursive", False) and kwargs.get("depth", False):
        opts["-d"] = kwargs.get("depth")
    if kwargs.get("type", False):
        opts["-t"] = kwargs.get("type")
    kwargs_sort = kwargs.get("sort", False)
    if kwargs_sort and kwargs_sort in properties:
        if kwargs.get("order", "ascending").startswith("a"):
            opts["-s"] = kwargs_sort
        else:
            opts["-S"] = kwargs_sort
    if isinstance(properties, list):
        # NOTE: There can be only one -o and it takes a comma-separated list
        opts["-o"] = ",".join(properties)
    else:
        opts["-o"] = properties

    ## parse zfs list
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="list", flags=flags, opts=opts, target=name,
        ),
        python_shell=False,
    )
    if res["retcode"] == 0:
        for ds in res["stdout"].splitlines():
            if kwargs.get("parsable", True):
                ds_data = __utils__["zfs.from_auto_dict"](
                    OrderedDict(list(zip(properties, ds.split("\t")))),
                )
            else:
                ds_data = __utils__["zfs.to_auto_dict"](
                    OrderedDict(list(zip(properties, ds.split("\t")))),
                    convert_to_human=True,
                )

            ret[ds_data["name"]] = ds_data
            del ret[ds_data["name"]]["name"]
    else:
        return __utils__["zfs.parse_command_result"](res)

    return ret


def list_mount():
    """
    List mounted zfs filesystems

    .. versionadded:: 2018.3.1

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.list_mount

    """
    ## List mounted filesystem
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="mount",), python_shell=False,
    )

    if res["retcode"] == 0:
        ret = OrderedDict()
        for mount in res["stdout"].splitlines():
            mount = mount.split()
            ret[mount[0]] = mount[-1]
        return ret
    else:
        return __utils__["zfs.parse_command_result"](res)


def mount(name=None, **kwargs):
    """
    Mounts ZFS file systems

    name : string
        name of the filesystem, having this set to None will mount all filesystems. (this is the default)
    overlay : boolean
        perform an overlay mount.
    options : string
        optional comma-separated list of mount options to use temporarily for
        the duration of the mount.

    .. versionadded:: 2016.3.0
    .. versionchanged:: 2018.3.1

    .. warning::

            Passing '-a' as name is deprecated and will be removed in 3001.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.mount
        salt '*' zfs.mount myzpool/mydataset
        salt '*' zfs.mount myzpool/mydataset options=ro

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    opts = {}

    # NOTE: set extra config from kwargs
    if kwargs.get("overlay", False):
        flags.append("-O")
    if kwargs.get("options", False):
        opts["-o"] = kwargs.get("options")

    ## Mount filesystem
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="mount", flags=flags, opts=opts, target=name,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "mounted")


def unmount(name, **kwargs):
    """
    Unmounts ZFS file systems

    name : string
        name of the filesystem, you can use None to unmount all mounted filesystems.
    force : boolean
        forcefully unmount the file system, even if it is currently in use.

    .. warning::

        Using ``-a`` for the name parameter will probably break your system, unless your rootfs is not on zfs.

    .. versionadded:: 2016.3.0
    .. versionchanged:: 2018.3.1

    .. warning::

            Passing '-a' as name is deprecated and will be removed in 3001.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.unmount myzpool/mydataset [force=True|False]

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get("force", False):
        flags.append("-f")
    if name in [None, "-a"]:
        # NOTE: still accept '-a' as name for backwards compatibility
        #       until Salt 3001 this should just simplify
        #       this to just set '-a' if name is not set.
        flags.append("-a")
        name = None

    ## Unmount filesystem
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="unmount", flags=flags, target=name,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "unmounted")


def inherit(prop, name, **kwargs):
    """
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

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.inherit canmount myzpool/mydataset [recursive=True|False]

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get("recursive", False):
        flags.append("-r")
    if kwargs.get("revert", False):
        flags.append("-S")

    ## Inherit property
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="inherit", flags=flags, property_name=prop, target=name,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "inherited")


def diff(name_a, name_b=None, **kwargs):
    """
    Display the difference between a snapshot of a given filesystem and
    another snapshot of that filesystem from a later time or the current
    contents of the filesystem.

    name_a : string
        name of snapshot
    name_b : string
        (optional) name of snapshot or filesystem
    show_changetime : boolean
        display the path's inode change time as the first column of output. (default = True)
    show_indication : boolean
        display an indication of the type of file. (default = True)
    parsable : boolean
        if true we don't parse the timestamp to a more readable date (default = True)

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.diff myzpool/mydataset@yesterday myzpool/mydataset

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = ["-H"]
    target = []

    # NOTE: set extra config from kwargs
    if kwargs.get("show_changetime", True):
        flags.append("-t")
    if kwargs.get("show_indication", True):
        flags.append("-F")

    # NOTE: update target
    target.append(name_a)
    if name_b:
        target.append(name_b)

    ## Diff filesystem/snapshot
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="diff", flags=flags, target=target,),
        python_shell=False,
    )

    if res["retcode"] != 0:
        return __utils__["zfs.parse_command_result"](res)
    else:
        if not kwargs.get("parsable", True) and kwargs.get("show_changetime", True):
            ret = OrderedDict()
            for entry in res["stdout"].splitlines():
                entry = entry.split()
                entry_timestamp = __utils__["dateutils.strftime"](
                    entry[0], "%Y-%m-%d.%H:%M:%S.%f"
                )
                entry_data = "\t\t".join(entry[1:])
                ret[entry_timestamp] = entry_data
        else:
            ret = res["stdout"].splitlines()
        return ret


def rollback(name, **kwargs):
    """
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

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.rollback myzpool/mydataset@yesterday

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config from kwargs
    if kwargs.get("recursive_all", False):
        flags.append("-R")
    if kwargs.get("recursive", False):
        flags.append("-r")
    if kwargs.get("force", False):
        if kwargs.get("recursive_all", False) or kwargs.get("recursive", False):
            flags.append("-f")
        else:
            log.warning(
                "zfs.rollback - force=True can only be used with recursive_all=True or recursive=True"
            )

    ## Rollback to snapshot
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="rollback", flags=flags, target=name,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "rolledback")


def clone(name_a, name_b, **kwargs):
    """
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

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.clone myzpool/mydataset@yesterday myzpool/mydataset_yesterday

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: push filesystem properties
    filesystem_properties = kwargs.get("properties", {})

    # NOTE: set extra config from kwargs
    if kwargs.get("create_parent", False):
        flags.append("-p")

    # NOTE: update target
    target.append(name_a)
    target.append(name_b)

    ## Clone filesystem/volume
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="clone",
            flags=flags,
            filesystem_properties=filesystem_properties,
            target=target,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "cloned")


def promote(name):
    """
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

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.promote myzpool/myclone

    """
    ## Promote clone
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="promote", target=name,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "promoted")


def bookmark(snapshot, bookmark):
    """
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

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.bookmark myzpool/mydataset@yesterday myzpool/mydataset#complete

    """
    # abort if we do not have feature flags
    if not __utils__["zfs.has_feature_flags"]():
        return OrderedDict([("error", "bookmarks are not supported")])

    ## Configure command
    # NOTE: initialize the defaults
    target = []

    # NOTE: update target
    target.append(snapshot)
    target.append(bookmark)

    ## Bookmark snapshot
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="bookmark", target=target,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "bookmarked")


def holds(snapshot, **kwargs):
    """
    Lists all existing user references for the given snapshot or snapshots.

    snapshot : string
        name of snapshot
    recursive : boolean
        lists the holds that are set on the named descendent snapshots also.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.holds myzpool/mydataset@baseline

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = ["-H"]
    target = []

    # NOTE: set extra config from kwargs
    if kwargs.get("recursive", False):
        flags.append("-r")

    # NOTE: update target
    target.append(snapshot)

    ## Lookup holds
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="holds", flags=flags, target=target,),
        python_shell=False,
    )

    ret = __utils__["zfs.parse_command_result"](res)
    if res["retcode"] == 0:
        for hold in res["stdout"].splitlines():
            hold_data = OrderedDict(
                list(zip(["name", "tag", "timestamp"], hold.split("\t"),))
            )
            ret[hold_data["tag"].strip()] = hold_data["timestamp"]

    return ret


def hold(tag, *snapshot, **kwargs):
    """
    Adds a single reference, named with the tag argument, to the specified
    snapshot or snapshots.

    .. note::

        Each snapshot has its own tag namespace, and tags must be unique within that space.

        If a hold exists on a snapshot, attempts to destroy that snapshot by
        using the zfs destroy command return EBUSY.

    tag : string
        name of tag
    snapshot : string
        name of snapshot(s)
    recursive : boolean
        specifies that a hold with the given tag is applied recursively to
        the snapshots of all descendent file systems.

    .. versionadded:: 2016.3.0
    .. versionchanged:: 2018.3.1

    .. warning::

        As of 2018.3.1 the tag parameter no longer accepts a comma-separated value.
        It's is now possible to create a tag that contains a comma, this was impossible before.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.hold mytag myzpool/mydataset@mysnapshot [recursive=True]
        salt '*' zfs.hold mytag myzpool/mydataset@mysnapshot myzpool/mydataset@myothersnapshot
    """

    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config from kwargs
    if kwargs.get("recursive", False):
        flags.append("-r")

    # NOTE: update target
    target.append(tag)
    target.extend(snapshot)

    ## hold snapshot
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="hold", flags=flags, target=target,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "held")


def release(tag, *snapshot, **kwargs):
    """
    Removes a single reference, named with the tag argument, from the
    specified snapshot or snapshots.

    .. note::

        The tag must already exist for each snapshot.
        If a hold exists on a snapshot, attempts to destroy that
        snapshot by using the zfs destroy command return EBUSY.

    tag : string
        name of tag
    snapshot : string
        name of snapshot(s)
    recursive : boolean
        recursively releases a hold with the given tag on the snapshots of
        all descendent file systems.

    .. versionadded:: 2016.3.0
    .. versionchanged:: 2018.3.1

    .. warning::

        As of 2018.3.1 the tag parameter no longer accepts a comma-separated value.
        It's is now possible to create a tag that contains a comma, this was impossible before.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.release mytag myzpool/mydataset@mysnapshot [recursive=True]
        salt '*' zfs.release mytag myzpool/mydataset@mysnapshot myzpool/mydataset@myothersnapshot

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config from kwargs
    if kwargs.get("recursive", False):
        flags.append("-r")

    # NOTE: update target
    target.append(tag)
    target.extend(snapshot)

    ## release snapshot
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](command="release", flags=flags, target=target,),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "released")


def snapshot(*snapshot, **kwargs):
    """
    Creates snapshots with the given names.

    snapshot : string
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

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.snapshot myzpool/mydataset@yesterday [recursive=True]
        salt '*' zfs.snapshot myzpool/mydataset@yesterday myzpool/myotherdataset@yesterday [recursive=True]

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = []

    # NOTE: push filesystem properties
    filesystem_properties = kwargs.get("properties", {})

    # NOTE: set extra config from kwargs
    if kwargs.get("recursive", False):
        flags.append("-r")

    ## Create snapshot
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="snapshot",
            flags=flags,
            filesystem_properties=filesystem_properties,
            target=list(snapshot),
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "snapshotted")


def set(*dataset, **kwargs):
    """
    Sets the property or list of properties to the given value(s) for each dataset.

    dataset : string
        name of snapshot(s), filesystem(s), or volume(s)
    properties : string
        additional zfs properties pairs

    .. note::

        properties are passed as key-value pairs. e.g.

            compression=off

    .. note::

        Only some properties can be edited.

        See the Properties section for more information on what properties
        can be set and acceptable values.

        Numeric values can be specified as exact values, or in a human-readable
        form with a suffix of B, K, M, G, T, P, E (for bytes, kilobytes,
        megabytes, gigabytes, terabytes, petabytes, or exabytes respectively).

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.set myzpool/mydataset compression=off
        salt '*' zfs.set myzpool/mydataset myzpool/myotherdataset compression=off
        salt '*' zfs.set myzpool/mydataset myzpool/myotherdataset compression=lz4 canmount=off

    """
    ## Configure command
    # NOTE: push filesystem properties
    filesystem_properties = salt.utils.args.clean_kwargs(**kwargs)

    ## Set property
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="set",
            property_name=list(filesystem_properties.keys()),
            property_value=list(filesystem_properties.values()),
            target=list(dataset),
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "set")


def get(*dataset, **kwargs):
    """
    Displays properties for the given datasets.

    dataset : string
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
        display numbers in parsable (exact) values (default = True)
        .. versionadded:: 2018.3.0

    .. note::
        If no datasets are specified, then the command displays properties
        for all datasets on the system.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.get
        salt '*' zfs.get myzpool/mydataset [recursive=True|False]
        salt '*' zfs.get myzpool/mydataset properties="sharenfs,mountpoint" [recursive=True|False]
        salt '*' zfs.get myzpool/mydataset myzpool/myotherdataset properties=available fields=value depth=1

    """
    ## Configure command
    # NOTE: initialize the defaults
    flags = ["-H"]
    opts = {}

    # NOTE: set extra config from kwargs
    if kwargs.get("depth", False):
        opts["-d"] = kwargs.get("depth")
    elif kwargs.get("recursive", False):
        flags.append("-r")
    fields = kwargs.get("fields", "value,source").split(",")
    if "name" in fields:  # ensure name is first
        fields.remove("name")
    if "property" in fields:  # ensure property is second
        fields.remove("property")
    fields.insert(0, "name")
    fields.insert(1, "property")
    opts["-o"] = ",".join(fields)
    if kwargs.get("type", False):
        opts["-t"] = kwargs.get("type")
    if kwargs.get("source", False):
        opts["-s"] = kwargs.get("source")

    # NOTE: set property_name
    property_name = kwargs.get("properties", "all")

    ## Get properties
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zfs_command"](
            command="get",
            flags=flags,
            opts=opts,
            property_name=property_name,
            target=list(dataset),
        ),
        python_shell=False,
    )

    ret = __utils__["zfs.parse_command_result"](res)
    if res["retcode"] == 0:
        for ds in res["stdout"].splitlines():
            ds_data = OrderedDict(list(zip(fields, ds.split("\t"))))

            if "value" in ds_data:
                if kwargs.get("parsable", True):
                    ds_data["value"] = __utils__["zfs.from_auto"](
                        ds_data["property"], ds_data["value"],
                    )
                else:
                    ds_data["value"] = __utils__["zfs.to_auto"](
                        ds_data["property"], ds_data["value"], convert_to_human=True,
                    )

            if ds_data["name"] not in ret:
                ret[ds_data["name"]] = OrderedDict()

            ret[ds_data["name"]][ds_data["property"]] = ds_data
            del ds_data["name"]
            del ds_data["property"]

    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
