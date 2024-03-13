"""
Management of Linux logical volumes
===================================

A state module to manage LVMs

.. code-block:: yaml

    /dev/sda:
      lvm.pv_present

    my_vg:
      lvm.vg_present:
        - devices: /dev/sda

    lvroot:
      lvm.lv_present:
        - vgname: my_vg
        - size: 10G
        - stripes: 5
        - stripesize: 8K
"""

import os

import salt.utils.path


def __virtual__():
    """
    Only load the module if lvm is installed
    """
    if salt.utils.path.which("lvm"):
        return "lvm"
    return (False, "lvm command not found")


def _convert_to_mb(size):

    str_size = str(size).lower()
    unit = str_size[-1:]
    if unit.isdigit():
        unit = "m"
    elif unit == "b":
        unit = str_size[-2:-1]
        str_size = str_size[:-2]
    else:
        str_size = str_size[:-1]

    if str_size[-1:].isdigit():
        size = int(str_size)
    else:
        raise salt.exceptions.ArgumentValueError(f"Size {size} is invalid.")

    if unit == "s":
        target_size = size / 2048
    elif unit == "m":
        target_size = size
    elif unit == "g":
        target_size = size * 1024
    elif unit == "t":
        target_size = size * 1024 * 1024
    elif unit == "p":
        target_size = size * 1024 * 1024 * 1024
    else:
        raise salt.exceptions.ArgumentValueError(f"Unit {unit} is invalid.")
    return target_size


def pv_present(name, **kwargs):
    """
    Set a Physical Device to be used as an LVM Physical Volume

    name
        The device name to initialize.

    kwargs
        Any supported options to pvcreate. See
        :mod:`linux_lvm <salt.modules.linux_lvm>` for more details.
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    if __salt__["lvm.pvdisplay"](name, quiet=True):
        ret["comment"] = f"Physical Volume {name} already present"
    elif __opts__["test"]:
        ret["comment"] = f"Physical Volume {name} is set to be created"
        ret["result"] = None
        return ret
    else:
        changes = __salt__["lvm.pvcreate"](name, **kwargs)

        if __salt__["lvm.pvdisplay"](name):
            ret["comment"] = f"Created Physical Volume {name}"
            ret["changes"]["created"] = changes
        else:
            ret["comment"] = f"Failed to create Physical Volume {name}"
            ret["result"] = False
    return ret


def pv_absent(name):
    """
    Ensure that a Physical Device is not being used by lvm

    name
        The device name to initialize.
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    if not __salt__["lvm.pvdisplay"](name, quiet=True):
        ret["comment"] = f"Physical Volume {name} does not exist"
    elif __opts__["test"]:
        ret["comment"] = f"Physical Volume {name} is set to be removed"
        ret["result"] = None
        return ret
    else:
        changes = __salt__["lvm.pvremove"](name)

        if __salt__["lvm.pvdisplay"](name, quiet=True):
            ret["comment"] = f"Failed to remove Physical Volume {name}"
            ret["result"] = False
        else:
            ret["comment"] = f"Removed Physical Volume {name}"
            ret["changes"]["removed"] = changes
    return ret


