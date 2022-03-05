"""
States for managing zfs datasets

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs, salt.modules.zfs
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: 2016.3.0
.. versionchanged:: 2018.3.1
  Big refactor to remove duplicate code, better type conversions and improved
  consistency in output.

.. code-block:: yaml

    test/shares/yuki:
      zfs.filesystem_present:
        - create_parent: true
        - properties:
            quota: 16G

    test/iscsi/haruhi:
      zfs.volume_present:
        - create_parent: true
        - volume_size: 16M
        - sparse: true
        - properties:
            readonly: on

    test/shares/yuki@frozen:
      zfs.snapshot_present

    moka_origin:
      zfs.hold_present:
        - snapshot: test/shares/yuki@frozen

    test/shares/moka:
      zfs.filesystem_present:
        - cloned_from: test/shares/yuki@frozen

    test/shares/moka@tsukune:
      zfs.snapshot_absent

"""

import logging
from datetime import datetime

from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = "zfs"

# Compare modifiers for zfs.schedule_snapshot
comp_hour = {"minute": 0}
comp_day = {"minute": 0, "hour": 0}
comp_month = {"minute": 0, "hour": 0, "day": 1}
comp_year = {"minute": 0, "hour": 0, "day": 1, "month": 1}


def __virtual__():
    """
    Provides zfs state
    """
    if not __grains__.get("zfs_support"):
        return False, "The zfs state cannot be loaded: zfs not supported"
    return __virtualname__


def _absent(name, dataset_type, force=False, recursive=False):
    """
    internal shared function for *_absent

    name : string
        name of dataset
    dataset_type : string [filesystem, volume, snapshot, or bookmark]
        type of dataset to remove
    force : boolean
        try harder to destroy the dataset
    recursive : boolean
        also destroy all the child datasets

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## log configuration
    dataset_type = dataset_type.lower()
    log.debug("zfs.%s_absent::%s::config::force = %s", dataset_type, name, force)
    log.debug(
        "zfs.%s_absent::%s::config::recursive = %s", dataset_type, name, recursive
    )

    ## destroy dataset if needed
    if __salt__["zfs.exists"](name, **{"type": dataset_type}):
        ## NOTE: dataset found with the name and dataset_type
        if not __opts__["test"]:
            mod_res = __salt__["zfs.destroy"](
                name, **{"force": force, "recursive": recursive}
            )
        else:
            mod_res = OrderedDict([("destroyed", True)])

        ret["result"] = mod_res["destroyed"]
        if ret["result"]:
            ret["changes"][name] = "destroyed"
            ret["comment"] = "{} {} was destroyed".format(
                dataset_type,
                name,
            )
        else:
            ret["comment"] = "failed to destroy {} {}".format(
                dataset_type,
                name,
            )
            if "error" in mod_res:
                ret["comment"] = mod_res["error"]
    else:
        ## NOTE: no dataset found with name of the dataset_type
        ret["comment"] = "{} {} is absent".format(dataset_type, name)

    return ret


def filesystem_absent(name, force=False, recursive=False):
    """
    ensure filesystem is absent on the system

    name : string
        name of filesystem
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    .. warning::

        If a volume with ``name`` exists, this state will succeed without
        destroying the volume specified by ``name``. This module is dataset type sensitive.

    """
    if not __utils__["zfs.is_dataset"](name):
        ret = {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "invalid dataset name: {}".format(name),
        }
    else:
        ret = _absent(name, "filesystem", force, recursive)
    return ret


def volume_absent(name, force=False, recursive=False):
    """
    ensure volume is absent on the system

    name : string
        name of volume
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    .. warning::

        If a filesystem with ``name`` exists, this state will succeed without
        destroying the filesystem specified by ``name``. This module is dataset type sensitive.

    """
    if not __utils__["zfs.is_dataset"](name):
        ret = {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "invalid dataset name: {}".format(name),
        }
    else:
        ret = _absent(name, "volume", force, recursive)
    return ret


def snapshot_absent(name, force=False, recursive=False):
    """
    ensure snapshot is absent on the system

    name : string
        name of snapshot
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    """
    if not __utils__["zfs.is_snapshot"](name):
        ret = {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "invalid snapshot name: {}".format(name),
        }
    else:
        ret = _absent(name, "snapshot", force, recursive)
    return ret


def bookmark_absent(name, force=False, recursive=False):
    """
    ensure bookmark is absent on the system

    name : string
        name of snapshot
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    """
    if not __utils__["zfs.is_bookmark"](name):
        ret = {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "invalid bookmark name: {}".format(name),
        }
    else:
        ret = _absent(name, "bookmark", force, recursive)
    return ret


def hold_absent(name, snapshot, recursive=False):
    """
    ensure hold is absent on the system

    name : string
        name of hold
    snapshot : string
        name of snapshot
    recursive : boolean
        recursively releases a hold with the given tag on the snapshots of all descendent file systems.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## log configuration
    log.debug("zfs.hold_absent::%s::config::snapshot = %s", name, snapshot)
    log.debug("zfs.hold_absent::%s::config::recursive = %s", name, recursive)

    ## check we have a snapshot/tag name
    if not __utils__["zfs.is_snapshot"](snapshot):
        ret["result"] = False
        ret["comment"] = "invalid snapshot name: {}".format(snapshot)
        return ret

    if (
        __utils__["zfs.is_snapshot"](name)
        or __utils__["zfs.is_bookmark"](name)
        or name == "error"
    ):
        ret["result"] = False
        ret["comment"] = "invalid tag name: {}".format(name)
        return ret

    ## release hold if required
    holds = __salt__["zfs.holds"](snapshot)
    if name in holds:
        ## NOTE: hold found for snapshot, release it
        if not __opts__["test"]:
            mod_res = __salt__["zfs.release"](
                name, snapshot, **{"recursive": recursive}
            )
        else:
            mod_res = OrderedDict([("released", True)])

        ret["result"] = mod_res["released"]
        if ret["result"]:
            ret["changes"] = {snapshot: {name: "released"}}
            ret["comment"] = "hold {} released".format(
                name,
            )
        else:
            ret["comment"] = "failed to release hold {}".format(
                name,
            )
            if "error" in mod_res:
                ret["comment"] = mod_res["error"]
    elif "error" in holds:
        ## NOTE: we have an error
        ret["result"] = False
        ret["comment"] = holds["error"]
    else:
        ## NOTE: no hold found with name for snapshot
        ret["comment"] = "hold {} is absent".format(
            name,
        )

    return ret


