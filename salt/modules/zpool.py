"""
Module for running ZFS zpool command

:codeauthor:    Nitin Madhok <nmadhok@g.clemson.edu>, Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs
:platform:      illumos,freebsd,linux

.. versionchanged:: 2018.3.1
  Big refactor to remove duplicate code, better type conversions and improved
  consistency in output.

"""

import logging
import os

import salt.utils.decorators
import salt.utils.decorators.path
import salt.utils.path
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

__virtualname__ = "zpool"
__func_alias__ = {
    "import_": "import",
    "list_": "list",
}


def __virtual__():
    """
    Only load when the platform has zfs support
    """
    if __grains__.get("zfs_support"):
        return __virtualname__
    else:
        return False, "The zpool module cannot be loaded: zfs not supported"


def _clean_vdev_config(config):
    """
    Return a simple vdev tree from zpool.status' config section
    """
    cln_config = OrderedDict()
    for label, sub_config in config.items():
        if label not in ["state", "read", "write", "cksum"]:
            sub_config = _clean_vdev_config(sub_config)

            if sub_config and isinstance(cln_config, list):
                cln_config.append(OrderedDict([(label, sub_config)]))
            elif sub_config and isinstance(cln_config, OrderedDict):
                cln_config[label] = sub_config
            elif isinstance(cln_config, list):
                cln_config.append(label)
            elif isinstance(cln_config, OrderedDict):
                new_config = []
                for old_label, old_config in cln_config.items():
                    new_config.append(OrderedDict([(old_label, old_config)]))
                new_config.append(label)
                cln_config = new_config
            else:
                cln_config = [label]

    return cln_config


def healthy():
    """
    Check if all zpools are healthy

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.healthy

    """
    ## collect status output
    # NOTE: we pass the -x flag, by doing this
    #       we will get 'all pools are healthy' on stdout
    #       if all pools are healthy, otherwise we will get
    #       the same output that we expect from zpool status
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"]("status", flags=["-x"]),
        python_shell=False,
    )
    return res["stdout"] == "all pools are healthy"


def status(zpool=None):
    """
    Return the status of the named zpool

    zpool : string
        optional name of storage pool

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.status myzpool

    """
    ret = OrderedDict()

    ## collect status output
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"]("status", target=zpool),
        python_shell=False,
    )

    if res["retcode"] != 0:
        return __utils__["zfs.parse_command_result"](res)

    # NOTE: command output for reference
    # =====================================================================
    #   pool: data
    #  state: ONLINE
    #   scan: scrub repaired 0 in 2h27m with 0 errors on Mon Jan  8 03:27:25 2018
    # config:
    #
    #     NAME                       STATE     READ WRITE CKSUM
    #     data                       ONLINE       0     0     0
    #       mirror-0                 ONLINE       0     0     0
    #         c0tXXXXCXXXXXXXXXXXd0  ONLINE       0     0     0
    #         c0tXXXXCXXXXXXXXXXXd0  ONLINE       0     0     0
    #         c0tXXXXCXXXXXXXXXXXd0  ONLINE       0     0     0
    #
    # errors: No known data errors
    # =====================================================================

    ## parse status output
    # NOTE: output is 'key: value' except for the 'config' key.
    #       multiple pools will repeat the output, so if switch pools if
    #       we see 'pool:'
    current_pool = None
    current_prop = None
    for zpd in res["stdout"].splitlines():
        if zpd.strip() == "":
            continue
        if ":" in zpd and zpd[0] != "\t":
            # NOTE: line is 'key: value' format, we just update a dict
            prop = zpd.split(":")[0].strip()
            value = ":".join(zpd.split(":")[1:]).strip()
            if prop == "pool" and current_pool != value:
                current_pool = value
                ret[current_pool] = OrderedDict()
            if prop != "pool":
                ret[current_pool][prop] = value

            current_prop = prop
        else:
            # NOTE: we append the line output to the last property
            #       this should only happens once we hit the config
            #       section
            ret[current_pool][current_prop] = "{}\n{}".format(
                ret[current_pool][current_prop], zpd
            )

    ## parse config property for each pool
    # NOTE: the config property has some structured data
    #       sadly this data is in a different format than
    #       the rest and it needs further processing
    for pool in ret:
        if "config" not in ret[pool]:
            continue
        header = None
        root_vdev = None
        vdev = None
        dev = None
        rdev = None
        config = ret[pool]["config"]
        config_data = OrderedDict()
        for line in config.splitlines():
            # NOTE: the first line is the header
            #       we grab all the none whitespace values
            if not header:
                header = line.strip().lower()
                header = [x for x in header.split(" ") if x not in [""]]
                continue

            # NOTE: data is indented by 1 tab, then multiples of 2 spaces
            #       to differential root vdev, vdev, and dev
            #
            #       we just strip the initial tab (can't use .strip() here)
            if line[0] == "\t":
                line = line[1:]

            # NOTE: transform data into dict
            stat_data = OrderedDict(
                list(
                    zip(
                        header,
                        [x for x in line.strip().split(" ") if x not in [""]],
                    )
                )
            )

            # NOTE: decode the zfs values properly
            stat_data = __utils__["zfs.from_auto_dict"](stat_data)

            # NOTE: store stat_data in the proper location
            if line.startswith(" " * 6):
                rdev = stat_data["name"]
                config_data[root_vdev][vdev][dev][rdev] = stat_data
            elif line.startswith(" " * 4):
                rdev = None
                dev = stat_data["name"]
                config_data[root_vdev][vdev][dev] = stat_data
            elif line.startswith(" " * 2):
                rdev = dev = None
                vdev = stat_data["name"]
                config_data[root_vdev][vdev] = stat_data
            else:
                rdev = dev = vdev = None
                root_vdev = stat_data["name"]
                config_data[root_vdev] = stat_data

            # NOTE: name already used as identifier, drop duplicate data
            del stat_data["name"]

        ret[pool]["config"] = config_data

    return ret


