# -*- coding: utf-8 -*-
"""
Management of Block Devices

A state module to manage blockdevices

.. code-block:: yaml


    /dev/sda:
      blockdev.tuned:
        - read-only: True

    master-data:
      blockdev.tuned:
        - name: /dev/vg/master-data
        - read-only: True
        - read-ahead: 1024


.. versionadded:: 2014.7.0
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import python libs
import os
import os.path
import time

# Import salt libs
import salt.utils.path
from salt.ext.six.moves import range

__virtualname__ = "blockdev"

# Init logger
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load this module if the disk execution module is available
    """
    if "disk.tune" in __salt__:
        return __virtualname__
    return (
        False,
        (
            "Cannot load the {0} state module: "
            "disk execution module not found".format(__virtualname__)
        ),
    )


def tuned(name, **kwargs):
    """
    Manage options of block device

    name
        The name of the block device

    opts:
      - read-ahead
          Read-ahead buffer size

      - filesystem-read-ahead
          Filesystem Read-ahead buffer size

      - read-only
          Set Read-Only

      - read-write
          Set Read-Write
    """

    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    kwarg_map = {
        "read-ahead": "getra",
        "filesystem-read-ahead": "getfra",
        "read-only": "getro",
        "read-write": "getro",
    }

    if not __salt__["file.is_blkdev"]:
        ret["comment"] = (
            "Changes to {0} cannot be applied. " "Not a block device. "
        ).format(name)
    elif __opts__["test"]:
        ret["comment"] = "Changes to {0} will be applied ".format(name)
        ret["result"] = None
        return ret
    else:
        current = __salt__["disk.dump"](name)
        changes = __salt__["disk.tune"](name, **kwargs)
        changeset = {}
        for key in kwargs:
            if key in kwarg_map:
                switch = kwarg_map[key]
                if current[switch] != changes[switch]:
                    if isinstance(kwargs[key], bool):
                        old = current[switch] == "1"
                        new = changes[switch] == "1"
                    else:
                        old = current[switch]
                        new = changes[switch]
                    if key == "read-write":
                        old = not old
                        new = not new
                    changeset[key] = "Changed from {0} to {1}".format(old, new)
        if changes:
            if changeset:
                ret["comment"] = ("Block device {0} " "successfully modified ").format(
                    name
                )
                ret["changes"] = changeset
            else:
                ret["comment"] = "Block device {0} already in correct state".format(
                    name
                )
        else:
            ret["comment"] = "Failed to modify block device {0}".format(name)
            ret["result"] = False
    return ret


def formatted(name, fs_type="ext4", force=False, **kwargs):
    """
    Manage filesystems of partitions.

    name
        The name of the block device

    fs_type
        The filesystem it should be formatted as

    force
        Force mke2fs to create a filesystem, even if the specified device is
        not a partition on a block special device. This option is only enabled
        for ext and xfs filesystems

        This option is dangerous, use it with caution.

        .. versionadded:: 2016.11.0
    """
    ret = {
        "changes": {},
        "comment": "{0} already formatted with {1}".format(name, fs_type),
        "name": name,
        "result": False,
    }

    if not os.path.exists(name):
        ret["comment"] = "{0} does not exist".format(name)
        return ret

    current_fs = _checkblk(name)

    if current_fs == fs_type:
        ret["result"] = True
        return ret
    elif not salt.utils.path.which("mkfs.{0}".format(fs_type)):
        ret["comment"] = "Invalid fs_type: {0}".format(fs_type)
        ret["result"] = False
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Changes to {0} will be applied ".format(name)
        ret["result"] = None
        return ret

    __salt__["disk.format"](name, fs_type, force=force, **kwargs)

    # Repeat fstype check up to 10 times with 3s sleeping between each
    # to avoid detection failing although mkfs has succeeded
    # see https://github.com/saltstack/salt/issues/25775
    # This retry maybe superfluous - switching to blkid
    for i in range(10):

        log.info("Check blk fstype attempt %d of 10", i + 1)
        current_fs = _checkblk(name)

        if current_fs == fs_type:
            ret["comment"] = ("{0} has been formatted " "with {1}").format(
                name, fs_type
            )
            ret["changes"] = {"new": fs_type, "old": current_fs}
            ret["result"] = True
            return ret

        if current_fs == "":
            log.info("Waiting 3s before next check")
            time.sleep(3)
        else:
            break

    ret["comment"] = "Failed to format {0}".format(name)
    ret["result"] = False
    return ret


def _checkblk(name):
    """
    Check if the blk exists and return its fstype if ok
    """

    blk = __salt__["cmd.run"](
        ["blkid", "-o", "value", "-s", "TYPE", name], ignore_retcode=True
    )
    return "" if not blk else blk