def hold_present(name, snapshot, recursive=False):
    """
    ensure hold is present on the system

    name : string
        name of holdt
    snapshot : string
        name of snapshot
    recursive : boolean
        recursively add hold with the given tag on the snapshots of all descendent file systems.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## log configuration
    log.debug("zfs.hold_present::%s::config::snapshot = %s", name, snapshot)
    log.debug("zfs.hold_present::%s::config::recursive = %s", name, recursive)

    ## check we have a snapshot/tag name
    if not __utils__["zfs.is_snapshot"](snapshot):
        ret["result"] = False
        ret["comment"] = "invalid snapshot name: {}".format(snapshot)
        return ret

    if (
        __utils__["zfs.is_snapshot"](name)
        or __utils__["zfs.is_bookmark"](name)
        or name == "error"
    ):
        ret["result"] = False
        ret["comment"] = "invalid tag name: {}".format(name)
        return ret

    ## place hold if required
    holds = __salt__["zfs.holds"](snapshot)
    if name in holds:
        ## NOTE: hold with name already exists for snapshot
        ret["comment"] = "hold {} is present for {}".format(
            name,
            snapshot,
        )
    else:
        ## NOTE: no hold found with name for snapshot
        if not __opts__["test"]:
            mod_res = __salt__["zfs.hold"](name, snapshot, **{"recursive": recursive})
        else:
            mod_res = OrderedDict([("held", True)])

        ret["result"] = mod_res["held"]
        if ret["result"]:
            ret["changes"] = OrderedDict([(snapshot, OrderedDict([(name, "held")]))])
            ret["comment"] = "hold {} added to {}".format(name, snapshot)
        else:
            ret["comment"] = "failed to add hold {} to {}".format(name, snapshot)
            if "error" in mod_res:
                ret["comment"] = mod_res["error"]

    return ret


def _dataset_present(
    dataset_type,
    name,
    properties,
    volume_size=None,
    sparse=False,
    create_parent=False,
    cloned_from=None,
):
    """
    internal handler for filesystem_present/volume_present

    dataset_type : string
        volume or filesystem
    name : string
        name of volume
    volume_size : string
        size of volume
    sparse : boolean
        create sparse volume
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    cloned_from : string
        name of snapshot to clone
    properties : dict
        additional zfs properties (-o)

    .. note::
        ``cloned_from`` is only use if the volume does not exist yet,
        when ``cloned_from`` is set after the volume exists it will be ignored.

    .. note::
        Properties do not get cloned, if you specify the properties in the state file
        they will be applied on a subsequent run.

        ``volume_size`` is considered a property, so the volume's size will be
        corrected when the properties get updated if it differs from the
        original volume.

        The sparse parameter is ignored when using ``cloned_from``.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## fallback dataset_type to filesystem if out of range
    if dataset_type not in ["filesystem", "volume"]:
        dataset_type = "filesystem"

    ## ensure properties are zfs values
    if properties is None:
        properties = {}
    properties = __utils__["zfs.from_auto_dict"](properties)
    if volume_size:
        ## NOTE: add volsize to properties
        volume_size = __utils__["zfs.from_size"](volume_size)
        properties.update({"volsize": volume_size})
    # The sorted isn't necessary for proper behavior, but it helps for the unit
    # tests.
    propnames = ",".join(sorted(properties.keys()))

    ## log configuration
    log.debug(
        "zfs.%s_present::%s::config::volume_size = %s", dataset_type, name, volume_size
    )
    log.debug("zfs.%s_present::%s::config::sparse = %s", dataset_type, name, sparse)
    log.debug(
        "zfs.%s_present::%s::config::create_parent = %s",
        dataset_type,
        name,
        create_parent,
    )
    log.debug(
        "zfs.%s_present::%s::config::cloned_from = %s", dataset_type, name, cloned_from
    )
    log.debug(
        "zfs.%s_present::%s::config::properties = %s", dataset_type, name, properties
    )

    ## check we have valid filesystem name/volume name/clone snapshot
    if not __utils__["zfs.is_dataset"](name):
        ret["result"] = False
        ret["comment"] = "invalid dataset name: {}".format(name)
        return ret

    if cloned_from and not __utils__["zfs.is_snapshot"](cloned_from):
        ret["result"] = False
        ret["comment"] = "{} is not a snapshot".format(cloned_from)
        return ret

    ## ensure dataset is in correct state
    ## NOTE: update the dataset
    exists = __salt__["zfs.exists"](name, **{"type": dataset_type})
    if exists and len(properties) == 0:
        ret["comment"] = "{} {} is uptodate".format(dataset_type, name)
    elif exists and len(properties) > 0:
        ## NOTE: fetch current volume properties
        properties_current = __salt__["zfs.get"](
            name,
            properties=propnames,
            type=dataset_type,
            fields="value",
            depth=0,
            parsable=True,
        ).get(name, OrderedDict())

        ## NOTE: build list of properties to update
        properties_update = []
        for prop in properties:
            ## NOTE: skip unexisting properties
            if prop not in properties_current:
                log.warning(
                    "zfs.%s_present::%s::update - unknown property: %s",
                    dataset_type,
                    name,
                    prop,
                )
                continue

            ## NOTE: compare current and wanted value
            if properties_current[prop]["value"] != properties[prop]:
                properties_update.append(prop)

        ## NOTE: update pool properties
        for prop in properties_update:
            if not __opts__["test"]:
                mod_res = __salt__["zfs.set"](name, **{prop: properties[prop]})
            else:
                mod_res = OrderedDict([("set", True)])

            if mod_res["set"]:
                if name not in ret["changes"]:
                    ret["changes"][name] = {}
                ret["changes"][name][prop] = properties[prop]
            else:
                ret["result"] = False
                if ret["comment"] == "":
                    ret["comment"] = "The following properties were not updated:"
                ret["comment"] = "{} {}".format(ret["comment"], prop)

        ## NOTE: update comment
        if ret["result"] and name in ret["changes"]:
            ret["comment"] = "{} {} was updated".format(dataset_type, name)
        elif ret["result"]:
            ret["comment"] = "{} {} is uptodate".format(dataset_type, name)
        else:
            ret["comment"] = "{} {} failed to be updated".format(dataset_type, name)

    ## NOTE: create or clone the dataset
    elif not exists:
        mod_res_action = "cloned" if cloned_from else "created"
        if __opts__["test"]:
            ## NOTE: pretend to create/clone
            mod_res = OrderedDict([(mod_res_action, True)])
        elif cloned_from:
            ## NOTE: add volsize to properties
            if volume_size:
                properties["volsize"] = volume_size

            ## NOTE: clone the dataset
            mod_res = __salt__["zfs.clone"](
                cloned_from,
                name,
                **{"create_parent": create_parent, "properties": properties}
            )
        else:
            ## NOTE: create the dataset
            mod_res = __salt__["zfs.create"](
                name,
                **{
                    "create_parent": create_parent,
                    "properties": properties,
                    "volume_size": volume_size,
                    "sparse": sparse,
                }
            )

        ret["result"] = mod_res[mod_res_action]
        if ret["result"]:
            ret["changes"][name] = mod_res_action
            if properties:
                ret["changes"][name] = properties
            ret["comment"] = "{} {} was {}".format(
                dataset_type,
                name,
                mod_res_action,
            )
        else:
            ret["comment"] = "failed to {} {} {}".format(
                mod_res_action[:-1],
                dataset_type,
                name,
            )
            if "error" in mod_res:
                ret["comment"] = mod_res["error"]

    return ret