def vg_present(name, devices=None, **kwargs):
    """
    Create an LVM Volume Group

    name
        The Volume Group name to create

    devices
        A list of devices that will be added to the Volume Group

    kwargs
        Any supported options to vgcreate. See
        :mod:`linux_lvm <salt.modules.linux_lvm>` for more details.
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}
    if isinstance(devices, str):
        devices = devices.split(",")

    if __salt__["lvm.vgdisplay"](name, quiet=True):
        ret["comment"] = f"Volume Group {name} already present"
        for device in devices:
            realdev = os.path.realpath(device)
            pvs = __salt__["lvm.pvdisplay"](realdev, real=True)
            if pvs and pvs.get(realdev, None):
                if pvs[realdev]["Volume Group Name"] == name:
                    ret["comment"] = "{}\n{}".format(
                        ret["comment"], f"{device} is part of Volume Group"
                    )
                elif pvs[realdev]["Volume Group Name"] in ["", "#orphans_lvm2"]:
                    __salt__["lvm.vgextend"](name, device)
                    pvs = __salt__["lvm.pvdisplay"](realdev, real=True)
                    if pvs[realdev]["Volume Group Name"] == name:
                        ret["changes"].update({device: f"added to {name}"})
                    else:
                        ret["comment"] = "{}\n{}".format(
                            ret["comment"], f"{device} could not be added"
                        )
                        ret["result"] = False
                else:
                    ret["comment"] = "{}\n{}".format(
                        ret["comment"],
                        "{} is part of {}".format(
                            device, pvs[realdev]["Volume Group Name"]
                        ),
                    )
                    ret["result"] = False
            else:
                ret["comment"] = "{}\n{}".format(
                    ret["comment"], f"pv {device} is not present"
                )
                ret["result"] = False
    elif __opts__["test"]:
        ret["comment"] = f"Volume Group {name} is set to be created"
        ret["result"] = None
        return ret
    else:
        changes = __salt__["lvm.vgcreate"](name, devices, **kwargs)

        if __salt__["lvm.vgdisplay"](name):
            ret["comment"] = f"Created Volume Group {name}"
            ret["changes"]["created"] = changes
        else:
            ret["comment"] = f"Failed to create Volume Group {name}"
            ret["result"] = False
    return ret


def vg_absent(name):
    """
    Remove an LVM volume group

    name
        The volume group to remove
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    if not __salt__["lvm.vgdisplay"](name, quiet=True):
        ret["comment"] = f"Volume Group {name} already absent"
    elif __opts__["test"]:
        ret["comment"] = f"Volume Group {name} is set to be removed"
        ret["result"] = None
        return ret
    else:
        changes = __salt__["lvm.vgremove"](name)

        if not __salt__["lvm.vgdisplay"](name, quiet=True):
            ret["comment"] = f"Removed Volume Group {name}"
            ret["changes"]["removed"] = changes
        else:
            ret["comment"] = f"Failed to remove Volume Group {name}"
            ret["result"] = False
    return ret


