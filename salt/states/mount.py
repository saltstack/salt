# -*- coding: utf-8 -*-
"""
Mounting of filesystems
=======================

Mount any type of mountable filesystem with the mounted function:

.. code-block:: yaml

    /mnt/sdb:
      mount.mounted:
        - device: /dev/sdb1
        - fstype: ext4
        - mkmnt: True
        - opts:
          - defaults

    /srv/bigdata:
      mount.mounted:
        - device: UUID=066e0200-2867-4ebe-b9e6-f30026ca2314
        - fstype: xfs
        - opts: nobootwait,noatime,nodiratime,nobarrier,logbufs=8
        - dump: 0
        - pass_num: 2
        - persist: True
        - mkmnt: True

    /var/lib/bigdata:
      mount.mounted:
        - device: /srv/bigdata
        - fstype: none
        - opts: bind
        - dump: 0
        - pass_num: 0
        - persist: True
        - mkmnt: True
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import python libs
import os.path
import re

from salt.ext import six

# Import salt libs
from salt.ext.six import string_types

log = logging.getLogger(__name__)


def _size_convert(_re_size):
    converted_size = int(_re_size.group("size_value"))
    if _re_size.group("size_unit") == "m":
        converted_size = int(converted_size) * 1024
    if _re_size.group("size_unit") == "g":
        converted_size = int(converted_size) * 1024 * 1024
    return converted_size


def mounted(
    name,
    device,
    fstype,
    mkmnt=False,
    opts="defaults",
    dump=0,
    pass_num=0,
    config="/etc/fstab",
    persist=True,
    mount=True,
    user=None,
    match_on="auto",
    device_name_regex=None,
    extra_mount_invisible_options=None,
    extra_mount_invisible_keys=None,
    extra_mount_ignore_fs_keys=None,
    extra_mount_translate_options=None,
    hidden_opts=None,
    **kwargs
):
    """
    Verify that a device is mounted

    name
        The path to the location where the device is to be mounted

    device
        The device name, typically the device node, such as ``/dev/sdb1``
        or ``UUID=066e0200-2867-4ebe-b9e6-f30026ca2314`` or ``LABEL=DATA``

    fstype
        The filesystem type, this will be ``xfs``, ``ext2/3/4`` in the case of classic
        filesystems, ``fuse`` in the case of fuse mounts, and ``nfs`` in the case of nfs mounts

    mkmnt
        If the mount point is not present then the state will fail, set ``mkmnt: True``
        to create the mount point if it is otherwise not present

    opts
        A list object of options or a comma delimited list

    dump
        The dump value to be passed into the fstab, Default is ``0``

    pass_num
        The pass value to be passed into the fstab, Default is ``0``

    config
        Set an alternative location for the fstab, Default is ``/etc/fstab``

    persist
        Set if the mount should be saved in the fstab, Default is ``True``

    mount
        Set if the mount should be mounted immediately, Default is ``True``

    user
        The account used to execute the mount; this defaults to the user salt is
        running as on the minion

    match_on
        A name or list of fstab properties on which this state should be applied.
        Default is ``auto``, a special value indicating to guess based on fstype.
        In general, ``auto`` matches on name for recognized special devices and
        device otherwise.

    device_name_regex
        A list of device exact names or regular expressions which should
        not force a remount. For example, glusterfs may be mounted with a
        comma-separated list of servers in fstab, but the /proc/self/mountinfo
        will show only the first available server.

        .. code-block:: jinja

            {% set glusterfs_ip_list = ['10.0.0.1', '10.0.0.2', '10.0.0.3'] %}

            mount glusterfs volume:
              mount.mounted:
                - name: /mnt/glusterfs_mount_point
                - device: {{ glusterfs_ip_list|join(',') }}:/volume_name
                - fstype: glusterfs
                - opts: _netdev,rw,defaults,direct-io-mode=disable
                - mkmnt: True
                - persist: True
                - dump: 0
                - pass_num: 0
                - device_name_regex:
                  - ({{ glusterfs_ip_list|join('|') }}):/volume_name

        .. versionadded:: 2016.11.0

    extra_mount_invisible_options
        A list of extra options that are not visible through the
        ``/proc/self/mountinfo`` interface.

        If a option is not visible through this interface it will always remount
        the device. This option extends the builtin ``mount_invisible_options``
        list.

    extra_mount_invisible_keys
        A list of extra key options that are not visible through the
        ``/proc/self/mountinfo`` interface.

        If a key option is not visible through this interface it will always
        remount the device. This option extends the builtin
        ``mount_invisible_keys`` list.

        A good example for a key option is the password option::

            password=badsecret

    extra_mount_ignore_fs_keys
        A dict of filesystem options which should not force a remount. This will update
        the internal dictionary. The dict should look like this::

            {
                'ramfs': ['size']
            }

    extra_mount_translate_options
        A dict of mount options that gets translated when mounted. To prevent a remount
        add additional options to the default dictionary. This will update the internal
        dictionary. The dictionary should look like this::

            {
                'tcp': 'proto=tcp',
                'udp': 'proto=udp'
            }

    hidden_opts
        A list of mount options that will be ignored when considering a remount
        as part of the state application

        .. versionadded:: 2015.8.2
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    update_mount_cache = False

    if not name:
        ret["result"] = False
        ret["comment"] = "Must provide name to mount.mounted"
        return ret

    if not device:
        ret["result"] = False
        ret["comment"] = "Must provide device to mount.mounted"
        return ret

    if not fstype:
        ret["result"] = False
        ret["comment"] = "Must provide fstype to mount.mounted"
        return ret

    if device_name_regex is None:
        device_name_regex = []

    # Defaults is not a valid option on Mac OS
    if __grains__["os"] in ["MacOS", "Darwin"] and opts == "defaults":
        opts = "noowners"

    # Defaults is not a valid option on AIX
    if __grains__["os"] in ["AIX"]:
        if opts == "defaults":
            opts = ""

    # Make sure that opts is correct, it can be a list or a comma delimited
    # string
    if isinstance(opts, string_types):
        opts = opts.split(",")

    if isinstance(hidden_opts, string_types):
        hidden_opts = hidden_opts.split(",")

    # remove possible trailing slash
    if not name == "/":
        name = name.rstrip("/")

    device_list = []
    # Get the active data
    active = __salt__["mount.active"](extended=True)
    real_name = os.path.realpath(name)
    if device.startswith("/"):
        if "bind" in opts and real_name in active:
            _device = device
            if active[real_name]["device"].startswith("/"):
                # Find the device that the bind really points at.
                while True:
                    if _device in active:
                        _real_device = active[_device]["device"]
                        opts = list(
                            set(
                                opts
                                + active[_device]["opts"]
                                + active[_device]["superopts"]
                            )
                        )
                        active[real_name]["opts"].append("bind")
                        break
                    _device = os.path.dirname(_device)
                real_device = _real_device
            else:
                # Remote file systems act differently.
                if _device in active:
                    opts = list(
                        set(
                            opts
                            + active[_device]["opts"]
                            + active[_device]["superopts"]
                        )
                    )
                    active[real_name]["opts"].append("bind")
                real_device = active[real_name]["device"]
        else:
            real_device = os.path.realpath(device)
    elif device.upper().startswith("UUID="):
        real_device = device.split("=")[1].strip('"').lower()
    elif device.upper().startswith("LABEL="):
        _label = device.split("=")[1]
        cmd = "blkid -t LABEL={0}".format(_label)
        res = __salt__["cmd.run_all"]("{0}".format(cmd))
        if res["retcode"] > 0:
            ret["comment"] = "Unable to find device with label {0}.".format(_label)
            ret["result"] = False
            return ret
        else:
            # output is a list of entries like this:
            # /dev/sda: LABEL="<label>" UUID="<uuid>" UUID_SUB="<uuid>" TYPE="btrfs"
            # exact list of properties varies between filesystems, but we're
            # only interested in the device in the first column
            for line in res["stdout"]:
                dev_with_label = line.split(":")[0]
                device_list.append(dev_with_label)
            real_device = device_list[0]
    else:
        real_device = device

    # LVS devices have 2 names under /dev:
    # /dev/mapper/vg--name-lv--name and /dev/vg-name/lv-name
    # No matter what name is used for mounting,
    # mount always displays the device as /dev/mapper/vg--name-lv--name
    # Note the double-dash escaping.
    # So, let's call that the canonical device name
    # We should normalize names of the /dev/vg-name/lv-name type to the canonical name
    lvs_match = re.match(r"^/dev/(?P<vg_name>[^/]+)/(?P<lv_name>[^/]+$)", device)
    if lvs_match:
        double_dash_escaped = dict(
            (k, re.sub(r"-", "--", v)) for k, v in six.iteritems(lvs_match.groupdict())
        )
        mapper_device = "/dev/mapper/{vg_name}-{lv_name}".format(**double_dash_escaped)
        if os.path.exists(mapper_device):
            real_device = mapper_device

    # When included in a Salt state file, FUSE devices are prefaced by the
    # filesystem type and a hash, e.g. sshfs.  In the mount list only the
    # hostname is included.  So if we detect that the device is a FUSE device
    # then we remove the prefaced string so that the device in state matches
    # the device in the mount list.
    fuse_match = re.match(r"^\w+\#(?P<device_name>.+)", device)
    if fuse_match:
        if "device_name" in fuse_match.groupdict():
            real_device = fuse_match.group("device_name")

    if real_name in active:
        if "superopts" not in active[real_name]:
            active[real_name]["superopts"] = []
        if mount:
            device_list.append(active[real_name]["device"])
            device_list.append(os.path.realpath(device_list[0]))
            alt_device = (
                active[real_name]["alt_device"]
                if "alt_device" in active[real_name]
                else None
            )
            uuid_device = (
                active[real_name]["device_uuid"]
                if "device_uuid" in active[real_name]
                else None
            )
            label_device = (
                active[real_name]["device_label"]
                if "device_label" in active[real_name]
                else None
            )
            if alt_device and alt_device not in device_list:
                device_list.append(alt_device)
            if uuid_device and uuid_device not in device_list:
                device_list.append(uuid_device)
            if label_device and label_device not in device_list:
                device_list.append(label_device)
            if opts:
                opts.sort()

                mount_invisible_options = [
                    "_netdev",
                    "actimeo",
                    "bg",
                    "comment",
                    "defaults",
                    "delay_connect",
                    "direct-io-mode",
                    "intr",
                    "loop",
                    "nointr",
                    "nobootwait",
                    "nofail",
                    "password",
                    "reconnect",
                    "retry",
                    "soft",
                    "auto",
                    "users",
                    "bind",
                    "nonempty",
                    "transform_symlinks",
                    "port",
                    "backup-volfile-servers",
                ]

                if extra_mount_invisible_options:
                    mount_invisible_options.extend(extra_mount_invisible_options)

                if hidden_opts:
                    mount_invisible_options = list(
                        set(mount_invisible_options) | set(hidden_opts)
                    )

                # options which are provided as key=value (e.g. password=Zohp5ohb)
                mount_invisible_keys = [
                    "actimeo",
                    "comment",
                    "credentials",
                    "direct-io-mode",
                    "password",
                    "port",
                    "retry",
                    "secretfile",
                ]

                if extra_mount_invisible_keys:
                    mount_invisible_keys.extend(extra_mount_invisible_keys)

                # Some filesystems have options which should not force a remount.
                mount_ignore_fs_keys = {"ramfs": ["size"]}

                if extra_mount_ignore_fs_keys:
                    mount_ignore_fs_keys.update(extra_mount_ignore_fs_keys)

                # Some options are translated once mounted
                mount_translate_options = {
                    "tcp": "proto=tcp",
                    "udp": "proto=udp",
                }

                if extra_mount_translate_options:
                    mount_translate_options.update(extra_mount_translate_options)

                for opt in opts:
                    if opt in mount_translate_options:
                        opt = mount_translate_options[opt]

                    keyval_option = opt.split("=")[0]
                    if keyval_option in mount_invisible_keys:
                        opt = keyval_option

                    size_match = re.match(
                        r"size=(?P<size_value>[0-9]+)(?P<size_unit>k|m|g)", opt
                    )
                    if size_match:
                        converted_size = _size_convert(size_match)
                        opt = "size={0}k".format(converted_size)
                    # make cifs option user synonym for option username which is reported by /proc/mounts
                    if fstype in ["cifs"] and opt.split("=")[0] == "user":
                        opt = "username={0}".format(opt.split("=")[1])

                    if opt.split("=")[0] in mount_ignore_fs_keys.get(fstype, []):
                        opt = opt.split("=")[0]

                    # convert uid/gid to numeric value from user/group name
                    name_id_opts = {"uid": "user.info", "gid": "group.info"}
                    if opt.split("=")[0] in name_id_opts and len(opt.split("=")) > 1:
                        _givenid = opt.split("=")[1]
                        _param = opt.split("=")[0]
                        _id = _givenid
                        if not re.match("[0-9]+$", _givenid):
                            _info = __salt__[name_id_opts[_param]](_givenid)
                            if _info and _param in _info:
                                _id = _info[_param]
                        opt = _param + "=" + six.text_type(_id)

                    _active_superopts = active[real_name].get("superopts", [])
                    for _active_opt in _active_superopts:
                        size_match = re.match(
                            r"size=(?P<size_value>[0-9]+)(?P<size_unit>k|m|g)",
                            _active_opt,
                        )
                        if size_match:
                            converted_size = _size_convert(size_match)
                            opt = "size={0}k".format(converted_size)
                            _active_superopts.remove(_active_opt)
                            _active_opt = "size={0}k".format(converted_size)
                            _active_superopts.append(_active_opt)

                    if (
                        opt not in active[real_name]["opts"]
                        and opt not in _active_superopts
                        and opt not in mount_invisible_options
                        and opt not in mount_ignore_fs_keys.get(fstype, [])
                        and opt not in mount_invisible_keys
                    ):
                        if __opts__["test"]:
                            ret["result"] = None
                            ret[
                                "comment"
                            ] = "Remount would be forced because options ({0}) changed".format(
                                opt
                            )
                            return ret
                        else:
                            # Some file systems require umounting and mounting if options change
                            # add others to list that require similiar functionality
                            if fstype in ["nfs", "cvfs"] or fstype.startswith("fuse"):
                                ret["changes"]["umount"] = (
                                    "Forced unmount and mount because "
                                    + "options ({0}) changed".format(opt)
                                )
                                unmount_result = __salt__["mount.umount"](real_name)
                                if unmount_result is True:
                                    mount_result = __salt__["mount.mount"](
                                        real_name,
                                        device,
                                        mkmnt=mkmnt,
                                        fstype=fstype,
                                        opts=opts,
                                    )
                                    ret["result"] = mount_result
                                else:
                                    ret["result"] = False
                                    ret[
                                        "comment"
                                    ] = "Unable to unmount {0}: {1}.".format(
                                        real_name, unmount_result
                                    )
                                    return ret
                            else:
                                ret["changes"]["umount"] = (
                                    "Forced remount because "
                                    + "options ({0}) changed".format(opt)
                                )
                                remount_result = __salt__["mount.remount"](
                                    real_name,
                                    device,
                                    mkmnt=mkmnt,
                                    fstype=fstype,
                                    opts=opts,
                                )
                                ret["result"] = remount_result
                                # Cleanup after the remount, so we
                                # don't write remount into fstab
                                if "remount" in opts:
                                    opts.remove("remount")

                            # Update the cache
                            update_mount_cache = True

                mount_cache = __salt__["mount.read_mount_cache"](real_name)
                if "opts" in mount_cache:
                    _missing = [opt for opt in mount_cache["opts"] if opt not in opts]

                    if _missing:
                        if __opts__["test"]:
                            ret["result"] = None
                            ret["comment"] = (
                                "Remount would be forced because"
                                " options ({0})"
                                "changed".format(",".join(_missing))
                            )
                            return ret
                        else:
                            # Some file systems require umounting and mounting if options change
                            # add others to list that require similiar functionality
                            if fstype in ["nfs", "cvfs"] or fstype.startswith("fuse"):
                                ret["changes"]["umount"] = (
                                    "Forced unmount and mount because "
                                    + "options ({0}) changed".format(opt)
                                )
                                unmount_result = __salt__["mount.umount"](real_name)
                                if unmount_result is True:
                                    mount_result = __salt__["mount.mount"](
                                        real_name,
                                        device,
                                        mkmnt=mkmnt,
                                        fstype=fstype,
                                        opts=opts,
                                    )
                                    ret["result"] = mount_result
                                else:
                                    ret["result"] = False
                                    ret[
                                        "comment"
                                    ] = "Unable to unmount {0}: {1}.".format(
                                        real_name, unmount_result
                                    )
                                    return ret
                            else:
                                ret["changes"]["umount"] = (
                                    "Forced remount because "
                                    + "options ({0}) changed".format(opt)
                                )
                                remount_result = __salt__["mount.remount"](
                                    real_name,
                                    device,
                                    mkmnt=mkmnt,
                                    fstype=fstype,
                                    opts=opts,
                                )
                                ret["result"] = remount_result
                                # Cleanup after the remount, so we
                                # don't write remount into fstab
                                if "remount" in opts:
                                    opts.remove("remount")

                        update_mount_cache = True
                else:
                    update_mount_cache = True

            if real_device not in device_list:
                # name matches but device doesn't - need to umount
                _device_mismatch_is_ignored = None
                for regex in list(device_name_regex):
                    for _device in device_list:
                        if re.match(regex, _device):
                            _device_mismatch_is_ignored = _device
                            break
                if _device_mismatch_is_ignored:
                    ret["result"] = True
                    ret["comment"] = (
                        "An umount will not be forced "
                        + "because device matched device_name_regex: "
                        + _device_mismatch_is_ignored
                    )
                elif __opts__["test"]:
                    ret["result"] = None
                    ret["comment"] = (
                        "An umount would have been forced "
                        + "because devices do not match.  Watched: "
                        + device
                    )
                else:
                    ret["changes"]["umount"] = (
                        "Forced unmount because devices "
                        + "don't match. Wanted: "
                        + device
                    )
                    if real_device != device:
                        ret["changes"]["umount"] += " (" + real_device + ")"
                    ret["changes"]["umount"] += ", current: " + ", ".join(device_list)
                    out = __salt__["mount.umount"](real_name, user=user)
                    active = __salt__["mount.active"](extended=True)
                    if real_name in active:
                        ret["comment"] = "Unable to unmount"
                        ret["result"] = None
                        return ret
                    update_mount_cache = True
            else:
                ret["comment"] = "Target was already mounted"
    # using a duplicate check so I can catch the results of a umount
    if real_name not in active:
        if mount:
            # The mount is not present! Mount it
            if __opts__["test"]:
                ret["result"] = None
                if os.path.exists(name):
                    ret["comment"] = "{0} would be mounted".format(name)
                elif mkmnt:
                    ret["comment"] = "{0} would be created and mounted".format(name)
                else:
                    ret[
                        "comment"
                    ] = "{0} does not exist and would not be created".format(name)
                return ret

            if not os.path.exists(name) and not mkmnt:
                ret["result"] = False
                ret["comment"] = "Mount directory is not present"
                return ret

            out = __salt__["mount.mount"](name, device, mkmnt, fstype, opts, user=user)
            active = __salt__["mount.active"](extended=True)
            update_mount_cache = True
            if isinstance(out, string_types):
                # Failed to (re)mount, the state has failed!
                ret["comment"] = out
                ret["result"] = False
                return ret
            elif real_name in active:
                # (Re)mount worked!
                ret["comment"] = "Target was successfully mounted"
                ret["changes"]["mount"] = True
        elif not os.path.exists(name):
            if __opts__["test"]:
                ret["result"] = None
                if mkmnt:
                    ret["comment"] = "{0} would be created, but not mounted".format(
                        name
                    )
                else:
                    ret[
                        "comment"
                    ] = "{0} does not exist and would neither be created nor mounted".format(
                        name
                    )
            elif mkmnt:
                __salt__["file.mkdir"](name, user=user)
                ret["comment"] = "{0} was created, not mounted".format(name)
            else:
                ret["comment"] = "{0} not present and not mounted".format(name)
        else:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = "{0} would not be mounted".format(name)
            else:
                ret["comment"] = "{0} not mounted".format(name)

    if persist:
        if "/etc/fstab" == config:
            # Override default for Mac OS
            if __grains__["os"] in ["MacOS", "Darwin"]:
                config = "/etc/auto_salt"

            # Override default for AIX
            elif "AIX" in __grains__["os"]:
                config = "/etc/filesystems"

        if __opts__["test"]:
            if __grains__["os"] in ["MacOS", "Darwin"]:
                out = __salt__["mount.set_automaster"](
                    name, device, fstype, opts, config, test=True
                )
            elif __grains__["os"] in ["AIX"]:
                out = __salt__["mount.set_filesystems"](
                    name,
                    device,
                    fstype,
                    opts,
                    mount,
                    config,
                    test=True,
                    match_on=match_on,
                )
            else:
                out = __salt__["mount.set_fstab"](
                    name,
                    device,
                    fstype,
                    opts,
                    dump,
                    pass_num,
                    config,
                    test=True,
                    match_on=match_on,
                )
            if out != "present":
                ret["result"] = None
                if out == "new":
                    if mount:
                        comment = (
                            "{0} is mounted, but needs to be "
                            "written to the fstab in order to be "
                            "made persistent."
                        ).format(name)
                    else:
                        comment = (
                            "{0} needs to be "
                            "written to the fstab in order to be "
                            "made persistent."
                        ).format(name)
                elif out == "change":
                    if mount:
                        comment = (
                            "{0} is mounted, but its fstab entry " "must be updated."
                        ).format(name)
                    else:
                        comment = ("The {0} fstab entry " "must be updated.").format(
                            name
                        )
                else:
                    ret["result"] = False
                    comment = (
                        "Unable to detect fstab status for "
                        "mount point {0} due to unexpected "
                        "output '{1}' from call to "
                        "mount.set_fstab. This is most likely "
                        "a bug."
                    ).format(name, out)
                if "comment" in ret:
                    ret["comment"] = "{0}. {1}".format(ret["comment"], comment)
                else:
                    ret["comment"] = comment
                return ret

        else:
            if __grains__["os"] in ["MacOS", "Darwin"]:
                out = __salt__["mount.set_automaster"](
                    name, device, fstype, opts, config
                )
            elif __grains__["os"] in ["AIX"]:
                out = __salt__["mount.set_filesystems"](
                    name, device, fstype, opts, mount, config, match_on=match_on
                )
            else:
                out = __salt__["mount.set_fstab"](
                    name,
                    device,
                    fstype,
                    opts,
                    dump,
                    pass_num,
                    config,
                    match_on=match_on,
                )

        if update_mount_cache:
            cache_result = __salt__["mount.write_mount_cache"](
                real_name, device, mkmnt=mkmnt, fstype=fstype, mount_opts=opts
            )

        if out == "present":
            ret["comment"] += ". Entry already exists in the fstab."
            return ret
        if out == "new":
            ret["changes"]["persist"] = "new"
            ret["comment"] += ". Added new entry to the fstab."
            return ret
        if out == "change":
            ret["changes"]["persist"] = "update"
            ret["comment"] += ". Updated the entry in the fstab."
            return ret
        if out == "bad config":
            ret["result"] = False
            ret["comment"] += ". However, the fstab was not found."
            return ret

    return ret