def filesystem_present(name, create_parent=False, properties=None, cloned_from=None):
    """
    ensure filesystem exists and has properties set

    name : string
        name of filesystem
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    cloned_from : string
        name of snapshot to clone
    properties : dict
        additional zfs properties (-o)

    .. note::
        ``cloned_from`` is only use if the filesystem does not exist yet,
        when ``cloned_from`` is set after the filesystem exists it will be ignored.

    .. note::
        Properties do not get cloned, if you specify the properties in the
        state file they will be applied on a subsequent run.

    """
    return _dataset_present(
        "filesystem",
        name,
        properties,
        create_parent=create_parent,
        cloned_from=cloned_from,
    )


def volume_present(
    name,
    volume_size,
    sparse=False,
    create_parent=False,
    properties=None,
    cloned_from=None,
):
    """
    ensure volume exists and has properties set

    name : string
        name of volume
    volume_size : string
        size of volume
    sparse : boolean
        create sparse volume
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    cloned_from : string
        name of snapshot to clone
    properties : dict
        additional zfs properties (-o)

    .. note::
        ``cloned_from`` is only use if the volume does not exist yet,
        when ``cloned_from`` is set after the volume exists it will be ignored.

    .. note::
        Properties do not get cloned, if you specify the properties in the state file
        they will be applied on a subsequent run.

        ``volume_size`` is considered a property, so the volume's size will be
        corrected when the properties get updated if it differs from the
        original volume.

        The sparse parameter is ignored when using ``cloned_from``.

    """
    return _dataset_present(
        "volume",
        name,
        properties,
        volume_size,
        sparse=sparse,
        create_parent=create_parent,
        cloned_from=cloned_from,
    )


