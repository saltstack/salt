"""
Module for managing BCache sets

BCache is a block-level caching mechanism similar to ZFS L2ARC/ZIL, dm-cache and fscache.
It works by formatting one block device as a cache set, then adding backend devices
(which need to be formatted as such) to the set and activating them.

It's available in Linux mainline kernel since 3.10

https://www.kernel.org/doc/Documentation/bcache.txt

This module needs the bcache userspace tools to function.

.. versionadded:: 2016.3.0

"""

import logging
import os
import re
import time

import salt.utils.path

log = logging.getLogger(__name__)

LOG = {
    "trace": logging.TRACE,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "crit": logging.CRITICAL,
}

__func_alias__ = {
    "attach_": "attach",
    "config_": "config",
    "super_": "super",
}

HAS_BLKDISCARD = salt.utils.path.which("blkdiscard") is not None


def __virtual__():
    """
    Only work when make-bcache is installed
    """
    return salt.utils.path.which("make-bcache") is not None


def uuid(dev=None):
    """
    Return the bcache UUID of a block device.
    If no device is given, the Cache UUID is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.uuid
        salt '*' bcache.uuid /dev/sda
        salt '*' bcache.uuid bcache0

    """
    try:
        if dev is None:
            # take the only directory in /sys/fs/bcache and return its basename
            return list(salt.utils.path.os_walk("/sys/fs/bcache/"))[0][1][0]
        else:
            # basename of the /sys/block/{dev}/bcache/cache symlink target
            return os.path.basename(_bcsys(dev, "cache"))
    except Exception:  # pylint: disable=broad-except
        return False


def attach_(dev=None):
    """
    Attach a backing devices to a cache set
    If no dev is given, all backing devices will be attached.

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.attach sdc
        salt '*' bcache.attach /dev/bcache1


    :return: bool or None if nuttin' happened
    """
    cache = uuid()
    if not cache:
        log.error("No cache to attach %s to", dev)
        return False

    if dev is None:
        res = {}
        for dev, data in status(alldevs=True).items():
            if "cache" in data:
                res[dev] = attach_(dev)

        return res if res else None

    bcache = uuid(dev)
    if bcache:
        if bcache == cache:
            log.info("%s is already attached to bcache %s, doing nothing", dev, cache)
            return None
        elif not detach(dev):
            return False

    log.debug("Attaching %s to bcache %s", dev, cache)

    if not _bcsys(
        dev,
        "attach",
        cache,
        "error",
        "Error attaching {} to bcache {}".format(dev, cache),
    ):
        return False

    return _wait(
        lambda: uuid(dev) == cache,
        "error",
        "{} received attach to bcache {}, but did not comply".format(dev, cache),
    )


def detach(dev=None):
    """
    Detach a backing device(s) from a cache set
    If no dev is given, all backing devices will be attached.

    Detaching a backing device will flush its write cache.
    This should leave the underlying device in a consistent state, but might take a while.

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.detach sdc
        salt '*' bcache.detach bcache1

    """
    if dev is None:
        res = {}
        for dev, data in status(alldevs=True).items():
            if "cache" in data:
                res[dev] = detach(dev)

        return res if res else None

    log.debug("Detaching %s", dev)
    if not _bcsys(dev, "detach", "goaway", "error", "Error detaching {}".format(dev)):
        return False
    return _wait(
        lambda: uuid(dev) is False,
        "error",
        "{} received detach, but did not comply".format(dev),
        300,
    )


def start():
    """
    Trigger a start of the full bcache system through udev.

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.start

    """
    if not _run_all("udevadm trigger", "error", "Error starting bcache: %s"):
        return False
    elif not _wait(
        lambda: uuid() is not False,
        "warn",
        "Bcache system started, but no active cache set found.",
    ):
        return False
    return True


def stop(dev=None):
    """
    Stop a bcache device
    If no device is given, all backing devices will be detached from the cache, which will subsequently be stopped.

    .. warning::
        'Stop' on an individual backing device means hard-stop;
        no attempt at flushing will be done and the bcache device will seemingly 'disappear' from the device lists

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.stop

    """
    if dev is not None:
        log.warning("Stopping %s, device will only reappear after reregistering!", dev)
        if not _bcsys(dev, "stop", "goaway", "error", "Error stopping {}".format(dev)):
            return False
        return _wait(
            lambda: _sysfs_attr(_bcpath(dev)) is False,
            "error",
            "Device {} did not stop".format(dev),
            300,
        )
    else:
        cache = uuid()
        if not cache:
            log.warning("bcache already stopped?")
            return None

        if not _alltrue(detach()):
            return False
        elif not _fssys("stop", "goaway", "error", "Error stopping cache"):
            return False

        return _wait(lambda: uuid() is False, "error", "Cache did not stop", 300)