def iostat(zpool=None, sample_time=5, parsable=True):
    """
    Display I/O statistics for the given pools

    zpool : string
        optional name of storage pool

    sample_time : int
        seconds to capture data before output
        default a sample of 5 seconds is used
    parsable : boolean
        display data in pythonc values (True, False, Bytes,...)

    .. versionadded:: 2016.3.0
    .. versionchanged:: 2018.3.1

        Added ```parsable``` parameter that defaults to True

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.iostat myzpool

    """
    ret = OrderedDict()

    ## get iostat output
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="iostat", flags=["-v"], target=[zpool, sample_time, 2]
        ),
        python_shell=False,
    )

    if res["retcode"] != 0:
        return __utils__["zfs.parse_command_result"](res)

    # NOTE: command output for reference
    # =====================================================================
    #                               capacity     operations    bandwidth
    # pool                       alloc   free   read  write   read  write
    # -------------------------  -----  -----  -----  -----  -----  -----
    # mypool                      648G  1.18T     10      6  1.30M   817K
    #   mirror                    648G  1.18T     10      6  1.30M   817K
    #     c0tXXXXCXXXXXXXXXXXd0      -      -      9      5  1.29M   817K
    #     c0tXXXXCXXXXXXXXXXXd0      -      -      9      5  1.29M   817K
    #     c0tXXXXCXXXXXXXXXXXd0      -      -      9      5  1.29M   817K
    # -------------------------  -----  -----  -----  -----  -----  -----
    # =====================================================================

    ## parse iostat output
    # NOTE: hardcode the header
    #       the double header line is hard to parse, we opt to
    #       hardcode the header fields
    header = [
        "name",
        "capacity-alloc",
        "capacity-free",
        "operations-read",
        "operations-write",
        "bandwidth-read",
        "bandwidth-write",
    ]
    root_vdev = None
    vdev = None
    dev = None
    current_data = OrderedDict()
    for line in res["stdout"].splitlines():
        # NOTE: skip header
        if line.strip() == "" or line.strip().split()[-1] in ["write", "bandwidth"]:
            continue

        # NOTE: reset pool on line separator
        if line.startswith("-") and line.endswith("-"):
            ret.update(current_data)
            current_data = OrderedDict()
            continue

        # NOTE: transform data into dict
        io_data = OrderedDict(
            list(
                zip(
                    header,
                    [x for x in line.strip().split(" ") if x not in [""]],
                )
            )
        )

        # NOTE: normalize values
        if parsable:
            # NOTE: raw numbers and pythonic types
            io_data = __utils__["zfs.from_auto_dict"](io_data)
        else:
            # NOTE: human readable zfs types
            io_data = __utils__["zfs.to_auto_dict"](io_data)

        # NOTE: store io_data in the proper location
        if line.startswith(" " * 4):
            dev = io_data["name"]
            current_data[root_vdev][vdev][dev] = io_data
        elif line.startswith(" " * 2):
            dev = None
            vdev = io_data["name"]
            current_data[root_vdev][vdev] = io_data
        else:
            dev = vdev = None
            root_vdev = io_data["name"]
            current_data[root_vdev] = io_data

        # NOTE: name already used as identifier, drop duplicate data
        del io_data["name"]

    return ret