def bookmark_present(name, snapshot):
    """
    ensure bookmark exists

    name : string
        name of bookmark
    snapshot : string
        name of snapshot

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## log configuration
    log.debug("zfs.bookmark_present::%s::config::snapshot = %s", name, snapshot)

    ## check we have valid snapshot/bookmark name
    if not __utils__["zfs.is_snapshot"](snapshot):
        ret["result"] = False
        ret["comment"] = "invalid snapshot name: {}".format(name)
        return ret

    if "#" not in name and "/" not in name:
        ## NOTE: simple snapshot name
        #        take the snapshot name and replace the snapshot but with the simple name
        #        e.g. pool/fs@snap + bm --> pool/fs#bm
        name = "{}#{}".format(snapshot[: snapshot.index("@")], name)
        ret["name"] = name

    if not __utils__["zfs.is_bookmark"](name):
        ret["result"] = False
        ret["comment"] = "invalid bookmark name: {}".format(name)
        return ret

    ## ensure bookmark exists
    if not __salt__["zfs.exists"](name, **{"type": "bookmark"}):
        ## NOTE: bookmark the snapshot
        if not __opts__["test"]:
            mod_res = __salt__["zfs.bookmark"](snapshot, name)
        else:
            mod_res = OrderedDict([("bookmarked", True)])

        ret["result"] = mod_res["bookmarked"]
        if ret["result"]:
            ret["changes"][name] = snapshot
            ret["comment"] = "{} bookmarked as {}".format(snapshot, name)
        else:
            ret["comment"] = "failed to bookmark {}".format(snapshot)
            if "error" in mod_res:
                ret["comment"] = mod_res["error"]
    else:
        ## NOTE: bookmark already exists
        ret["comment"] = "bookmark is present"

    return ret


def snapshot_present(name, recursive=False, properties=None):
    """
    ensure snapshot exists and has properties set

    name : string
        name of snapshot
    recursive : boolean
        recursively create snapshots of all descendent datasets
    properties : dict
        additional zfs properties (-o)

    .. note:
        Properties are only set at creation time

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## log configuration
    log.debug("zfs.snapshot_present::%s::config::recursive = %s", name, recursive)
    log.debug("zfs.snapshot_present::%s::config::properties = %s", name, properties)

    ## ensure properties are zfs values
    if properties:
        properties = __utils__["zfs.from_auto_dict"](properties)

    ## check we have valid snapshot name
    if not __utils__["zfs.is_snapshot"](name):
        ret["result"] = False
        ret["comment"] = "invalid snapshot name: {}".format(name)
        return ret

    ## ensure snapshot exits
    if not __salt__["zfs.exists"](name, **{"type": "snapshot"}):
        ## NOTE: create the snapshot
        if not __opts__["test"]:
            mod_res = __salt__["zfs.snapshot"](
                name, **{"recursive": recursive, "properties": properties}
            )
        else:
            mod_res = OrderedDict([("snapshotted", True)])

        ret["result"] = mod_res["snapshotted"]
        if ret["result"]:
            ret["changes"][name] = "snapshotted"
            if properties:
                ret["changes"][name] = properties
            ret["comment"] = "snapshot {} was created".format(name)
        else:
            ret["comment"] = "failed to create snapshot {}".format(name)
            if "error" in mod_res:
                ret["comment"] = mod_res["error"]
    else:
        ## NOTE: snapshot already exists
        ret["comment"] = "snapshot is present"

    return ret