def swap(name, persist=True, config="/etc/fstab"):
    """
    Activates a swap device

    .. code-block:: yaml

        /root/swapfile:
          mount.swap

    .. note::
        ``swap`` does not currently support LABEL
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    on_ = __salt__["mount.swaps"]()

    if __salt__["file.is_link"](name):
        real_swap_device = __salt__["file.readlink"](name)
        if not real_swap_device.startswith("/"):
            real_swap_device = "/dev/{0}".format(os.path.basename(real_swap_device))
    else:
        real_swap_device = name

    if real_swap_device in on_:
        ret["comment"] = "Swap {0} already active".format(name)
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Swap {0} is set to be activated".format(name)
    else:
        __salt__["mount.swapon"](real_swap_device)

        on_ = __salt__["mount.swaps"]()

        if real_swap_device in on_:
            ret["comment"] = "Swap {0} activated".format(name)
            ret["changes"] = on_[real_swap_device]
        else:
            ret["comment"] = "Swap {0} failed to activate".format(name)
            ret["result"] = False

    if persist:
        device_key_name = "device"
        if "AIX" in __grains__["os"]:
            device_key_name = "dev"
            if "/etc/fstab" == config:
                # Override default for AIX
                config = "/etc/filesystems"
            fstab_data = __salt__["mount.filesystems"](config)
        else:
            fstab_data = __salt__["mount.fstab"](config)
        if __opts__["test"]:
            if name not in fstab_data and name not in [
                fstab_data[item]["device"] for item in fstab_data
            ]:
                ret["result"] = None
                if name in on_:
                    ret["comment"] = (
                        "Swap {0} is set to be added to the "
                        "fstab and to be activated"
                    ).format(name)
            return ret

        if "none" in fstab_data:
            if (
                fstab_data["none"][device_key_name] == name
                and fstab_data["none"]["fstype"] != "swap"
            ):
                return ret

        if "AIX" in __grains__["os"]:
            out = None
            ret["result"] = False
            ret["comment"] += ". swap not present in /etc/filesystems on AIX."
            return ret
        else:
            # present, new, change, bad config
            # Make sure the entry is in the fstab
            out = __salt__["mount.set_fstab"](
                "none", name, "swap", ["defaults"], 0, 0, config
            )
        if out == "present":
            return ret
        if out == "new":
            ret["changes"]["persist"] = "new"
            ret["comment"] += ". Added new entry to the fstab."
            return ret
        if out == "change":
            ret["changes"]["persist"] = "update"
            ret["comment"] += ". Updated the entry in the fstab."
            return ret
        if out == "bad config":
            ret["result"] = False
            ret["comment"] += ". However, the fstab was not found."
            return ret
    return ret


def unmounted(
    name, device=None, config="/etc/fstab", persist=False, user=None, **kwargs
):
    """
    .. versionadded:: 0.17.0

    Verify that a device is not mounted

    name
        The path to the location where the device is to be unmounted from

    device
        The device to be unmounted.  This is optional because the device could
        be mounted in multiple places.

        .. versionadded:: 2015.5.0

    config
        Set an alternative location for the fstab, Default is ``/etc/fstab``

    persist
        Set if the mount should be purged from the fstab, Default is ``False``

    user
        The user to own the mount; this defaults to the user salt is
        running as on the minion
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    update_mount_cache = False

    if not name:
        ret["result"] = False
        ret["comment"] = "Must provide name to mount.unmounted"
        return ret

    # Get the active data
    active = __salt__["mount.active"](extended=True)
    if name not in active:
        # Nothing to unmount
        ret["comment"] = "Target was already unmounted"
    if name in active:
        # The mount is present! Unmount it
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = ("Mount point {0} is mounted but should not " "be").format(
                name
            )
            return ret
        if device:
            out = __salt__["mount.umount"](name, device, user=user)
            update_mount_cache = True
        else:
            out = __salt__["mount.umount"](name, user=user)
            update_mount_cache = True
        if isinstance(out, string_types):
            # Failed to umount, the state has failed!
            ret["comment"] = out
            ret["result"] = False
        elif out is True:
            # umount worked!
            ret["comment"] = "Target was successfully unmounted"
            ret["changes"]["umount"] = True
        else:
            ret["comment"] = "Execute set to False, Target was not unmounted"
            ret["result"] = True

    if update_mount_cache:
        cache_result = __salt__["mount.delete_mount_cache"](name)

    if persist:
        device_key_name = "device"
        # Override default for Mac OS
        if __grains__["os"] in ["MacOS", "Darwin"] and config == "/etc/fstab":
            config = "/etc/auto_salt"
            fstab_data = __salt__["mount.automaster"](config)
        elif "AIX" in __grains__["os"]:
            device_key_name = "dev"
            if config == "/etc/fstab":
                config = "/etc/filesystems"
            fstab_data = __salt__["mount.filesystems"](config)
        else:
            fstab_data = __salt__["mount.fstab"](config)

        if name not in fstab_data:
            ret["comment"] += ". fstab entry not found"
        else:
            if device:
                if fstab_data[name][device_key_name] != device:
                    ret["comment"] += ". fstab entry for device {0} not found".format(
                        device
                    )
                    return ret
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = (
                    "Mount point {0} is unmounted but needs to "
                    "be purged from {1} to be made "
                    "persistent"
                ).format(name, config)
                return ret
            else:
                if __grains__["os"] in ["MacOS", "Darwin"]:
                    out = __salt__["mount.rm_automaster"](name, device, config)
                elif "AIX" in __grains__["os"]:
                    out = __salt__["mount.rm_filesystems"](name, device, config)
                else:
                    out = __salt__["mount.rm_fstab"](name, device, config)
                if out is not True:
                    ret["result"] = False
                    ret["comment"] += ". Failed to persist purge"
                else:
                    ret["comment"] += ". Removed target from fstab"
                    ret["changes"]["persist"] = "purged"

    return ret