def list_(properties="size,alloc,free,cap,frag,health", zpool=None, parsable=True):
    """
    .. versionadded:: 2015.5.0

    Return information about (all) storage pools

    zpool : string
        optional name of storage pool

    properties : string
        comma-separated list of properties to list

    parsable : boolean
        display numbers in parsable (exact) values

        .. versionadded:: 2018.3.0

    .. note::

        The ``name`` property will always be included, while the ``frag``
        property will get removed if not available

    zpool : string
        optional zpool

    .. note::

        Multiple storage pool can be provided as a space separated list

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.list
        salt '*' zpool.list zpool=tank
        salt '*' zpool.list 'size,free'
        salt '*' zpool.list 'size,free' tank

    """
    ret = OrderedDict()

    ## update properties
    # NOTE: properties should be a list
    if not isinstance(properties, list):
        properties = properties.split(",")

    # NOTE: name should be first property
    while "name" in properties:
        properties.remove("name")
    properties.insert(0, "name")

    # NOTE: remove 'frags' if we don't have feature flags
    if not __utils__["zfs.has_feature_flags"]():
        while "frag" in properties:
            properties.remove("frag")

    ## collect list output
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="list",
            flags=["-H"],
            opts={"-o": ",".join(properties)},
            target=zpool,
        ),
        python_shell=False,
    )

    if res["retcode"] != 0:
        return __utils__["zfs.parse_command_result"](res)

    # NOTE: command output for reference
    # ========================================================================
    # data  1992864825344   695955501056    1296909324288   34  11%     ONLINE
    # =========================================================================

    ## parse list output
    for line in res["stdout"].splitlines():
        # NOTE: transform data into dict
        zpool_data = OrderedDict(
            list(
                zip(
                    properties,
                    line.strip().split("\t"),
                )
            )
        )

        # NOTE: normalize values
        if parsable:
            # NOTE: raw numbers and pythonic types
            zpool_data = __utils__["zfs.from_auto_dict"](zpool_data)
        else:
            # NOTE: human readable zfs types
            zpool_data = __utils__["zfs.to_auto_dict"](zpool_data)

        ret[zpool_data["name"]] = zpool_data
        del ret[zpool_data["name"]]["name"]

    return ret


def get(zpool, prop=None, show_source=False, parsable=True):
    """
    .. versionadded:: 2016.3.0

    Retrieves the given list of properties

    zpool : string
        Name of storage pool

    prop : string
        Optional name of property to retrieve

    show_source : boolean
        Show source of property

    parsable : boolean
        Display numbers in parsable (exact) values

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.get myzpool

    """
    ret = OrderedDict()
    value_properties = ["name", "property", "value", "source"]

    ## collect get output
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="get",
            flags=["-H"],
            property_name=prop if prop else "all",
            target=zpool,
        ),
        python_shell=False,
    )

    if res["retcode"] != 0:
        return __utils__["zfs.parse_command_result"](res)

    # NOTE: command output for reference
    # ========================================================================
    # ...
    # data  mountpoint  /data   local
    # data  compression off     default
    # ...
    # =========================================================================

    # parse get output
    for line in res["stdout"].splitlines():
        # NOTE: transform data into dict
        prop_data = OrderedDict(
            list(
                zip(
                    value_properties,
                    [x for x in line.strip().split("\t") if x not in [""]],
                )
            )
        )

        # NOTE: older zfs does not have -o, fall back to manually stipping the name field
        del prop_data["name"]

        # NOTE: normalize values
        if parsable:
            # NOTE: raw numbers and pythonic types
            prop_data["value"] = __utils__["zfs.from_auto"](
                prop_data["property"], prop_data["value"]
            )
        else:
            # NOTE: human readable zfs types
            prop_data["value"] = __utils__["zfs.to_auto"](
                prop_data["property"], prop_data["value"]
            )

        # NOTE: show source if requested
        if show_source:
            ret[prop_data["property"]] = prop_data
            del ret[prop_data["property"]]["property"]
        else:
            ret[prop_data["property"]] = prop_data["value"]

    return ret