def back_make(dev, cache_mode="writeback", force=False, attach=True, bucket_size=None):
    """
    Create a backing device for attachment to a set.
    Because the block size must be the same, a cache set already needs to exist.

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.back_make sdc cache_mode=writeback attach=True


    :param cache_mode: writethrough, writeback, writearound or none.
    :param force: Overwrite existing bcaches
    :param attach: Immediately attach the backing device to the set
    :param bucket_size: Size of a bucket (see kernel doc)
    """
    # pylint: disable=too-many-return-statements
    cache = uuid()

    if not cache:
        log.error("No bcache set found")
        return False
    elif _sysfs_attr(_bcpath(dev)):
        if not force:
            log.error(
                "%s already contains a bcache. Wipe it manually or use force", dev
            )
            return False
        elif uuid(dev) and not detach(dev):
            return False
        elif not stop(dev):
            return False

    dev = _devpath(dev)
    block_size = _size_map(_fssys("block_size"))
    # You might want to override, we pick the cache set's as sane default
    if bucket_size is None:
        bucket_size = _size_map(_fssys("bucket_size"))

    cmd = "make-bcache --block {} --bucket {} --{} --bdev {}".format(
        block_size, bucket_size, cache_mode, dev
    )
    if force:
        cmd += " --wipe-bcache"

    if not _run_all(cmd, "error", "Error creating backing device {}: %s".format(dev)):
        return False
    elif not _sysfs_attr(
        "fs/bcache/register",
        _devpath(dev),
        "error",
        "Error registering backing device {}".format(dev),
    ):
        return False
    elif not _wait(
        lambda: _sysfs_attr(_bcpath(dev)) is not False,
        "error",
        "Backing device {} did not register".format(dev),
    ):
        return False
    elif attach:
        return attach_(dev)

    return True


def cache_make(
    dev, reserved=None, force=False, block_size=None, bucket_size=None, attach=True
):
    """
    Create BCache cache on a block device.
    If blkdiscard is available the entire device will be properly cleared in advance.

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.cache_make sdb reserved=10% block_size=4096


    :param reserved: if dev is a full device, create a partition table with this size empty.

        .. note::
              this increases the amount of reserved space available to SSD garbage collectors,
              potentially (vastly) increasing performance
    :param block_size: Block size of the cache; defaults to devices' logical block size
    :param force: Overwrite existing BCache sets
    :param attach: Attach all existing backend devices immediately
    """
    # TODO: multiple devs == md jbod

    # pylint: disable=too-many-return-statements
    # ---------------- Preflight checks ----------------
    cache = uuid()
    if cache:
        if not force:
            log.error("BCache cache %s is already on the system", cache)
            return False
        cache = _bdev()

    dev = _devbase(dev)
    udev = __salt__["udev.env"](dev)

    if (
        "ID_FS_TYPE" in udev
        or (udev.get("DEVTYPE", None) != "partition" and "ID_PART_TABLE_TYPE" in udev)
    ) and not force:
        log.error("%s already contains data, wipe first or force", dev)
        return False
    elif reserved is not None and udev.get("DEVTYPE", None) != "disk":
        log.error("Need a partitionable blockdev for reserved to work")
        return False

    _, block, bucket = _sizes(dev)

    if bucket_size is None:
        bucket_size = bucket
        # TODO: bucket from _sizes() makes no sense
        bucket_size = False
    if block_size is None:
        block_size = block

    # ---------------- Still here, start doing destructive stuff ----------------
    if cache:
        if not stop():
            return False
        # Wipe the current cache device as well,
        # forever ruining any chance of it accidentally popping up again
        elif not _wipe(cache):
            return False

    # Can't do enough wiping
    if not _wipe(dev):
        return False

    if reserved:
        cmd = (
            "parted -m -s -a optimal -- "
            "/dev/{0} mklabel gpt mkpart bcache-reserved 1M {1} mkpart bcache {1} 100%".format(
                dev, reserved
            )
        )
        # if wipe was incomplete & part layout remains the same,
        # this is one condition set where udev would make it accidentally popup again
        if not _run_all(
            cmd, "error", "Error creating bcache partitions on {}: %s".format(dev)
        ):
            return False
        dev = "{}2".format(dev)

    # ---------------- Finally, create a cache ----------------
    cmd = "make-bcache --cache /dev/{} --block {} --wipe-bcache".format(dev, block_size)

    # Actually bucket_size should always have a value, but for testing 0 is possible as well
    if bucket_size:
        cmd += " --bucket {}".format(bucket_size)

    if not _run_all(cmd, "error", "Error creating cache {}: %s".format(dev)):
        return False
    elif not _wait(
        lambda: uuid() is not False,
        "error",
        "Cache {} seemingly created OK, but FS did not activate".format(dev),
    ):
        return False

    if attach:
        return _alltrue(attach_())
    else:
        return True