def mod_watch(name, user=None, **kwargs):
    """
    The mounted watcher, called to invoke the watch command.

    .. note::
        This state exists to support special handling of the ``watch``
        :ref:`requisite <requisites>`. It should not be called directly.

        Parameters for this function should be set by the state being triggered.

    name
        The name of the mount point

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if kwargs["sfun"] == "mounted":
        out = __salt__["mount.remount"](
            name, kwargs["device"], False, kwargs["fstype"], kwargs["opts"], user=user
        )
        if out:
            ret["comment"] = "{0} remounted".format(name)
        else:
            ret["result"] = False
            ret["comment"] = "{0} failed to remount: {1}".format(name, out)
    else:
        ret["comment"] = "Watch not supported in {0} at this time".format(
            kwargs["sfun"]
        )
    return ret


def _convert_to(maybe_device, convert_to):
    """
    Convert a device name, UUID or LABEL to a device name, UUID or
    LABEL.

    Return the fs_spec required for fstab.

    """

    # Fast path. If we already have the information required, we can
    # save one blkid call
    if (
        not convert_to
        or (convert_to == "device" and maybe_device.startswith("/"))
        or maybe_device.startswith("{}=".format(convert_to.upper()))
    ):
        return maybe_device

    # Get the device information
    if maybe_device.startswith("/"):
        blkid = __salt__["disk.blkid"](maybe_device)
    else:
        blkid = __salt__["disk.blkid"](token=maybe_device)

    result = None
    if len(blkid) == 1:
        if convert_to == "device":
            result = list(blkid.keys())[0]
        else:
            key = convert_to.upper()
            result = "{}={}".format(key, list(blkid.values())[0][key])

    return result


def fstab_present(
    name,
    fs_file,
    fs_vfstype,
    fs_mntops="defaults",
    fs_freq=0,
    fs_passno=0,
    mount_by=None,
    config="/etc/fstab",
    mount=True,
    match_on="auto",
    not_change=False,
):
    """Makes sure that a fstab mount point is pressent.

    name
        The name of block device. Can be any valid fs_spec value.

    fs_file
        Mount point (target) for the filesystem.

    fs_vfstype
        The type of the filesystem (e.g. ext4, xfs, btrfs, ...)

    fs_mntops
        The mount options associated with the filesystem. Default is
        ``defaults``.

    fs_freq
        Field is used by dump to determine which fs need to be
        dumped. Default is ``0``

    fs_passno
        Field is used by fsck to determine the order in which
        filesystem checks are done at boot time. Default is ``0``

    mount_by
        Select the final value for fs_spec. Can be [``None``,
        ``device``, ``label``, ``uuid``, ``partlabel``,
        ``partuuid``]. If ``None``, the value for fs_spect will be the
        parameter ``name``, in other case will search the correct
        value based on the device name. For example, for ``uuid``, the
        value for fs_spec will be of type 'UUID=xxx' instead of the
        device name set in ``name``.

    config
        Place where the fstab file lives. Default is ``/etc/fstab``

    mount
        Set if the mount should be mounted immediately. Default is
        ``True``

    match_on
        A name or list of fstab properties on which this state should
        be applied.  Default is ``auto``, a special value indicating
        to guess based on fstype.  In general, ``auto`` matches on
        name for recognized special devices and device otherwise.

    not_change
        By default, if the entry is found in the fstab file but is
        different from the expected content (like different options),
        the entry will be replaced with the correct content. If this
        parameter is set to ``True`` and the line is found, the
        original content will be preserved.

    """
    ret = {
        "name": name,
        "result": False,
        "changes": {},
        "comment": [],
    }

    # Adjust fs_mntops based on the OS
    if fs_mntops == "defaults":
        if __grains__["os"] in ["MacOS", "Darwin"]:
            fs_mntops = "noowners"
        elif __grains__["os"] == "AIX":
            fs_mntops = ""

    # Adjust the config file based on the OS
    if config == "/etc/fstab":
        if __grains__["os"] in ["MacOS", "Darwin"]:
            config = "/etc/auto_salt"
        elif __grains__["os"] == "AIX":
            config = "/etc/filesystems"

    if not fs_file == "/":
        fs_file = fs_file.rstrip("/")

    fs_spec = _convert_to(name, mount_by)

    # Validate that the device is valid after the conversion
    if not fs_spec:
        msg = "Device {} cannot be converted to {}"
        ret["comment"].append(msg.format(name, mount_by))
        return ret

    if __opts__["test"]:
        if __grains__["os"] in ["MacOS", "Darwin"]:
            out = __salt__["mount.set_automaster"](
                name=fs_file,
                device=fs_spec,
                fstype=fs_vfstype,
                opts=fs_mntops,
                config=config,
                test=True,
                not_change=not_change,
            )
        elif __grains__["os"] == "AIX":
            out = __salt__["mount.set_filesystems"](
                name=fs_file,
                device=fs_spec,
                fstype=fs_vfstype,
                opts=fs_mntops,
                mount=mount,
                config=config,
                test=True,
                match_on=match_on,
                not_change=not_change,
            )
        else:
            out = __salt__["mount.set_fstab"](
                name=fs_file,
                device=fs_spec,
                fstype=fs_vfstype,
                opts=fs_mntops,
                dump=fs_freq,
                pass_num=fs_passno,
                config=config,
                test=True,
                match_on=match_on,
                not_change=not_change,
            )
        ret["result"] = None
        if out == "present":
            msg = "{} entry is already in {}."
            ret["comment"].append(msg.format(fs_file, config))
        elif out == "new":
            msg = "{} entry will be written in {}."
            ret["comment"].append(msg.format(fs_file, config))
        elif out == "change":
            msg = "{} entry will be updated in {}."
            ret["comment"].append(msg.format(fs_file, config))
        else:
            ret["result"] = False
            msg = "{} entry cannot be created in {}: {}."
            ret["comment"].append(msg.format(fs_file, config, out))
        return ret

    if __grains__["os"] in ["MacOS", "Darwin"]:
        out = __salt__["mount.set_automaster"](
            name=fs_file,
            device=fs_spec,
            fstype=fs_vfstype,
            opts=fs_mntops,
            config=config,
            not_change=not_change,
        )
    elif __grains__["os"] == "AIX":
        out = __salt__["mount.set_filesystems"](
            name=fs_file,
            device=fs_spec,
            fstype=fs_vfstype,
            opts=fs_mntops,
            mount=mount,
            config=config,
            match_on=match_on,
            not_change=not_change,
        )
    else:
        out = __salt__["mount.set_fstab"](
            name=fs_file,
            device=fs_spec,
            fstype=fs_vfstype,
            opts=fs_mntops,
            dump=fs_freq,
            pass_num=fs_passno,
            config=config,
            match_on=match_on,
            not_change=not_change,
        )

    ret["result"] = True
    if out == "present":
        msg = "{} entry was already in {}."
        ret["comment"].append(msg.format(fs_file, config))
    elif out == "new":
        ret["changes"]["persist"] = out
        msg = "{} entry added in {}."
        ret["comment"].append(msg.format(fs_file, config))
    elif out == "change":
        ret["changes"]["persist"] = out
        msg = "{} entry updated in {}."
        ret["comment"].append(msg.format(fs_file, config))
    else:
        ret["result"] = False
        msg = "{} entry cannot be changed in {}: {}."
        ret["comment"].append(msg.format(fs_file, config, out))

    return ret


def fstab_absent(name, fs_file, mount_by=None, config="/etc/fstab"):
    """
    Makes sure that a fstab mount point is absent.

    name
        The name of block device. Can be any valid fs_spec value.

    fs_file
        Mount point (target) for the filesystem.

    mount_by
        Select the final value for fs_spec. Can be [``None``,
        ``device``, ``label``, ``uuid``, ``partlabel``,
        ``partuuid``]. If ``None``, the value for fs_spect will be the
        parameter ``name``, in other case will search the correct
        value based on the device name. For example, for ``uuid``, the
        value for fs_spec will be of type 'UUID=xxx' instead of the
        device name set in ``name``.

    config
        Place where the fstab file lives

    """
    ret = {
        "name": name,
        "result": False,
        "changes": {},
        "comment": [],
    }

    # Adjust the config file based on the OS
    if config == "/etc/fstab":
        if __grains__["os"] in ["MacOS", "Darwin"]:
            config = "/etc/auto_salt"
        elif __grains__["os"] == "AIX":
            config = "/etc/filesystems"

    if not fs_file == "/":
        fs_file = fs_file.rstrip("/")

    fs_spec = _convert_to(name, mount_by)

    if __grains__["os"] in ["MacOS", "Darwin"]:
        fstab_data = __salt__["mount.automaster"](config)
    elif __grains__["os"] == "AIX":
        fstab_data = __salt__["mount.filesystems"](config)
    else:
        fstab_data = __salt__["mount.fstab"](config)

    if __opts__["test"]:
        ret["result"] = None
        if fs_file not in fstab_data:
            msg = "{} entry is already missing in {}."
            ret["comment"].append(msg.format(fs_file, config))
        else:
            msg = "{} entry will be removed from {}."
            ret["comment"].append(msg.format(fs_file, config))
        return ret

    if fs_file in fstab_data:
        if __grains__["os"] in ["MacOS", "Darwin"]:
            out = __salt__["mount.rm_automaster"](
                name=fs_file, device=fs_spec, config=config
            )
        elif __grains__["os"] == "AIX":
            out = __salt__["mount.rm_filesystems"](
                name=fs_file, device=fs_spec, config=config
            )
        else:
            out = __salt__["mount.rm_fstab"](
                name=fs_file, device=fs_spec, config=config
            )

        if out is not True:
            ret["result"] = False
            msg = "{} entry failed when removing from {}."
            ret["comment"].append(msg.format(fs_file, config))
        else:
            ret["result"] = True
            ret["changes"]["persist"] = "removed"
            msg = "{} entry removed from {}."
            ret["comment"].append(msg.format(fs_file, config))
    else:
        ret["result"] = True
        msg = "{} entry is already missing in {}."
        ret["comment"].append(msg.format(fs_file, config))

    return ret