def set(zpool, prop, value):
    """
    Sets the given property on the specified pool

    zpool : string
        Name of storage pool

    prop : string
        Name of property to set

    value : string
        Value to set for the specified property

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.set myzpool readonly yes

    """
    ret = OrderedDict()

    # set property
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="set",
            property_name=prop,
            property_value=value,
            target=zpool,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "set")


def exists(zpool):
    """
    Check if a ZFS storage pool is active

    zpool : string
        Name of storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.exists myzpool

    """
    # list for zpool
    # NOTE: retcode > 0 if zpool does not exists
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="list",
            target=zpool,
        ),
        python_shell=False,
        ignore_retcode=True,
    )

    return res["retcode"] == 0


def destroy(zpool, force=False):
    """
    Destroys a storage pool

    zpool : string
        Name of storage pool

    force : boolean
        Force destroy of pool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.destroy myzpool

    """
    # destroy zpool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="destroy",
            flags=["-f"] if force else None,
            target=zpool,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "destroyed")


def scrub(zpool, stop=False, pause=False):
    """
    Scrub a storage pool

    zpool : string
        Name of storage pool

    stop : boolean
        If ``True``, cancel ongoing scrub

    pause : boolean
        If ``True``, pause ongoing scrub

        .. versionadded:: 2018.3.0

        .. note::

            Pause is only available on recent versions of ZFS.

            If both ``pause`` and ``stop`` are ``True``, then ``stop`` will
            win.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.scrub myzpool

    """
    ## select correct action
    if stop:
        action = ["-s"]
    elif pause:
        action = ["-p"]
    else:
        action = None

    ## Scrub storage pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="scrub",
            flags=action,
            target=zpool,
        ),
        python_shell=False,
    )

    if res["retcode"] != 0:
        return __utils__["zfs.parse_command_result"](res, "scrubbing")

    ret = OrderedDict()
    if stop or pause:
        ret["scrubbing"] = False
    else:
        ret["scrubbing"] = True
    return ret