def config_(dev=None, **kwargs):
    """
    Show or update config of a bcache device.

    If no device is given, operate on the cache set itself.

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.config
        salt '*' bcache.config bcache1
        salt '*' bcache.config errors=panic journal_delay_ms=150
        salt '*' bcache.config bcache1 cache_mode=writeback writeback_percent=15

    :return: config or True/False
    """
    if dev is None:
        spath = _fspath()
    else:
        spath = _bcpath(dev)

    # filter out 'hidden' kwargs added by our favourite orchestration system
    updates = {key: val for key, val in kwargs.items() if not key.startswith("__")}

    if updates:
        endres = 0
        for key, val in updates.items():
            endres += _sysfs_attr(
                [spath, key],
                val,
                "warn",
                "Failed to update {} with {}".format(os.path.join(spath, key), val),
            )
        return endres > 0
    else:
        result = {}
        data = _sysfs_parse(spath, config=True, internals=True, options=True)
        for key in ("other_ro", "inter_ro"):
            if key in data:
                del data[key]

        for key in data:
            result.update(data[key])

        return result


def status(stats=False, config=False, internals=False, superblock=False, alldevs=False):
    """
    Show the full status of the BCache system and optionally all its involved devices

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.status
        salt '*' bcache.status stats=True
        salt '*' bcache.status internals=True alldevs=True

    :param stats: include statistics
    :param config: include settings
    :param internals: include internals
    :param superblock: include superblock
    """
    bdevs = []
    for _, links, _ in salt.utils.path.os_walk("/sys/block/"):
        for block in links:
            if "bcache" in block:
                continue

            for spath, sdirs, _ in salt.utils.path.os_walk(
                "/sys/block/{}".format(block), followlinks=False
            ):
                if "bcache" in sdirs:
                    bdevs.append(os.path.basename(spath))
    statii = {}
    for bcache in bdevs:
        statii[bcache] = device(bcache, stats, config, internals, superblock)

    cuuid = uuid()
    cdev = _bdev()
    if cdev:
        count = 0
        for dev in statii:
            if dev != cdev:
                # it's a backing dev
                if statii[dev]["cache"] == cuuid:
                    count += 1
        statii[cdev]["attached_backing_devices"] = count

        if not alldevs:
            statii = statii[cdev]

    return statii


