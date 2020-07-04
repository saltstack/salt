# -*- coding: utf-8 -*-
"""
Managing software RAID with mdadm
==================================

:depends:    mdadm

A state module for creating or destroying software RAID devices.

.. code-block:: yaml

    /dev/md0:
      raid.present:
        - level: 5
        - devices:
          - /dev/xvdd
          - /dev/xvde
          - /dev/xvdf
        - chunk: 256
        - run: True
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
import salt.utils.path

# Set up logger
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "raid"


def __virtual__():
    """
    mdadm provides raid functions for Linux
    """
    if __grains__["kernel"] != "Linux":
        return (False, "Only supported on Linux")
    if not salt.utils.path.which("mdadm"):
        return (False, "Unable to locate command: mdadm")
    return __virtualname__


def present(name, level, devices, **kwargs):
    """
    Verify that the raid is present

    .. versionchanged:: 2014.7.0

    name
        The name of raid device to be created

    level
                The RAID level to use when creating the raid.

    devices
        A list of devices used to build the array.

    kwargs
        Optional arguments to be passed to mdadm.

    Example:

    .. code-block:: yaml

        /dev/md0:
          raid.present:
            - level: 5
            - devices:
              - /dev/xvdd
              - /dev/xvde
              - /dev/xvdf
            - chunk: 256
            - run: True
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    # Device exists
    raids = __salt__["raid.list"]()
    present = raids.get(name)

    # Decide whether to create or assemble
    missing = []
    uuid_dict = {}
    new_devices = []

    for dev in devices:
        if dev == "missing" or not __salt__["file.access"](dev, "f"):
            missing.append(dev)
            continue
        superblock = __salt__["raid.examine"](dev, quiet=True)

        if "MD_UUID" in superblock:
            uuid = superblock["MD_UUID"]
            if uuid not in uuid_dict:
                uuid_dict[uuid] = []
            uuid_dict[uuid].append(dev)
        else:
            new_devices.append(dev)

    if len(uuid_dict) > 1:
        ret[
            "comment"
        ] = "Devices are a mix of RAID constituents with multiple MD_UUIDs: {0}.".format(
            sorted(uuid_dict)
        )
        ret["result"] = False
        return ret
    elif len(uuid_dict) == 1:
        uuid = next(iter(uuid_dict))
        if present and present["uuid"] != uuid:
            ret[
                "comment"
            ] = "Devices MD_UUIDs: {0} differs from present RAID uuid {1}.".format(
                uuid, present["uuid"]
            )
            ret["result"] = False
            return ret

        devices_with_superblock = uuid_dict[uuid]
    else:
        devices_with_superblock = []

    if present:
        do_assemble = False
        do_create = False
    elif len(devices_with_superblock) > 0:
        do_assemble = True
        do_create = False
        verb = "assembled"
    else:
        if len(new_devices) == 0:
            ret["comment"] = "All devices are missing: {0}.".format(missing)
            ret["result"] = False
            return ret
        do_assemble = False
        do_create = True
        verb = "created"

    # If running with test use the test_mode with create or assemble
    if __opts__["test"]:
        if do_assemble:
            res = __salt__["raid.assemble"](
                name, devices_with_superblock, test_mode=True, **kwargs
            )
        elif do_create:
            res = __salt__["raid.create"](
                name,
                level,
                new_devices + ["missing"] * len(missing),
                test_mode=True,
                **kwargs
            )

        if present:
            ret["comment"] = "Raid {0} already present.".format(name)

        if do_assemble or do_create:
            ret["comment"] = "Raid will be {0} with: {1}".format(verb, res)
            ret["result"] = None

        if (do_assemble or present) and len(new_devices) > 0:
            ret["comment"] += " New devices will be added: {0}".format(new_devices)
            ret["result"] = None

        if len(missing) > 0:
            ret["comment"] += " Missing devices: {0}".format(missing)

        return ret

    # Attempt to create or assemble the array
    if do_assemble:
        __salt__["raid.assemble"](name, devices_with_superblock, **kwargs)
    elif do_create:
        __salt__["raid.create"](
            name, level, new_devices + ["missing"] * len(missing), **kwargs
        )

    if not present:
        raids = __salt__["raid.list"]()
        changes = raids.get(name)
        if changes:
            ret["comment"] = "Raid {0} {1}.".format(name, verb)
            ret["changes"] = changes
            # Saving config
            __salt__["raid.save_config"]()
        else:
            ret["comment"] = "Raid {0} failed to be {1}.".format(name, verb)
            ret["result"] = False
    else:
        ret["comment"] = "Raid {0} already present.".format(name)

    if (do_assemble or present) and len(new_devices) > 0 and ret["result"]:
        for d in new_devices:
            res = __salt__["raid.add"](name, d)
            if not res:
                ret["comment"] += " Unable to add {0} to {1}.\n".format(d, name)
                ret["result"] = False
            else:
                ret["comment"] += " Added new device {0} to {1}.\n".format(d, name)
        if ret["result"]:
            ret["changes"]["added"] = new_devices

    if len(missing) > 0:
        ret["comment"] += " Missing devices: {0}".format(missing)

    return ret


def absent(name):
    """
    Verify that the raid is absent

    name
        The name of raid device to be destroyed

    .. code-block:: yaml

        /dev/md0:
          raid:
            - absent
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    # Raid does not exist
    if name not in __salt__["raid.list"]():
        ret["comment"] = "Raid {0} already absent".format(name)
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Raid {0} is set to be destroyed".format(name)
        ret["result"] = None
        return ret
    else:
        # Attempt to destroy raid
        ret["result"] = __salt__["raid.destroy"](name)

        if ret["result"]:
            ret["comment"] = "Raid {0} has been destroyed".format(name)
        else:
            ret["comment"] = "Raid {0} failed to be destroyed".format(name)
        return ret