def create(zpool, *vdevs, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Create a simple zpool, a mirrored zpool, a zpool having nested VDEVs, a hybrid zpool with cache, spare and log drives or a zpool with RAIDZ-1, RAIDZ-2 or RAIDZ-3

    zpool : string
        Name of storage pool

    vdevs : string
        One or move devices

    force : boolean
        Forces use of vdevs, even if they appear in use or specify a
        conflicting replication level.

    mountpoint : string
        Sets the mount point for the root dataset

    altroot : string
        Equivalent to "-o cachefile=none,altroot=root"

    properties : dict
        Additional pool properties

    filesystem_properties : dict
        Additional filesystem properties

    createboot : boolean
        create a boot partition

        .. versionadded:: 2018.3.0

        .. warning:
          This is only available on illumos and Solaris

    CLI Examples:

    .. code-block:: bash

        salt '*' zpool.create myzpool /path/to/vdev1 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 /path/to/vdev2 [...] [force=True|False]
        salt '*' zpool.create myzpool raidz1 /path/to/vdev1 /path/to/vdev2 raidz2 /path/to/vdev3 /path/to/vdev4 /path/to/vdev5 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 [...] mirror /path/to/vdev2 /path/to/vdev3 [...] [force=True|False]
        salt '*' zpool.create myhybridzpool mirror /tmp/file1 [...] log mirror /path/to/vdev1 [...] cache /path/to/vdev2 [...] spare /path/to/vdev3 [...] [force=True|False]

    .. note::

        Zpool properties can be specified at the time of creation of the pool
        by passing an additional argument called "properties" and specifying
        the properties with their respective values in the form of a python
        dictionary:

        .. code-block:: text

            properties="{'property1': 'value1', 'property2': 'value2'}"

        Filesystem properties can be specified at the time of creation of the
        pool by passing an additional argument called "filesystem_properties"
        and specifying the properties with their respective values in the form
        of a python dictionary:

        .. code-block:: text

            filesystem_properties="{'property1': 'value1', 'property2': 'value2'}"

        Example:

        .. code-block:: bash

            salt '*' zpool.create myzpool /path/to/vdev1 [...] properties="{'property1': 'value1', 'property2': 'value2'}"

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create myzpool /path/to/vdev1 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 /path/to/vdev2 [...] [force=True|False]
        salt '*' zpool.create myzpool raidz1 /path/to/vdev1 /path/to/vdev2 raidz2 /path/to/vdev3 /path/to/vdev4 /path/to/vdev5 [...] [force=True|False]
        salt '*' zpool.create myzpool mirror /path/to/vdev1 [...] mirror /path/to/vdev2 /path/to/vdev3 [...] [force=True|False]
        salt '*' zpool.create myhybridzpool mirror /tmp/file1 [...] log mirror /path/to/vdev1 [...] cache /path/to/vdev2 [...] spare /path/to/vdev3 [...] [force=True|False]

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    opts = {}
    target = []

    # NOTE: push pool and filesystem properties
    pool_properties = kwargs.get("properties", {})
    filesystem_properties = kwargs.get("filesystem_properties", {})

    # NOTE: set extra config based on kwargs
    if kwargs.get("force", False):
        flags.append("-f")
    if kwargs.get("createboot", False) or "bootsize" in pool_properties:
        flags.append("-B")
    if kwargs.get("altroot", False):
        opts["-R"] = kwargs.get("altroot")
    if kwargs.get("mountpoint", False):
        opts["-m"] = kwargs.get("mountpoint")

    # NOTE: append the pool name and specifications
    target.append(zpool)
    target.extend(vdevs)

    ## Create storage pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="create",
            flags=flags,
            opts=opts,
            pool_properties=pool_properties,
            filesystem_properties=filesystem_properties,
            target=target,
        ),
        python_shell=False,
    )

    ret = __utils__["zfs.parse_command_result"](res, "created")
    if ret["created"]:
        ## NOTE: lookup zpool status for vdev config
        ret["vdevs"] = _clean_vdev_config(
            __salt__["zpool.status"](zpool=zpool)[zpool]["config"][zpool],
        )

    return ret


def add(zpool, *vdevs, **kwargs):
    """
    Add the specified vdev\'s to the given storage pool

    zpool : string
        Name of storage pool

    vdevs : string
        One or more devices

    force : boolean
        Forces use of device

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.add myzpool /path/to/vdev1 /path/to/vdev2 [...]

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config based on kwargs
    if kwargs.get("force", False):
        flags.append("-f")

    # NOTE: append the pool name and specifications
    target.append(zpool)
    target.extend(vdevs)

    ## Update storage pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="add",
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    ret = __utils__["zfs.parse_command_result"](res, "added")
    if ret["added"]:
        ## NOTE: lookup zpool status for vdev config
        ret["vdevs"] = _clean_vdev_config(
            __salt__["zpool.status"](zpool=zpool)[zpool]["config"][zpool],
        )

    return ret


def attach(zpool, device, new_device, force=False):
    """
    Attach specified device to zpool

    zpool : string
        Name of storage pool

    device : string
        Existing device name too

    new_device : string
        New device name (to be attached to ``device``)

    force : boolean
        Forces use of device

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.attach myzpool /path/to/vdev1 /path/to/vdev2 [...]

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config
    if force:
        flags.append("-f")

    # NOTE: append the pool name and specifications
    target.append(zpool)
    target.append(device)
    target.append(new_device)

    ## Update storage pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="attach",
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    ret = __utils__["zfs.parse_command_result"](res, "attached")
    if ret["attached"]:
        ## NOTE: lookup zpool status for vdev config
        ret["vdevs"] = _clean_vdev_config(
            __salt__["zpool.status"](zpool=zpool)[zpool]["config"][zpool],
        )

    return ret


def detach(zpool, device):
    """
    Detach specified device to zpool

    zpool : string
        Name of storage pool

    device : string
        Device to detach

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.detach myzpool /path/to/vdev1

    """
    ## Update storage pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="detach",
            target=[zpool, device],
        ),
        python_shell=False,
    )

    ret = __utils__["zfs.parse_command_result"](res, "detatched")
    if ret["detatched"]:
        ## NOTE: lookup zpool status for vdev config
        ret["vdevs"] = _clean_vdev_config(
            __salt__["zpool.status"](zpool=zpool)[zpool]["config"][zpool],
        )

    return ret