def device(dev, stats=False, config=False, internals=False, superblock=False):
    """
    Check the state of a single bcache device

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.device bcache0
        salt '*' bcache.device /dev/sdc stats=True

    :param stats: include statistics
    :param settings: include all settings
    :param internals: include all internals
    :param superblock: include superblock info
    """
    result = {}

    if not _sysfs_attr(
        _bcpath(dev), None, "error", "{} is not a bcache fo any kind".format(dev)
    ):
        return False
    elif _bcsys(dev, "set"):
        # ---------------- It's the cache itself ----------------
        result["uuid"] = uuid()
        base_attr = [
            "block_size",
            "bucket_size",
            "cache_available_percent",
            "cache_replacement_policy",
            "congested",
        ]

        # ---------------- Parse through both the blockdev & the FS ----------------
        result.update(_sysfs_parse(_bcpath(dev), base_attr, stats, config, internals))
        result.update(_sysfs_parse(_fspath(), base_attr, stats, config, internals))

        result.update(result.pop("base"))
    else:
        # ---------------- It's a backing device ----------------
        back_uuid = uuid(dev)
        if back_uuid is not None:
            result["cache"] = back_uuid

        try:
            result["dev"] = os.path.basename(_bcsys(dev, "dev"))
        except Exception:  # pylint: disable=broad-except
            pass
        result["bdev"] = _bdev(dev)

        base_attr = ["cache_mode", "running", "state", "writeback_running"]
        base_path = _bcpath(dev)

        result.update(_sysfs_parse(base_path, base_attr, stats, config, internals))
        result.update(result.pop("base"))

        # ---------------- Modifications ----------------
        state = [result["state"]]
        if result.pop("running"):
            state.append("running")
        else:
            state.append("stopped")
        if "writeback_running" in result:
            if result.pop("writeback_running"):
                state.append("writeback_running")
            else:
                state.append("writeback_stopped")
        result["state"] = state

    # ---------------- Statistics ----------------
    if "stats" in result:
        replre = r"(stats|cache)_"
        statres = result["stats"]
        for attr in result["stats"]:
            if "/" not in attr:
                key = re.sub(replre, "", attr)
                statres[key] = statres.pop(attr)
            else:
                stat, key = attr.split("/", 1)
                stat = re.sub(replre, "", stat)
                key = re.sub(replre, "", key)
                if stat not in statres:
                    statres[stat] = {}
                statres[stat][key] = statres.pop(attr)
        result["stats"] = statres

    # ---------------- Internals ----------------
    if internals:
        interres = result.pop("inter_ro", {})
        interres.update(result.pop("inter_rw", {}))
        if interres:
            for key in interres:
                if key.startswith("internal"):
                    nkey = re.sub(r"internal[s/]*", "", key)
                    interres[nkey] = interres.pop(key)
                    key = nkey
                if key.startswith(("btree", "writeback")):
                    mkey, skey = re.split(r"_", key, maxsplit=1)
                    if mkey not in interres:
                        interres[mkey] = {}
                    interres[mkey][skey] = interres.pop(key)
            result["internals"] = interres

    # ---------------- Config ----------------
    if config:
        configres = result["config"]
        for key in configres:
            if key.startswith("writeback"):
                mkey, skey = re.split(r"_", key, maxsplit=1)
                if mkey not in configres:
                    configres[mkey] = {}
                configres[mkey][skey] = configres.pop(key)
        result["config"] = configres

    # ---------------- Superblock ----------------
    if superblock:
        result["superblock"] = super_(dev)

    return result


def super_(dev):
    """
    Read out BCache SuperBlock

    CLI Example:

    .. code-block:: bash

        salt '*' bcache.device bcache0
        salt '*' bcache.device /dev/sdc

    """
    dev = _devpath(dev)
    ret = {}

    res = _run_all(
        "bcache-super-show {}".format(dev),
        "error",
        "Error reading superblock on {}: %s".format(dev),
    )
    if not res:
        return False

    for line in res.splitlines():  # pylint: disable=no-member
        line = line.strip()
        if not line:
            continue

        key, val = (val.strip() for val in re.split(r"[\s]+", line, maxsplit=1))
        if not (key and val):
            continue

        mval = None
        if " " in val:
            rval, mval = (val.strip() for val in re.split(r"[\s]+", val, maxsplit=1))
            mval = mval[1:-1]
        else:
            rval = val

        try:
            rval = int(rval)
        except Exception:  # pylint: disable=broad-except
            try:
                rval = float(rval)
            except Exception:  # pylint: disable=broad-except
                if rval == "yes":
                    rval = True
                elif rval == "no":
                    rval = False

        pkey, key = re.split(r"\.", key, maxsplit=1)
        if pkey not in ret:
            ret[pkey] = {}

        if mval is not None:
            ret[pkey][key] = (rval, mval)
        else:
            ret[pkey][key] = rval

    return ret


# -------------------------------- HELPER FUNCTIONS --------------------------------


def _devbase(dev):
    """
    Basename of just about any dev
    """
    dev = os.path.realpath(os.path.expandvars(dev))
    dev = os.path.basename(dev)
    return dev


def _devpath(dev):
    """
    Return /dev name of just about any dev
    :return: /dev/devicename
    """
    return os.path.join("/dev", _devbase(dev))


def _syspath(dev):
    """
    Full SysFS path of a device
    """
    dev = _devbase(dev)
    dev = re.sub(r"^([vhs][a-z]+)([0-9]+)", r"\1/\1\2", dev)

    # name = re.sub(r'^([a-z]+)(?<!(bcache|md|dm))([0-9]+)', r'\1/\1\2', name)
    return os.path.join("/sys/block/", dev)


def _bdev(dev=None):
    """
    Resolve a bcacheX or cache to a real dev
    :return: basename of bcache dev
    """
    if dev is None:
        dev = _fssys("cache0")
    else:
        dev = _bcpath(dev)

    if not dev:
        return False
    else:
        return _devbase(os.path.dirname(dev))


def _bcpath(dev):
    """
    Full SysFS path of a bcache device
    """
    return os.path.join(_syspath(dev), "bcache")