def lv_present(
    name,
    vgname=None,
    size=None,
    extents=None,
    snapshot=None,
    pv="",
    thinvolume=False,
    thinpool=False,
    force=False,
    resizefs=False,
    **kwargs,
):
    """
    Ensure that a Logical Volume is present, creating it if absent.

    name
        The name of the Logical Volume

    vgname
        The name of the Volume Group on which the Logical Volume resides

    size
        The size of the Logical Volume in megabytes, or use a suffix
        such as S, M, G, T, P for 512 byte sectors, megabytes, gigabytes
        or terabytes respectively. The suffix is case insensitive.

    extents
        The number of logical extents allocated to the Logical Volume
        It can be a percentage allowed by lvcreate's syntax, in this case
        it will set the Logical Volume initial size and won't be resized.

    snapshot
        The name of the snapshot

    pv
        The Physical Volume to use

    kwargs
        Any supported options to lvcreate. See
        :mod:`linux_lvm <salt.modules.linux_lvm>` for more details.

    .. versionadded:: 2016.11.0

    thinvolume
        Logical Volume is thinly provisioned

    thinpool
        Logical Volume is a thin pool

    .. versionadded:: 2018.3.0

    force
        Assume yes to all prompts

    .. versionadded:: 3002

    resizefs
        Use fsadm to resize the logical volume filesystem if needed

    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    if extents and size:
        ret["comment"] = "Only one of extents or size can be specified."
        ret["result"] = False
        return ret

    if size:
        size_mb = _convert_to_mb(size)

    _snapshot = None

    if snapshot:
        _snapshot = name
        name = snapshot

    if thinvolume:
        lvpath = "/dev/{}/{}".format(vgname.split("/")[0], name)
    else:
        lvpath = f"/dev/{vgname}/{name}"

    lv_info = __salt__["lvm.lvdisplay"](lvpath, quiet=True)
    lv_info = lv_info.get(lvpath)

    if not lv_info:
        if __opts__["test"]:
            ret["comment"] = f"Logical Volume {name} is set to be created"
            ret["result"] = None
            return ret
        else:
            changes = __salt__["lvm.lvcreate"](
                name,
                vgname,
                size=size,
                extents=extents,
                snapshot=_snapshot,
                pv=pv,
                thinvolume=thinvolume,
                thinpool=thinpool,
                force=force,
                **kwargs,
            )

            if __salt__["lvm.lvdisplay"](lvpath):
                ret["comment"] = f"Created Logical Volume {name}"
                ret["changes"]["created"] = changes
            else:
                ret["comment"] = "Failed to create Logical Volume {}. Error: {}".format(
                    name, changes["Output from lvcreate"]
                )
                ret["result"] = False
    else:
        ret["comment"] = f"Logical Volume {name} already present"

        if size or extents:
            old_extents = int(lv_info["Current Logical Extents Associated"])
            old_size_mb = _convert_to_mb(lv_info["Logical Volume Size"] + "s")
            if size:
                extents = old_extents
            else:
                # ignore percentage "extents" if the logical volume already exists
                if "%" in str(extents):
                    ret["comment"] = (
                        "Logical Volume {} already present, {} won't be resized.".format(
                            name, extents
                        )
                    )
                    extents = old_extents
                size_mb = old_size_mb

            if force is False and (size_mb < old_size_mb or extents < old_extents):
                ret["comment"] = (
                    "To reduce a Logical Volume option 'force' must be True."
                )
                ret["result"] = False
                return ret

            if size_mb != old_size_mb or extents != old_extents:
                if __opts__["test"]:
                    ret["comment"] = "Logical Volume {} is set to be resized".format(
                        name
                    )
                    ret["result"] = None
                    return ret
                else:
                    if size:
                        changes = __salt__["lvm.lvresize"](
                            lvpath=lvpath, size=size, resizefs=resizefs, force=force
                        )
                    else:
                        changes = __salt__["lvm.lvresize"](
                            lvpath=lvpath,
                            extents=extents,
                            resizefs=resizefs,
                            force=force,
                        )

                    if not changes:
                        ret["comment"] = (
                            "Failed to resize Logical Volume. Unknown Error."
                        )
                        ret["result"] = False

                    lv_info = __salt__["lvm.lvdisplay"](lvpath, quiet=True)[lvpath]
                    new_size_mb = _convert_to_mb(lv_info["Logical Volume Size"] + "s")
                    if new_size_mb != old_size_mb:
                        ret["comment"] = f"Resized Logical Volume {name}"
                        ret["changes"]["resized"] = changes
                    else:
                        ret["comment"] = (
                            "Failed to resize Logical Volume {}.\nError: {}".format(
                                name, changes["Output from lvresize"]
                            )
                        )
                        ret["result"] = False
    return ret


def lv_absent(name, vgname=None):
    """
    Remove a given existing Logical Volume from a named existing volume group

    name
        The Logical Volume to remove

    vgname
        The name of the Volume Group on which the Logical Volume resides
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    lvpath = f"/dev/{vgname}/{name}"
    if not __salt__["lvm.lvdisplay"](lvpath, quiet=True):
        ret["comment"] = f"Logical Volume {name} already absent"
    elif __opts__["test"]:
        ret["comment"] = f"Logical Volume {name} is set to be removed"
        ret["result"] = None
        return ret
    else:
        changes = __salt__["lvm.lvremove"](name, vgname)

        if not __salt__["lvm.lvdisplay"](lvpath, quiet=True):
            ret["comment"] = f"Removed Logical Volume {name}"
            ret["changes"]["removed"] = changes
        else:
            ret["comment"] = f"Failed to remove Logical Volume {name}"
            ret["result"] = False
    return ret