def split(zpool, newzpool, **kwargs):
    """
    .. versionadded:: 2018.3.0

    Splits devices off pool creating newpool.

    .. note::

        All vdevs in pool must be mirrors.  At the time of the split,
        ``newzpool`` will be a replica of ``zpool``.

        After splitting, do not forget to import the new pool!

    zpool : string
        Name of storage pool

    newzpool : string
        Name of new storage pool

    mountpoint : string
        Sets the mount point for the root dataset

    altroot : string
        Sets altroot for newzpool

    properties : dict
        Additional pool properties for newzpool

    CLI Examples:

    .. code-block:: bash

        salt '*' zpool.split datamirror databackup
        salt '*' zpool.split datamirror databackup altroot=/backup

    .. note::

        Zpool properties can be specified at the time of creation of the pool
        by passing an additional argument called "properties" and specifying
        the properties with their respective values in the form of a python
        dictionary:

        .. code-block:: text

            properties="{'property1': 'value1', 'property2': 'value2'}"

        Example:

        .. code-block:: bash

            salt '*' zpool.split datamirror databackup properties="{'readonly': 'on'}"

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.split datamirror databackup
        salt '*' zpool.split datamirror databackup altroot=/backup

    """
    ## Configure pool
    # NOTE: initialize the defaults
    opts = {}

    # NOTE: push pool and filesystem properties
    pool_properties = kwargs.get("properties", {})

    # NOTE: set extra config based on kwargs
    if kwargs.get("altroot", False):
        opts["-R"] = kwargs.get("altroot")

    ## Split storage pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="split",
            opts=opts,
            pool_properties=pool_properties,
            target=[zpool, newzpool],
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "split")