def promoted(name):
    """
    ensure a dataset is not a clone

    name : string
        name of fileset or volume

    .. warning::

        only one dataset can be the origin,
        if you promote a clone the original will now point to the promoted dataset

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## check we if we have a valid dataset name
    if not __utils__["zfs.is_dataset"](name):
        ret["result"] = False
        ret["comment"] = "invalid dataset name: {}".format(name)
        return ret

    ## ensure dataset is the primary instance
    if not __salt__["zfs.exists"](name, **{"type": "filesystem,volume"}):
        ## NOTE: we don't have a dataset
        ret["result"] = False
        ret["comment"] = "dataset {} does not exist".format(name)
    else:
        ## NOTE: check if we have a blank origin (-)
        if (
            __salt__["zfs.get"](
                name, **{"properties": "origin", "fields": "value", "parsable": True}
            )[name]["origin"]["value"]
            == "-"
        ):
            ## NOTE: we're already promoted
            ret["comment"] = "{} already promoted".format(name)
        else:
            ## NOTE: promote dataset
            if not __opts__["test"]:
                mod_res = __salt__["zfs.promote"](name)
            else:
                mod_res = OrderedDict([("promoted", True)])

            ret["result"] = mod_res["promoted"]
            if ret["result"]:
                ret["changes"][name] = "promoted"
                ret["comment"] = "{} promoted".format(name)
            else:
                ret["comment"] = "failed to promote {}".format(name)
                if "error" in mod_res:
                    ret["comment"] = mod_res["error"]

    return ret


def _schedule_snapshot_retrieve(dataset, prefix, snapshots):
    """
    Update snapshots dict with current snapshots

    dataset: string
        name of filesystem or volume
    prefix : string
        prefix for the snapshots
        e.g. 'test' will result in snapshots being named 'test-yyyymmdd_hhmm'
    snapshots : OrderedDict
        preseeded OrderedDict with configuration

    """
    ## NOTE: retrieve all snapshots for the dataset
    for snap in sorted(
        __salt__["zfs.list"](
            dataset, **{"recursive": True, "depth": 1, "type": "snapshot"}
        ).keys()
    ):
        ## NOTE: we only want the actualy name
        ##       myzpool/data@zbck-20171201_000248 -> zbck-20171201_000248
        snap_name = snap[snap.index("@") + 1 :]

        ## NOTE: we only want snapshots matching our prefix
        if not snap_name.startswith("{}-".format(prefix)):
            continue

        ## NOTE: retrieve the holds for this snapshot
        snap_holds = __salt__["zfs.holds"](snap)

        ## NOTE: this snapshot has no holds, eligable for pruning
        if not snap_holds:
            snapshots["_prunable"].append(snap)

        ## NOTE: update snapshots based on holds (if any)
        ##       we are only interested in the ones from our schedule
        ##       if we find any others we skip them
        for hold in snap_holds:
            if hold in snapshots["_schedule"].keys():
                snapshots[hold].append(snap)

    return snapshots


def _schedule_snapshot_prepare(dataset, prefix, snapshots):
    """
    Update snapshots dict with info for a new snapshot

    dataset: string
        name of filesystem or volume
    prefix : string
        prefix for the snapshots
        e.g. 'test' will result in snapshots being named 'test-yyyymmdd_hhmm'
    snapshots : OrderedDict
        preseeded OrderedDict with configuration

    """
    ## NOTE: generate new snapshot name
    snapshot_create_name = "{dataset}@{prefix}-{timestamp}".format(
        dataset=dataset,
        prefix=prefix,
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )

    ## NOTE: figure out if we need to create the snapshot
    timestamp_now = datetime.now().replace(second=0, microsecond=0)
    snapshots["_create"][snapshot_create_name] = []
    for hold, hold_count in snapshots["_schedule"].items():
        ## NOTE: skip hold if we don't keep snapshots for it
        if hold_count == 0:
            continue

        ## NOTE: figure out if we need the current hold on the new snapshot
        if snapshots[hold]:
            ## NOTE: extract datetime from snapshot name
            timestamp = datetime.strptime(
                snapshots[hold][-1],
                "{}@{}-%Y%m%d_%H%M%S".format(dataset, prefix),
            ).replace(second=0, microsecond=0)

            ## NOTE: compare current timestamp to timestamp from snapshot
            if hold == "minute" and timestamp_now <= timestamp:
                continue
            elif hold == "hour" and timestamp_now.replace(
                **comp_hour
            ) <= timestamp.replace(**comp_hour):
                continue
            elif hold == "day" and timestamp_now.replace(
                **comp_day
            ) <= timestamp.replace(**comp_day):
                continue
            elif hold == "month" and timestamp_now.replace(
                **comp_month
            ) <= timestamp.replace(**comp_month):
                continue
            elif hold == "year" and timestamp_now.replace(
                **comp_year
            ) <= timestamp.replace(**comp_year):
                continue

        ## NOTE: add hold entry for snapshot
        snapshots["_create"][snapshot_create_name].append(hold)

    return snapshots


def scheduled_snapshot(name, prefix, recursive=True, schedule=None):
    """
    maintain a set of snapshots based on a schedule

    name : string
        name of filesystem or volume
    prefix : string
        prefix for the snapshots
        e.g. 'test' will result in snapshots being named 'test-yyyymmdd_hhmm'
    recursive : boolean
        create snapshots for all children also
    schedule : dict
        dict holding the schedule, the following keys are available (minute, hour,
        day, month, and year) by default all are set to 0 the value indicated the
        number of snapshots of that type to keep around.

    .. warning::

        snapshots will only be created and pruned every time the state runs.
        a schedule must be setup to automatically run the state. this means that if
        you run the state daily the hourly snapshot will only be made once per day!

    .. versionchanged:: 2018.3.0

        switched to localtime from gmtime so times now take into account timezones.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ## initialize defaults
    schedule_holds = ["minute", "hour", "day", "month", "year"]
    snapshots = OrderedDict(
        [("_create", OrderedDict()), ("_prunable", []), ("_schedule", OrderedDict())]
    )

    ## strict configuration validation
    ## NOTE: we need a valid dataset
    if not __utils__["zfs.is_dataset"](name):
        ret["result"] = False
        ret["comment"] = "invalid dataset name: {}".format(name)

    if not __salt__["zfs.exists"](name, **{"type": "filesystem,volume"}):
        ret["comment"] = "dataset {} does not exist".format(name)
        ret["result"] = False

    ## NOTE: prefix must be 4 or longer
    if not prefix or len(prefix) < 4:
        ret["comment"] = "prefix ({}) must be at least 4 long".format(prefix)
        ret["result"] = False

    ## NOTE: validate schedule
    total_count = 0
    for hold in schedule_holds:
        snapshots[hold] = []
        if hold not in schedule:
            snapshots["_schedule"][hold] = 0
        elif isinstance(schedule[hold], int):
            snapshots["_schedule"][hold] = schedule[hold]
        else:
            ret["result"] = False
            ret["comment"] = "schedule value for {} is not an integer".format(
                hold,
            )
            break
        total_count += snapshots["_schedule"][hold]
    if ret["result"] and total_count == 0:
        ret["result"] = False
        ret["comment"] = "schedule is not valid, you need to keep atleast 1 snapshot"

    ## NOTE: return if configuration is not valid
    if not ret["result"]:
        return ret

    ## retrieve existing snapshots
    snapshots = _schedule_snapshot_retrieve(name, prefix, snapshots)

    ## prepare snapshot
    snapshots = _schedule_snapshot_prepare(name, prefix, snapshots)

    ## log configuration
    log.debug("zfs.scheduled_snapshot::%s::config::recursive = %s", name, recursive)
    log.debug("zfs.scheduled_snapshot::%s::config::prefix = %s", name, prefix)
    log.debug("zfs.scheduled_snapshot::%s::snapshots = %s", name, snapshots)

    ## create snapshot(s)
    for snapshot_name, snapshot_holds in snapshots["_create"].items():
        ## NOTE: skip if new snapshot has no holds
        if not snapshot_holds:
            continue

        ## NOTE: create snapshot
        if not __opts__["test"]:
            mod_res = __salt__["zfs.snapshot"](
                snapshot_name, **{"recursive": recursive}
            )
        else:
            mod_res = OrderedDict([("snapshotted", True)])

        if not mod_res["snapshotted"]:
            ret["result"] = False
            ret["comment"] = "error creating snapshot ({})".format(snapshot_name)
        else:
            ## NOTE: create holds (if we have a snapshot)
            for hold in snapshot_holds:
                if not __opts__["test"]:
                    mod_res = __salt__["zfs.hold"](
                        hold, snapshot_name, **{"recursive": recursive}
                    )
                else:
                    mod_res = OrderedDict([("held", True)])

                if not mod_res["held"]:
                    ret["result"] = False
                    ret["comment"] = "error adding hold ({}) to snapshot ({})".format(
                        hold,
                        snapshot_name,
                    )
                    break

                snapshots[hold].append(snapshot_name)

        if ret["result"]:
            ret["comment"] = "scheduled snapshots updated"
            if "created" not in ret["changes"]:
                ret["changes"]["created"] = []
            ret["changes"]["created"].append(snapshot_name)

    ## prune hold(s)
    for hold, hold_count in snapshots["_schedule"].items():
        while ret["result"] and len(snapshots[hold]) > hold_count:
            ## NOTE: pop oldest snapshot
            snapshot_name = snapshots[hold].pop(0)

            ## NOTE: release hold for snapshot
            if not __opts__["test"]:
                mod_res = __salt__["zfs.release"](
                    hold, snapshot_name, **{"recursive": recursive}
                )
            else:
                mod_res = OrderedDict([("released", True)])

            if not mod_res["released"]:
                ret["result"] = False
                ret["comment"] = "error adding hold ({}) to snapshot ({})".format(
                    hold,
                    snapshot_name,
                )

            ## NOTE: mark as prunable
            if not __salt__["zfs.holds"](snapshot_name):
                snapshots["_prunable"].append(snapshot_name)

    ## prune snapshot(s)
    for snapshot_name in snapshots["_prunable"]:
        ## NOTE: destroy snapshot
        if not __opts__["test"]:
            mod_res = __salt__["zfs.destroy"](snapshot_name, **{"recursive": recursive})
        else:
            mod_res = OrderedDict([("destroyed", True)])

        if not mod_res["destroyed"]:
            ret["result"] = False
            ret["comment"] = "error prunding snapshot ({1})".format(
                snapshot_name,
            )
            break

    if ret["result"] and snapshots["_prunable"]:
        ret["comment"] = "scheduled snapshots updated"
        ret["changes"]["pruned"] = snapshots["_prunable"]

    if ret["result"] and not ret["changes"]:
        ret["comment"] = "scheduled snapshots are up to date"

    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