def _fspath():
    """
    :return: path of active bcache
    """
    cuuid = uuid()
    if not cuuid:
        return False
    else:
        return os.path.join("/sys/fs/bcache/", cuuid)


def _fssys(name, value=None, log_lvl=None, log_msg=None):
    """
    Simple wrapper to interface with bcache SysFS
    """
    fspath = _fspath()
    if not fspath:
        return False
    else:
        return _sysfs_attr([fspath, name], value, log_lvl, log_msg)


def _bcsys(dev, name, value=None, log_lvl=None, log_msg=None):
    """
    Simple wrapper to interface with backing devs SysFS
    """
    return _sysfs_attr([_bcpath(dev), name], value, log_lvl, log_msg)


def _sysfs_attr(name, value=None, log_lvl=None, log_msg=None):
    """
    Simple wrapper with logging around sysfs.attr
    """
    if isinstance(name, str):
        name = [name]
    res = __salt__["sysfs.attr"](os.path.join(*name), value)
    if not res and log_lvl is not None and log_msg is not None:
        log.log(LOG[log_lvl], log_msg)
    return res


def _sysfs_parse(
    path, base_attr=None, stats=False, config=False, internals=False, options=False
):
    """
    Helper function for parsing BCache's SysFS interface
    """
    result = {}

    # ---------------- Parse through the interfaces list ----------------
    intfs = __salt__["sysfs.interfaces"](path)

    # Actions, we ignore
    del intfs["w"]

    # -------- Sorting hat --------
    binkeys = []
    if internals:
        binkeys.extend(["inter_ro", "inter_rw"])
    if config:
        binkeys.append("config")
    if stats:
        binkeys.append("stats")

    bintf = {}
    for key in binkeys:
        bintf[key] = []

    for intf in intfs["r"]:
        if intf.startswith("internal"):
            key = "inter_ro"
        elif "stats" in intf:
            key = "stats"
        else:
            # What to do with these???
            # I'll utilize 'inter_ro' as 'misc' as well
            key = "inter_ro"

        if key in bintf:
            bintf[key].append(intf)

    for intf in intfs["rw"]:
        if intf.startswith("internal"):
            key = "inter_rw"
        else:
            key = "config"

        if key in bintf:
            bintf[key].append(intf)

    if base_attr is not None:
        for intf in bintf:
            bintf[intf] = [sintf for sintf in bintf[intf] if sintf not in base_attr]
        bintf["base"] = base_attr

    mods = {
        "stats": [
            "internal/bset_tree_stats",
            "writeback_rate_debug",
            "metadata_written",
            "nbuckets",
            "written",
            "average_key_size",
            "btree_cache_size",
        ],
    }

    for modt, modlist in mods.items():
        found = []
        if modt not in bintf:
            continue
        for mod in modlist:
            for intflist in bintf.values():
                if mod in intflist:
                    found.append(mod)
                    intflist.remove(mod)
        bintf[modt] += found

    # -------- Fetch SysFS vals --------
    bintflist = [intf for iflist in bintf.values() for intf in iflist]
    result.update(__salt__["sysfs.read"](bintflist, path))

    # -------- Parse through well known string lists --------
    for strlist in (
        "writeback_rate_debug",
        "internal/bset_tree_stats",
        "priority_stats",
    ):
        if strlist in result:
            listres = {}
            for line in result[strlist].split("\n"):
                key, val = line.split(":", 1)
                val = val.strip()
                try:
                    val = int(val)
                except Exception:  # pylint: disable=broad-except
                    try:
                        val = float(val)
                    except Exception:  # pylint: disable=broad-except
                        pass
                listres[key.strip()] = val
            result[strlist] = listres

    # -------- Parse through selection lists --------
    if not options:
        for sellist in ("cache_mode", "cache_replacement_policy", "errors"):
            if sellist in result:
                result[sellist] = re.search(r"\[(.+)\]", result[sellist]).groups()[0]

    # -------- Parse through well known bools --------
    for boolkey in ("running", "writeback_running", "congested"):
        if boolkey in result:
            result[boolkey] = bool(result[boolkey])

    # -------- Recategorize results --------
    bresult = {}
    for iftype, intflist in bintf.items():
        ifres = {}
        for intf in intflist:
            if intf in result:
                ifres[intf] = result.pop(intf)
        if ifres:
            bresult[iftype] = ifres

    return bresult