def replace(zpool, old_device, new_device=None, force=False):
    """
    Replaces ``old_device`` with ``new_device``

    .. note::

        This is equivalent to attaching ``new_device``,
        waiting for it to resilver, and then detaching ``old_device``.

        The size of ``new_device`` must be greater than or equal to the minimum
        size of all the devices in a mirror or raidz configuration.

    zpool : string
        Name of storage pool

    old_device : string
        Old device to replace

    new_device : string
        Optional new device

    force : boolean
        Forces use of new_device, even if its appears to be in use.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.replace myzpool /path/to/vdev1 /path/to/vdev2

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config
    if force:
        flags.append("-f")

    # NOTE: append the pool name and specifications
    target.append(zpool)
    target.append(old_device)
    if new_device:
        target.append(new_device)

    ## Replace device
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="replace",
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    ret = __utils__["zfs.parse_command_result"](res, "replaced")
    if ret["replaced"]:
        ## NOTE: lookup zpool status for vdev config
        ret["vdevs"] = _clean_vdev_config(
            __salt__["zpool.status"](zpool=zpool)[zpool]["config"][zpool],
        )

    return ret


@salt.utils.decorators.path.which("mkfile")
def create_file_vdev(size, *vdevs):
    """
    Creates file based virtual devices for a zpool

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.create_file_vdev 7G /path/to/vdev1 [/path/to/vdev2] [...]

    .. note::

        Depending on file size, the above command may take a while to return.

    """
    ret = OrderedDict()
    err = OrderedDict()

    _mkfile_cmd = salt.utils.path.which("mkfile")
    for vdev in vdevs:
        if os.path.isfile(vdev):
            ret[vdev] = "existed"
        else:
            res = __salt__["cmd.run_all"](
                "{mkfile} {size} {vdev}".format(
                    mkfile=_mkfile_cmd,
                    size=size,
                    vdev=vdev,
                ),
                python_shell=False,
            )
            if res["retcode"] != 0:
                if "stderr" in res and ":" in res["stderr"]:
                    ret[vdev] = "failed"
                    err[vdev] = ":".join(res["stderr"].strip().split(":")[1:])
            else:
                ret[vdev] = "created"
    if err:
        ret["error"] = err

    return ret


def export(*pools, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Export storage pools

    pools : string
        One or more storage pools to export

    force : boolean
        Force export of storage pools

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.export myzpool ... [force=True|False]
        salt '*' zpool.export myzpool2 myzpool2 ... [force=True|False]

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    targets = []

    # NOTE: set extra config based on kwargs
    if kwargs.get("force", False):
        flags.append("-f")

    # NOTE: append the pool name and specifications
    targets = list(pools)

    ## Export pools
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="export",
            flags=flags,
            target=targets,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "exported")


def import_(zpool=None, new_name=None, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Import storage pools or list pools available for import

    zpool : string
        Optional name of storage pool

    new_name : string
        Optional new name for the storage pool

    mntopts : string
        Comma-separated list of mount options to use when mounting datasets
        within the pool.

    force : boolean
        Forces import, even if the pool appears to be potentially active.

    altroot : string
        Equivalent to "-o cachefile=none,altroot=root"

    dir : string
        Searches for devices or files in dir, multiple dirs can be specified as
        follows: ``dir="dir1,dir2"``

    no_mount : boolean
        Import the pool without mounting any file systems.

    only_destroyed : boolean
        Imports destroyed pools only. This also sets ``force=True``.

    recovery : bool|str
        false: do not try to recovery broken pools
        true: try to recovery the pool by rolling back the latest transactions
        test: check if a pool can be recovered, but don't import it
        nolog: allow import without log device, recent transactions might be lost

        .. note::
            If feature flags are not support this forced to the default of 'false'

        .. warning::
            When recovery is set to 'test' the result will be have imported set to True if the pool
            can be imported. The pool might also be imported if the pool was not broken to begin with.

    properties : dict
        Additional pool properties

    .. note::

        Zpool properties can be specified at the time of creation of the pool
        by passing an additional argument called "properties" and specifying
        the properties with their respective values in the form of a python
        dictionary:

        .. code-block:: text

            properties="{'property1': 'value1', 'property2': 'value2'}"

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.import [force=True|False]
        salt '*' zpool.import myzpool [mynewzpool] [force=True|False]
        salt '*' zpool.import myzpool dir='/tmp'

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    opts = {}
    target = []

    # NOTE: push pool and filesystem properties
    pool_properties = kwargs.get("properties", {})

    # NOTE: set extra config based on kwargs
    if kwargs.get("force", False) or kwargs.get("only_destroyed", False):
        flags.append("-f")
    if kwargs.get("only_destroyed", False):
        flags.append("-D")
    if kwargs.get("no_mount", False):
        flags.append("-N")
    if kwargs.get("altroot", False):
        opts["-R"] = kwargs.get("altroot")
    if kwargs.get("mntopts", False):
        # NOTE: -o is used for both mount options and pool properties!
        #       ```-o nodevices,noexec,nosetuid,ro``` vs ```-o prop=val```
        opts["-o"] = kwargs.get("mntopts")
    if kwargs.get("dir", False):
        opts["-d"] = kwargs.get("dir").split(",")
    if kwargs.get("recovery", False) and __utils__["zfs.has_feature_flags"]():
        recovery = kwargs.get("recovery")
        if recovery in [True, "test"]:
            flags.append("-F")
        if recovery == "test":
            flags.append("-n")
        if recovery == "nolog":
            flags.append("-m")

    # NOTE: append the pool name and specifications
    if zpool:
        target.append(zpool)
        target.append(new_name)
    else:
        flags.append("-a")

    ## Import storage pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="import",
            flags=flags,
            opts=opts,
            pool_properties=pool_properties,
            target=target,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "imported")


def online(zpool, *vdevs, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Ensure that the specified devices are online

    zpool : string
        name of storage pool

    vdevs : string
        one or more devices

    expand : boolean
        Expand the device to use all available space.

        .. note::

            If the device is part of a mirror or raidz then all devices must be
            expanded before the new space will become available to the pool.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.online myzpool /path/to/vdev1 [...]

    """
    ## Configure pool
    # default options
    flags = []
    target = []

    # set flags and options
    if kwargs.get("expand", False):
        flags.append("-e")
    target.append(zpool)
    if vdevs:
        target.extend(vdevs)

    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config based on kwargs
    if kwargs.get("expand", False):
        flags.append("-e")

    # NOTE: append the pool name and specifications
    target.append(zpool)
    target.extend(vdevs)

    ## Bring online device
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="online",
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "onlined")


def offline(zpool, *vdevs, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Ensure that the specified devices are offline

    .. warning::

        By default, the ``OFFLINE`` state is persistent. The device remains
        offline when the system is rebooted. To temporarily take a device
        offline, use ``temporary=True``.

    zpool : string
        name of storage pool

    vdevs : string
        One or more devices

    temporary : boolean
        Enable temporarily offline

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.offline myzpool /path/to/vdev1 [...] [temporary=True|False]

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    target = []

    # NOTE: set extra config based on kwargs
    if kwargs.get("temporary", False):
        flags.append("-t")

    # NOTE: append the pool name and specifications
    target.append(zpool)
    target.extend(vdevs)

    ## Take a device offline
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="offline",
            flags=flags,
            target=target,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "offlined")


def labelclear(device, force=False):
    """
    .. versionadded:: 2018.3.0

    Removes ZFS label information from the specified device

    device : string
        Device name; must not be part of an active pool configuration.

    force : boolean
        Treat exported or foreign devices as inactive

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.labelclear /path/to/dev

    """
    ## clear label for all specified device
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="labelclear",
            flags=["-f"] if force else None,
            target=device,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "labelcleared")


def clear(zpool, device=None):
    """
    Clears device errors in a pool.

    .. warning::

        The device must not be part of an active pool configuration.

    zpool : string
        name of storage pool
    device : string
        (optional) specific device to clear

    .. versionadded:: 2018.3.1

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.clear mypool
        salt '*' zpool.clear mypool /path/to/dev

    """
    ## Configure pool
    # NOTE: initialize the defaults
    target = []

    # NOTE: append the pool name and specifications
    target.append(zpool)
    target.append(device)

    ## clear storage pool errors
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="clear",
            target=target,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "cleared")


def reguid(zpool):
    """
    Generates a new unique identifier for the pool

    .. warning::
        You must ensure that all devices in this pool are online and healthy
        before performing this action.

    zpool : string
        name of storage pool

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.reguid myzpool
    """
    ## generate new GUID for pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="reguid",
            target=zpool,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "reguided")


def reopen(zpool):
    """
    Reopen all the vdevs associated with the pool

    zpool : string
        name of storage pool

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.reopen myzpool

    """
    ## reopen all devices fro pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="reopen",
            target=zpool,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "reopened")


def upgrade(zpool=None, version=None):
    """
    .. versionadded:: 2016.3.0

    Enables all supported features on the given pool

    zpool : string
        Optional storage pool, applies to all otherwize

    version : int
        Version to upgrade to, if unspecified upgrade to the highest possible

    .. warning::
        Once this is done, the pool will no longer be accessible on systems that do not
        support feature flags. See zpool-features(5) for details on compatibility with
        systems that support feature flags, but do not support all features enabled on the pool.

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.upgrade myzpool

    """
    ## Configure pool
    # NOTE: initialize the defaults
    flags = []
    opts = {}

    # NOTE: set extra config
    if version:
        opts["-V"] = version
    if not zpool:
        flags.append("-a")

    ## Upgrade pool
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="upgrade",
            flags=flags,
            opts=opts,
            target=zpool,
        ),
        python_shell=False,
    )

    return __utils__["zfs.parse_command_result"](res, "upgraded")


def history(zpool=None, internal=False, verbose=False):
    """
    .. versionadded:: 2016.3.0

    Displays the command history of the specified pools, or all pools if no
    pool is specified

    zpool : string
        Optional storage pool

    internal : boolean
        Toggle display of internally logged ZFS events

    verbose : boolean
        Toggle display of the user name, the hostname, and the zone in which
        the operation was performed

    CLI Example:

    .. code-block:: bash

        salt '*' zpool.upgrade myzpool

    """
    ret = OrderedDict()

    ## Configure pool
    # NOTE: initialize the defaults
    flags = []

    # NOTE: set extra config
    if verbose:
        flags.append("-l")
    if internal:
        flags.append("-i")

    ## Lookup history
    res = __salt__["cmd.run_all"](
        __utils__["zfs.zpool_command"](
            command="history",
            flags=flags,
            target=zpool,
        ),
        python_shell=False,
    )

    if res["retcode"] != 0:
        return __utils__["zfs.parse_command_result"](res)
    else:
        pool = "unknown"
        for line in res["stdout"].splitlines():
            if line.startswith("History for"):
                pool = line[13:-2]
                ret[pool] = OrderedDict()
            else:
                if line == "":
                    continue
                log_timestamp = line[0:19]
                log_command = line[20:]
                ret[pool][log_timestamp] = log_command

    return ret