def _size_map(size):
    """
    Map Bcache's size strings to real bytes
    """
    try:
        # I know, I know, EAFP.
        # But everything else is reason for None
        if not isinstance(size, int):
            if re.search(r"[Kk]", size):
                size = 1024 * float(re.sub(r"[Kk]", "", size))
            elif re.search(r"[Mm]", size):
                size = 1024**2 * float(re.sub(r"[Mm]", "", size))
            size = int(size)
        return size
    except Exception:  # pylint: disable=broad-except
        return None


def _sizes(dev):
    """
    Return neigh useless sizing info about a blockdev
    :return: (total size in blocks, blocksize, maximum discard size in bytes)
    """
    dev = _devbase(dev)

    # standarization yay
    block_sizes = (
        "hw_sector_size",
        "minimum_io_size",
        "physical_block_size",
        "logical_block_size",
    )
    discard_sizes = (
        "discard_max_bytes",
        "discard_max_hw_bytes",
    )

    sysfs = __salt__["sysfs.read"](
        (
            "size",
            "queue/hw_sector_size",
            "../queue/hw_sector_size",
            "queue/discard_max_bytes",
            "../queue/discard_max_bytes",
        ),
        root=_syspath(dev),
    )

    # TODO: makes no sense
    # First of all, it has to be a power of 2
    # Secondly, this returns 4GiB - 512b on Intel 3500's for some weird reason
    # discard_granularity seems in bytes, resolves to 512b ???
    # max_hw_sectors_kb???
    # There's also discard_max_hw_bytes more recently
    # See: https://www.kernel.org/doc/Documentation/block/queue-sysfs.txt
    # Also, I cant find any docs yet regarding bucket sizes;
    # it's supposed to be discard_max_hw_bytes,
    # but no way to figure that one reliably out apparently

    discard = sysfs.get(
        "queue/discard_max_bytes", sysfs.get("../queue/discard_max_bytes", None)
    )
    block = sysfs.get(
        "queue/hw_sector_size", sysfs.get("../queue/hw_sector_size", None)
    )

    return 512 * sysfs["size"], block, discard


def _wipe(dev):
    """
    REALLY DESTRUCTIVE STUFF RIGHT AHEAD
    """
    endres = 0
    dev = _devbase(dev)

    size, block, discard = _sizes(dev)

    if discard is None:
        log.error("Unable to read SysFS props for %s", dev)
        return None
    elif not discard:
        log.warning("%s seems unable to discard", dev)
        wiper = "dd"
    elif not HAS_BLKDISCARD:
        log.warning(
            "blkdiscard binary not available, properly wipe the dev manually for"
            " optimal results"
        )
        wiper = "dd"
    else:
        wiper = "blkdiscard"

    wipe_failmsg = "Error wiping {}: %s".format(dev)
    if wiper == "dd":
        blocks = 4
        cmd = "dd if=/dev/zero of=/dev/{} bs=1M count={}".format(dev, blocks)
        endres += _run_all(cmd, "warn", wipe_failmsg)

        # Some stuff (<cough>GPT</cough>) writes stuff at the end of a dev as well
        cmd += " seek={}".format((size / 1024**2) - blocks)
        endres += _run_all(cmd, "warn", wipe_failmsg)

    elif wiper == "blkdiscard":
        cmd = "blkdiscard /dev/{}".format(dev)
        endres += _run_all(cmd, "warn", wipe_failmsg)
        # TODO: fix annoying bug failing blkdiscard by trying to discard 1 sector past blkdev
        endres = 1

    return endres > 0


def _wait(lfunc, log_lvl=None, log_msg=None, tries=10):
    """
    Wait for lfunc to be True
    :return: True if lfunc succeeded within tries, False if it didn't
    """
    i = 0
    while i < tries:
        time.sleep(1)

        if lfunc():
            return True
        else:
            i += 1
    if log_lvl is not None:
        log.log(LOG[log_lvl], log_msg)
    return False


def _run_all(cmd, log_lvl=None, log_msg=None, exitcode=0):
    """
    Simple wrapper around cmd.run_all
    log_msg can contain {0} for stderr
    :return: True or stdout, False if retcode wasn't exitcode
    """
    res = __salt__["cmd.run_all"](cmd)
    if res["retcode"] == exitcode:
        if res["stdout"]:
            return res["stdout"]
        else:
            return True

    if log_lvl is not None:
        log.log(LOG[log_lvl], log_msg, res["stderr"])
    return False


def _alltrue(resdict):
    if resdict is None:
        return True
    return len([val for val in resdict.values() if val]) > 0
