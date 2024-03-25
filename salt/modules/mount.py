"""
Salt module to manage Unix mounts and the fstab file
"""

import logging
import os
import re

import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.mount
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, CommandNotFoundError
from salt.utils.odict import OrderedDict

# Set up logger
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "mount"


def __virtual__():
    """
    Only load on POSIX-like systems
    """
    # Disable on Windows, a specific file module exists:
    if salt.utils.platform.is_windows():
        return (False, "The mount module cannot be loaded: not a POSIX-like system.")
    return True


def _list_mounts():
    ret = {}
    if __grains__["os"] in ["MacOS", "Darwin"]:
        mounts = __salt__["cmd.run_stdout"]("mount")
    else:
        mounts = __salt__["cmd.run_stdout"]("mount -l")

    for line in mounts.split("\n"):
        comps = re.sub(r"\s+", " ", line).split()
        if len(comps) >= 3:
            ret[comps[2]] = comps[0]
    return ret


def _active_mountinfo(ret):
    _list = _list_mounts()
    filename = "/proc/self/mountinfo"
    if not os.access(filename, os.R_OK):
        msg = "File not readable {0}"
        raise CommandExecutionError(msg.format(filename))

    if "disk.blkid" not in __context__:
        __context__["disk.blkid"] = __salt__["disk.blkid"]()
    blkid_info = __context__["disk.blkid"]

    with salt.utils.files.fopen(filename) as ifile:
        for line in ifile:
            comps = salt.utils.stringutils.to_unicode(line).split()
            device = comps[2].split(":")
            # each line can have any number of
            # optional parameters, we use the
            # location of the separator field to
            # determine the location of the elements
            # after it.
            _sep = comps.index("-")
            device_name = comps[_sep + 2]
            device_uuid = None
            device_label = None
            if device_name:
                device_uuid = blkid_info.get(device_name, {}).get("UUID")
                device_uuid = device_uuid and device_uuid.lower()
                device_label = blkid_info.get(device_name, {}).get("LABEL")
            ret[comps[4]] = {
                "mountid": comps[0],
                "parentid": comps[1],
                "major": device[0],
                "minor": device[1],
                "root": comps[3],
                "opts": _resolve_user_group_names(comps[5].split(",")),
                "fstype": comps[_sep + 1],
                "device": device_name.replace("\\040", "\\ "),
                "alt_device": _list.get(comps[4], None),
                "superopts": _resolve_user_group_names(comps[_sep + 3].split(",")),
                "device_uuid": device_uuid,
                "device_label": device_label,
            }
    return ret


def _active_mounts(ret):
    """
    List active mounts on Linux systems
    """
    _list = _list_mounts()
    filename = "/proc/self/mounts"
    if not os.access(filename, os.R_OK):
        msg = "File not readable {0}"
        raise CommandExecutionError(msg.format(filename))

    with salt.utils.files.fopen(filename) as ifile:
        for line in ifile:
            comps = salt.utils.stringutils.to_unicode(line).split()
            ret[comps[1]] = {
                "device": comps[0],
                "alt_device": _list.get(comps[1], None),
                "fstype": comps[2],
                "opts": _resolve_user_group_names(comps[3].split(",")),
            }
    return ret


def _active_mounts_aix(ret):
    """
    List active mounts on AIX systems
    """
    for line in __salt__["cmd.run_stdout"]("mount -p").split("\n"):
        comps = re.sub(r"\s+", " ", line).split()
        if comps:
            if comps[0] == "node" or comps[0] == "--------":
                continue
            comps_len = len(comps)
            if line.startswith((" ", "\t")):
                curr_opts = (
                    _resolve_user_group_names(comps[6].split(","))
                    if 7 == comps_len
                    else []
                )
                if curr_opts:
                    ret[comps[1]] = {
                        "device": comps[0],
                        "fstype": comps[2],
                        "opts": curr_opts,
                    }
                else:
                    ret[comps[1]] = {"device": comps[0], "fstype": comps[2]}
            else:
                curr_opts = (
                    _resolve_user_group_names(comps[7].split(","))
                    if 8 == comps_len
                    else []
                )
                if curr_opts:
                    ret[comps[2]] = {
                        "node": comps[0],
                        "device": comps[1],
                        "fstype": comps[3],
                        "opts": curr_opts,
                    }
                else:
                    ret[comps[2]] = {
                        "node": comps[0],
                        "device": comps[1],
                        "fstype": comps[3],
                    }
    return ret


def _active_mounts_freebsd(ret):
    """
    List active mounts on FreeBSD systems
    """
    for line in __salt__["cmd.run_stdout"]("mount -p").split("\n"):
        comps = re.sub(r"\s+", " ", line).split()
        ret[comps[1]] = {
            "device": comps[0],
            "fstype": comps[2],
            "opts": _resolve_user_group_names(comps[3].split(",")),
        }
    return ret


def _active_mounts_solaris(ret):
    """
    List active mounts on Solaris systems
    """
    for line in __salt__["cmd.run_stdout"]("mount -v").split("\n"):
        comps = re.sub(r"\s+", " ", line).split()
        ret[comps[2]] = {
            "device": comps[0],
            "fstype": comps[4],
            "opts": _resolve_user_group_names(comps[5].split("/")),
        }
    return ret


def _active_mounts_openbsd(ret):
    """
    List active mounts on OpenBSD systems
    """
    for line in __salt__["cmd.run_stdout"]("mount -v").split("\n"):
        comps = re.sub(r"\s+", " ", line).split()
        parens = re.findall(r"\((.*?)\)", line, re.DOTALL)
        if len(parens) > 1:
            nod = __salt__["cmd.run_stdout"](f"ls -l {comps[0]}")
            nod = " ".join(nod.split()).split(" ")
            ret[comps[3]] = {
                "device": comps[0],
                "fstype": comps[5],
                "opts": _resolve_user_group_names(parens[1].split(", ")),
                "major": str(nod[4].strip(",")),
                "minor": str(nod[5]),
                "device_uuid": parens[0],
            }
        else:
            ret[comps[2]] = {
                "device": comps[0],
                "fstype": comps[4],
                "opts": _resolve_user_group_names(parens[0].split(", ")),
            }
    return ret


def _active_mounts_darwin(ret):
    """
    List active mounts on Mac OS systems
    """
    for line in __salt__["cmd.run_stdout"]("mount").split("\n"):
        comps = re.sub(r"\s+", " ", line).split()
        parens = re.findall(r"\((.*?)\)", line, re.DOTALL)[0].split(", ")
        ret[comps[2]] = {
            "device": comps[0],
            "fstype": parens[0],
            "opts": _resolve_user_group_names(parens[1:]),
        }
    return ret


def _resolve_user_group_names(opts):
    """
    Resolve user and group names in related opts
    """
    name_id_opts = {"uid": "user.info", "gid": "group.info"}
    for ind, opt in enumerate(opts):
        if opt.split("=")[0] in name_id_opts:
            _givenid = opt.split("=")[1]
            _param = opt.split("=")[0]
            _id = _givenid
            if not re.match("[0-9]+$", _givenid):
                _info = __salt__[name_id_opts[_param]](_givenid)
                if _info and _param in _info:
                    _id = _info[_param]
            opts[ind] = _param + "=" + str(_id)
        opts[ind] = opts[ind].replace("\\040", "\\ ")
    return opts


def active(extended=False):
    """
    List the active mounts.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.active
    """
    ret = {}
    if __grains__["os"] == "FreeBSD":
        _active_mounts_freebsd(ret)
    elif "AIX" in __grains__["kernel"]:
        _active_mounts_aix(ret)
    elif __grains__["kernel"] == "SunOS":
        _active_mounts_solaris(ret)
    elif __grains__["os"] == "OpenBSD":
        _active_mounts_openbsd(ret)
    elif __grains__["os"] in ["MacOS", "Darwin"]:
        _active_mounts_darwin(ret)
    else:
        if extended:
            try:
                _active_mountinfo(ret)
            except CommandExecutionError:
                _active_mounts(ret)
        else:
            _active_mounts(ret)
    return ret


class _fstab_entry:
    """
    Utility class for manipulating fstab entries. Primarily we're parsing,
    formatting, and comparing lines. Parsing emits dicts expected from
    fstab() or raises a ValueError.

    Note: We'll probably want to use os.normpath and os.normcase on 'name'
    """

    class ParseError(ValueError):
        """
        Error raised when a line isn't parsible as an fstab entry
        """

    fstab_keys = ("device", "name", "fstype", "opts", "dump", "pass_num")

    # preserve data format
    compatibility_keys = ("device", "name", "fstype", "opts", "dump", "pass")

    fstab_format = "{device}\t\t{name}\t{fstype}\t{opts}\t{dump} {pass_num}\n"

    @classmethod
    def dict_from_line(cls, line, keys=fstab_keys):
        if len(keys) != 6:
            raise ValueError(f"Invalid key array: {keys}")
        if line.startswith("#"):
            raise cls.ParseError("Comment!")

        comps = line.split()
        if len(comps) < 4 or len(comps) > 6:
            raise cls.ParseError("Invalid Entry!")

        comps.extend(["0"] * (len(keys) - len(comps)))

        return dict(zip(keys, comps))

    @classmethod
    def from_line(cls, *args, **kwargs):
        return cls(**cls.dict_from_line(*args, **kwargs))

    @classmethod
    def dict_to_line(cls, entry):
        return cls.fstab_format.format(**entry)

    def __str__(self):
        """
        String value, only works for full repr
        """
        return self.dict_to_line(self.criteria)

    def __repr__(self):
        """
        Always works
        """
        return repr(self.criteria)

    def pick(self, keys):
        """
        Returns an instance with just those keys
        """
        subset = {key: self.criteria[key] for key in keys}
        return self.__class__(**subset)

    def __init__(self, **criteria):
        """
        Store non-empty, non-null values to use as filter
        """
        items = [
            key_value for key_value in criteria.items() if key_value[1] is not None
        ]
        items = [(key_value1[0], str(key_value1[1])) for key_value1 in items]
        self.criteria = dict(items)

    @staticmethod
    def norm_path(path):
        """
        Resolve equivalent paths equivalently
        """
        return os.path.normcase(os.path.normpath(path))

    def match(self, line):
        """
        Compare potentially partial criteria against line
        """
        entry = self.dict_from_line(line)
        for key, value in self.criteria.items():
            if key == "opts":
                ex_opts = sorted(entry.get(key, "").split(","))
                cr_opts = sorted(value.split(","))
                if ex_opts != cr_opts:
                    return False
            elif entry[key] != value:
                return False
        return True


class _vfstab_entry:
    """
    Utility class for manipulating vfstab entries. Primarily we're parsing,
    formatting, and comparing lines. Parsing emits dicts expected from
    fstab() or raises a ValueError.

    Note: We'll probably want to use os.normpath and os.normcase on 'name'
    Note: This parses vfstab entries on Solaris like systems

    #device     device      mount       FS  fsck    mount   mount
    #to mount   to fsck     point       type    pass    at boot options
    #
    /devices    -   /devices            devfs    -   no     -
    """

    class ParseError(ValueError):
        """Error raised when a line isn't parsible as an fstab entry"""

    vfstab_keys = (
        "device",
        "device_fsck",
        "name",
        "fstype",
        "pass_fsck",
        "mount_at_boot",
        "opts",
    )
    # NOTE: weird formatting to match default spacing on Solaris
    vfstab_format = (
        "{device:<11} {device_fsck:<3} {name:<19} {fstype:<8} {pass_fsck:<3}"
        " {mount_at_boot:<6} {opts}\n"
    )

    @classmethod
    def dict_from_line(cls, line):
        if line.startswith("#"):
            raise cls.ParseError("Comment!")

        comps = line.split()
        if len(comps) != 7:
            raise cls.ParseError("Invalid Entry!")

        return dict(zip(cls.vfstab_keys, comps))

    @classmethod
    def from_line(cls, *args, **kwargs):
        return cls(**cls.dict_from_line(*args, **kwargs))

    @classmethod
    def dict_to_line(cls, entry):
        return cls.vfstab_format.format(**entry)

    def __str__(self):
        """
        String value, only works for full repr
        """
        return self.dict_to_line(self.criteria)

    def __repr__(self):
        """
        Always works
        """
        return repr(self.criteria)

    def pick(self, keys):
        """
        Returns an instance with just those keys
        """
        subset = {key: self.criteria[key] for key in keys}
        return self.__class__(**subset)

    def __init__(self, **criteria):
        """
        Store non-empty, non-null values to use as filter
        """
        items = [
            key_value for key_value in criteria.items() if key_value[1] is not None
        ]
        items = [(key_value1[0], str(key_value1[1])) for key_value1 in items]
        self.criteria = dict(items)

    @staticmethod
    def norm_path(path):
        """
        Resolve equivalent paths equivalently
        """
        return os.path.normcase(os.path.normpath(path))

    def match(self, line):
        """
        Compare potentially partial criteria against line
        """
        entry = self.dict_from_line(line)
        for key, value in self.criteria.items():
            if key == "opts":
                ex_opts = sorted(entry.get(key, "").split(","))
                cr_opts = sorted(value.split(","))
                if ex_opts != cr_opts:
                    return False
            elif entry[key] != value:
                return False
        return True


class _FileSystemsEntry:
    """
    Utility class for manipulating filesystem entries. Primarily we're parsing,
    formatting, and comparing lines. Parsing emits dicts expected from
    fstab() or raises a ValueError.

    Note: We'll probably want to use os.normpath and os.normcase on 'name'
    """

    class ParseError(ValueError):
        """
        Error raised when a line isn't parsible as an fstab entry
        """

    filesystems_keys = ("device", "name", "fstype", "vfstype", "opts", "mount")

    # preserve data format of filesystems
    compatibility_keys = (
        "dev",
        "dev",
        "name",
        "fstype",
        "vfstype",
        "opts",
        "mount",
        "type",
        "vfs",
        "account",
        "boot",
        "check",
        "free",
        "nodename",
        "quota",
        "size",
        "vol",
        "log",
    )

    @classmethod
    def dict_from_lines(cls, lines, keys=filesystems_keys):
        if len(lines) < 2:
            raise ValueError(f"Invalid number of lines: {lines}")
        if not keys:
            # if empty force default filesystems_keys
            keys = _FileSystemsEntry.filesystems_keys
        elif len(keys) < 6:
            raise ValueError(f"Invalid key name array: {keys}")

        blk_lines = lines
        orddict = OrderedDict()
        orddict["name"] = blk_lines[0].split(":")[0].strip()
        blk_lines.pop(0)
        for line in blk_lines:
            if line.startswith("#"):
                raise cls.ParseError("Comment!")

            comps = line.split("= ")
            if len(comps) != 2:
                raise cls.ParseError("Invalid Entry!")

            key_name = comps[0].strip()
            if key_name in keys:
                orddict[key_name] = comps[1].strip()
            else:
                raise ValueError(f"Invalid name for use in filesystems: {key_name}")

        return orddict

    @classmethod
    def dict_from_cmd_line(cls, ipargs, keys):
        cmdln_dict = ipargs
        if keys:
            for key, value in keys.items():
                # ignore unknown or local scope keys
                if key.startswith("__"):
                    continue
                if key in _FileSystemsEntry.compatibility_keys:
                    cmdln_dict[key] = value

        return cmdln_dict

    @classmethod
    def from_line(cls, *args, **kwargs):
        return cls(**cls.dict_from_cmd_line(*args, **kwargs))

    @classmethod
    def dict_to_lines(cls, fsys_dict_entry):
        entry = fsys_dict_entry
        strg_out = entry["name"] + ":" + os.linesep
        for k, v in entry.items():
            if "name" not in k:
                strg_out += f"\t{k}\t\t= {v}" + os.linesep
        strg_out += os.linesep
        return str(strg_out)

    @classmethod
    def dict_to_list_lines(cls, fsys_dict_entry):
        entry = fsys_dict_entry
        list_out = []
        list_out.append(str(entry["name"] + ":" + os.linesep))
        for k, v in entry.items():
            if "name" not in k:
                list_out.append(str(f"\t{k}\t\t= {v}" + os.linesep))
        list_out.append(str(os.linesep))
        return list_out

    def dict_from_entry(self):
        ret = OrderedDict()
        ret[self.criteria["name"]] = self.criteria
        return ret

    def __str__(self):
        """
        String value, only works for full repr
        """
        return self.dict_to_lines(self.criteria)

    def __repr__(self):
        """
        Always works
        """
        return repr(self.criteria)

    def pick(self, keys):
        """
        Returns an instance with just those keys
        """
        subset = {key: self.criteria[key] for key in keys}
        return self.__class__(**subset)

    def __init__(self, **criteria):
        """
        Store non-empty, non-null values to use as filter
        """
        items = [
            key_value for key_value in criteria.items() if key_value[1] is not None
        ]
        items = [(key_value1[0], str(key_value1[1])) for key_value1 in items]
        self.criteria = OrderedDict(items)

    @staticmethod
    def norm_path(path):
        """
        Resolve equivalent paths equivalently
        """
        return os.path.normcase(os.path.normpath(path))

    def match(self, fsys_view):
        """
        Compare potentially partial criteria against built filesystems entry dictionary
        """
        evalue_dict = fsys_view[1]
        for key, value in self.criteria.items():
            if key in evalue_dict:
                if key == "opts":
                    ex_opts = sorted(evalue_dict.get(key, "").split(","))
                    cr_opts = sorted(value.split(","))
                    if ex_opts != cr_opts:
                        return False
                elif evalue_dict[key] != value:
                    return False
            else:
                return False
        return True

    def __getitem__(self, key):
        """
        Return value for input key
        """
        return self.criteria[key]


def fstab(config="/etc/fstab"):
    """
    .. versionchanged:: 2016.3.2

    List the contents of the fstab

    CLI Example:

    .. code-block:: bash

        salt '*' mount.fstab
    """
    ret = {}
    if not os.path.isfile(config):
        return ret
    with salt.utils.files.fopen(config) as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line)
            try:
                if __grains__["kernel"] == "SunOS":
                    # Note: comments use in default vfstab file!
                    if line[0] == "#":
                        continue
                    entry = _vfstab_entry.dict_from_line(line)
                else:
                    entry = _fstab_entry.dict_from_line(
                        line, _fstab_entry.compatibility_keys
                    )

                entry["opts"] = entry["opts"].split(",")
                while entry["name"] in ret:
                    entry["name"] += "_"

                ret[entry.pop("name")] = entry
            except _fstab_entry.ParseError:
                pass
            except _vfstab_entry.ParseError:
                pass

    return ret


def vfstab(config="/etc/vfstab"):
    """
    .. versionadded:: 2016.3.2

    List the contents of the vfstab

    CLI Example:

    .. code-block:: bash

        salt '*' mount.vfstab
    """
    # NOTE: vfstab is a wrapper for fstab
    return fstab(config)


def rm_fstab(name, device, config="/etc/fstab"):
    """
    .. versionchanged:: 2016.3.2

    Remove the mount point from the fstab

    CLI Example:

    .. code-block:: bash

        salt '*' mount.rm_fstab /mnt/foo /dev/sdg
    """
    modified = False

    if __grains__["kernel"] == "SunOS":
        criteria = _vfstab_entry(name=name, device=device)
    else:
        criteria = _fstab_entry(name=name, device=device)

    lines = []
    try:
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                try:
                    if criteria.match(line):
                        modified = True
                    else:
                        lines.append(line)

                except _fstab_entry.ParseError:
                    lines.append(line)
                except _vfstab_entry.ParseError:
                    lines.append(line)

    except OSError as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    if modified:
        try:
            with salt.utils.files.fopen(config, "wb") as ofile:
                ofile.writelines(salt.utils.data.encode(lines))
        except OSError as exc:
            msg = "Couldn't write to {0}: {1}"
            raise CommandExecutionError(msg.format(config, exc))

    # Note: not clear why we always return 'True'
    # --just copying previous behavior at this point...
    return True


def rm_vfstab(name, device, config="/etc/vfstab"):
    """
    .. versionadded:: 2016.3.2

    Remove the mount point from the vfstab

    CLI Example:

    .. code-block:: bash

        salt '*' mount.rm_vfstab /mnt/foo /device/c0t0d0p0
    """
    ## NOTE: rm_vfstab is a wrapper for rm_fstab
    return rm_fstab(name, device, config)


def set_fstab(
    name,
    device,
    fstype,
    opts="defaults",
    dump=0,
    pass_num=0,
    config="/etc/fstab",
    test=False,
    match_on="auto",
    not_change=False,
    **kwargs,
):
    """
    Verify that this mount is represented in the fstab, change the mount
    to match the data passed, or add the mount if it is not present.

    If the entry is found via `match_on` and `not_change` is True, the
    current line will be preserved.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.set_fstab /mnt/foo /dev/sdz1 ext4
    """

    # Fix the opts type if it is a list
    if isinstance(opts, list):
        opts = ",".join(opts)

    # preserve arguments for updating
    entry_args = {
        "name": name,
        "device": device.replace("\\ ", "\\040"),
        "fstype": fstype,
        "opts": opts.replace("\\ ", "\\040"),
        "dump": dump,
        "pass_num": pass_num,
    }

    lines = []
    ret = None

    # Transform match_on into list--items will be checked later
    if isinstance(match_on, list):
        pass
    elif not isinstance(match_on, str):
        msg = "match_on must be a string or list of strings"
        raise CommandExecutionError(msg)
    elif match_on == "auto":
        # Try to guess right criteria for auto....
        # NOTE: missing some special fstypes here
        specialFSes = frozenset(
            [
                "none",
                "tmpfs",
                "sysfs",
                "proc",
                "fusectl",
                "debugfs",
                "securityfs",
                "devtmpfs",
                "cgroup",
                "nfs",
                "nfs4",
                "glusterfs",
                "btrfs",
            ]
        )

        if fstype in specialFSes:
            match_on = ["name"]
        else:
            match_on = ["device"]
    else:
        match_on = [match_on]

    # generate entry and criteria objects, handle invalid keys in match_on
    entry = _fstab_entry(**entry_args)
    try:
        criteria = entry.pick(match_on)

    except KeyError:

        def filterFn(key):
            return key not in _fstab_entry.fstab_keys

        invalid_keys = filter(filterFn, match_on)

        msg = f'Unrecognized keys in match_on: "{invalid_keys}"'
        raise CommandExecutionError(msg)

    # parse file, use ret to cache status
    if not os.path.isfile(config):
        raise CommandExecutionError(f'Bad config file "{config}"')

    try:
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                try:
                    if criteria.match(line):
                        # Note: If ret isn't None here,
                        # we've matched multiple lines
                        ret = "present"
                        if entry.match(line) or not_change:
                            lines.append(line)
                        else:
                            ret = "change"
                            lines.append(str(entry))
                    else:
                        lines.append(line)

                except _fstab_entry.ParseError:
                    lines.append(line)

    except OSError as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    # add line if not present or changed
    if ret is None:
        lines.append(str(entry))
        ret = "new"

    if ret != "present":  # ret in ['new', 'change']:
        if not salt.utils.args.test_mode(test=test, **kwargs):
            try:
                with salt.utils.files.fopen(config, "wb") as ofile:
                    # The line was changed, commit it!
                    ofile.writelines(salt.utils.data.encode(lines))
            except OSError:
                msg = "File not writable {0}"
                raise CommandExecutionError(msg.format(config))

    return ret


def set_vfstab(
    name,
    device,
    fstype,
    opts="-",
    device_fsck="-",
    pass_fsck="-",
    mount_at_boot="yes",
    config="/etc/vfstab",
    test=False,
    match_on="auto",
    not_change=False,
    **kwargs,
):
    """
    .. versionadded:: 2016.3.2

    Verify that this mount is represented in the fstab, change the mount
    to match the data passed, or add the mount if it is not present.

    If the entry is found via `match_on` and `not_change` is True, the
    current line will be preserved.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.set_vfstab /mnt/foo /device/c0t0d0p0 ufs
    """

    # Fix the opts type if it is a list
    if isinstance(opts, list):
        opts = ",".join(opts)

    # Map unknown values for mount_at_boot to no
    if mount_at_boot != "yes":
        mount_at_boot = "no"

    # preserve arguments for updating
    entry_args = {
        "name": name,
        "device": device,
        "fstype": fstype,
        "opts": opts,
        "device_fsck": device_fsck,
        "pass_fsck": pass_fsck,
        "mount_at_boot": mount_at_boot,
    }

    lines = []
    ret = None

    # Transform match_on into list--items will be checked later
    if isinstance(match_on, list):
        pass
    elif not isinstance(match_on, str):
        msg = "match_on must be a string or list of strings"
        raise CommandExecutionError(msg)
    elif match_on == "auto":
        # Try to guess right criteria for auto....
        # NOTE: missing some special fstypes here
        specialFSes = frozenset(
            ["devfs", "proc", "ctfs", "objfs", "sharefs", "fs", "tmpfs"]
        )

        if fstype in specialFSes:
            match_on = ["name"]
        else:
            match_on = ["device"]
    else:
        match_on = [match_on]

    # generate entry and criteria objects, handle invalid keys in match_on
    entry = _vfstab_entry(**entry_args)
    try:
        criteria = entry.pick(match_on)

    except KeyError:

        def filterFn(key):
            return key not in _vfstab_entry.vfstab_keys

        invalid_keys = filter(filterFn, match_on)

        msg = f'Unrecognized keys in match_on: "{invalid_keys}"'
        raise CommandExecutionError(msg)

    # parse file, use ret to cache status
    if not os.path.isfile(config):
        raise CommandExecutionError(f'Bad config file "{config}"')

    try:
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                try:
                    if criteria.match(line):
                        # Note: If ret isn't None here,
                        # we've matched multiple lines
                        ret = "present"
                        if entry.match(line) or not_change:
                            lines.append(line)
                        else:
                            ret = "change"
                            lines.append(str(entry))
                    else:
                        lines.append(line)

                except _vfstab_entry.ParseError:
                    lines.append(line)

    except OSError as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    # add line if not present or changed
    if ret is None:
        lines.append(str(entry))
        ret = "new"

    if ret != "present":  # ret in ['new', 'change']:
        if not salt.utils.args.test_mode(test=test, **kwargs):
            try:
                with salt.utils.files.fopen(config, "wb") as ofile:
                    # The line was changed, commit it!
                    ofile.writelines(salt.utils.data.encode(lines))
            except OSError:
                msg = "File not writable {0}"
                raise CommandExecutionError(msg.format(config))

    return ret


def rm_automaster(name, device, config="/etc/auto_salt"):
    """
    Remove the mount point from the auto_master

    CLI Example:

    .. code-block:: bash

        salt '*' mount.rm_automaster /mnt/foo /dev/sdg
    """
    contents = automaster(config)
    if name not in contents:
        return True
    # The entry is present, get rid of it
    lines = []
    try:
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                if line.startswith("#"):
                    # Commented
                    lines.append(line)
                    continue
                if not line.strip():
                    # Blank line
                    lines.append(line)
                    continue
                comps = line.split()
                if len(comps) != 3:
                    # Invalid entry
                    lines.append(line)
                    continue

                comps = line.split()
                prefix = "/.."
                name_chk = comps[0].replace(prefix, "")
                device_fmt = comps[2].split(":")

                if device:
                    if name_chk == name and device_fmt[1] == device:
                        continue
                else:
                    if name_chk == name:
                        continue
                lines.append(line)
    except OSError as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    try:
        with salt.utils.files.fopen(config, "wb") as ofile:
            ofile.writelines(salt.utils.data.encode(lines))
    except OSError as exc:
        msg = "Couldn't write to {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    # Update automount
    __salt__["cmd.run"]("automount -cv")
    return True


def set_automaster(
    name,
    device,
    fstype,
    opts="",
    config="/etc/auto_salt",
    test=False,
    not_change=False,
    **kwargs,
):
    """
    Verify that this mount is represented in the auto_salt, change the mount
    to match the data passed, or add the mount if it is not present.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.set_automaster /mnt/foo /dev/sdz1 ext4
    """
    # Fix the opts type if it is a list
    if isinstance(opts, list):
        opts = ",".join(opts)
    lines = []
    change = False
    present = False
    automaster_file = "/etc/auto_master"

    if not os.path.isfile(config):
        __salt__["file.touch"](config)
        __salt__["file.append"](automaster_file, f"/-\t\t\t{config}")

    name = f"/..{name}"
    device_fmt = f"{fstype}:{device}"
    type_opts = f"-fstype={fstype},{opts}"

    if fstype == "smbfs":
        device_fmt = device_fmt.replace(fstype, "")

    try:
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                if line.startswith("#"):
                    # Commented
                    lines.append(line)
                    continue
                if not line.strip():
                    # Blank line
                    lines.append(line)
                    continue
                comps = line.split()
                if len(comps) != 3:
                    # Invalid entry
                    lines.append(line)
                    continue
                if comps[0] == name or comps[2] == device_fmt:
                    present = True
                    if not_change:
                        continue
                    # check to see if there are changes
                    # and fix them if there are any
                    if comps[0] != name:
                        change = True
                        comps[0] = name
                    if comps[1] != type_opts:
                        change = True
                        comps[1] = type_opts
                    if comps[2] != device_fmt:
                        change = True
                        comps[2] = device_fmt
                    if change:
                        log.debug(
                            "auto_master entry for mount point %s needs to be updated",
                            name,
                        )
                        newline = f"{name}\t{type_opts}\t{device_fmt}\n"
                        lines.append(newline)
                else:
                    lines.append(line)
    except OSError as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, exc))

    if change:
        if not salt.utils.args.test_mode(test=test, **kwargs):
            try:
                with salt.utils.files.fopen(config, "wb") as ofile:
                    # The line was changed, commit it!
                    ofile.writelines(salt.utils.data.encode(lines))
            except OSError:
                msg = "File not writable {0}"
                raise CommandExecutionError(msg.format(config))

        return "change"

    if not change:
        if present:
            # The right entry is already here
            return "present"
        else:
            if not salt.utils.args.test_mode(test=test, **kwargs):
                # The entry is new, add it to the end of the fstab
                newline = f"{name}\t{type_opts}\t{device_fmt}\n"
                lines.append(newline)
                try:
                    with salt.utils.files.fopen(config, "wb") as ofile:
                        # The line was changed, commit it!
                        ofile.writelines(salt.utils.data.encode(lines))
                except OSError:
                    raise CommandExecutionError(f"File not writable {config}")
    return "new"


def automaster(config="/etc/auto_salt"):
    """
    List the contents of the auto master

    CLI Example:

    .. code-block:: bash

        salt '*' mount.automaster
    """
    ret = {}
    if not os.path.isfile(config):
        return ret
    with salt.utils.files.fopen(config) as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line)
            if line.startswith("#"):
                # Commented
                continue
            if not line.strip():
                # Blank line
                continue
            comps = line.split()
            if len(comps) != 3:
                # Invalid entry
                continue

            prefix = "/.."
            name = comps[0].replace(prefix, "")
            device_fmt = comps[2].split(":")
            opts = comps[1].split(",")

            ret[name] = {"device": device_fmt[1], "fstype": opts[0], "opts": opts[1:]}
    return ret


def mount(
    name, device=False, mkmnt=False, fstype="", opts="defaults", user=None, util="mount"
):
    """
    Mount a device

    CLI Example:

    .. code-block:: bash

        salt '*' mount.mount /mnt/foo /dev/sdz1 True
    """
    if util != "mount":
        # This functionality used to live in img.mount_image
        if util == "guestfs":
            return __salt__["guestfs.mount"](name, root=device)
        elif util == "qemu_nbd":
            mnt = __salt__["qemu_nbd.init"](name, device)
            if not mnt:
                return False
            first = next(iter(mnt.keys()))
            __context__[f"img.mnt_{first}"] = mnt
            return first
        return False

    # Darwin doesn't expect defaults when mounting without other options
    if "defaults" in opts and __grains__["os"] in ["MacOS", "Darwin", "AIX"]:
        opts = None

    if isinstance(opts, str):
        opts = opts.split(",")

    if not os.path.exists(name) and mkmnt:
        __salt__["file.mkdir"](name, user=user)

    args = ""
    if opts is not None:
        lopts = ",".join(opts)
        args = f"-o {lopts}"

    if fstype:
        # use of fstype on AIX differs from typical Linux use of -t
        # functionality AIX uses -v vfsname, -t fstype mounts all with
        # fstype in /etc/filesystems
        if "AIX" in __grains__["os"]:
            args += f" -v {fstype}"
        elif "solaris" in __grains__["os"].lower():
            args += f" -F {fstype}"
        else:
            args += f" -t {fstype}"

    cmd = "mount "
    if device:
        cmd += f"{args} '{device}' '{name}' "
    else:
        cmd += f"'{name}' "
    out = __salt__["cmd.run_all"](cmd, runas=user, python_shell=False)
    if out["retcode"]:
        return out["stderr"]
    return True


def remount(name, device, mkmnt=False, fstype="", opts="defaults", user=None):
    """
    Attempt to remount a device, if the device is not already mounted, mount
    is called

    CLI Example:

    .. code-block:: bash

        salt '*' mount.remount /mnt/foo /dev/sdz1 True
    """
    force_mount = False
    if __grains__["os"] in ["MacOS", "Darwin"]:
        if opts == "defaults":
            opts = "noowners"
        if fstype == "smbfs":
            force_mount = True

    if "AIX" in __grains__["os"]:
        if opts == "defaults":
            opts = []

    if isinstance(opts, str):
        opts = opts.split(",")
    mnts = active()
    if name in mnts:
        # The mount point is mounted, attempt to remount it with the given data
        if "remount" not in opts and __grains__["os"] not in [
            "OpenBSD",
            "MacOS",
            "Darwin",
        ]:
            opts.append("remount")
        if force_mount:
            # We need to force the mount but first we should unmount
            umount(name, device, user=user)
        args = ""
        if opts:
            lopts = ",".join(opts)
            args = f"-o {lopts}"

        if fstype:
            # use of fstype on AIX differs from typical Linux use of
            # -t functionality AIX uses -v vfsname, -t fstype mounts
            # all with fstype in /etc/filesystems
            if "AIX" in __grains__["os"]:
                args += f" -v {fstype}"
            elif "solaris" in __grains__["os"].lower():
                args += f" -F {fstype}"
            else:
                args += f" -t {fstype}"

        if __grains__["os"] not in ["OpenBSD", "MacOS", "Darwin"] or force_mount:
            cmd = f"mount {args} '{device}' '{name}' "
        else:
            cmd = f"mount -u {args} '{device}' '{name}' "
        out = __salt__["cmd.run_all"](cmd, runas=user, python_shell=False)
        if out["retcode"]:
            return out["stderr"]
        return True
    # Mount a filesystem that isn't already
    return mount(name, device, mkmnt, fstype, opts, user=user)


def umount(name, device=None, user=None, util="mount"):
    """
    Attempt to unmount a device by specifying the directory it is mounted on

    CLI Example:

    .. code-block:: bash

        salt '*' mount.umount /mnt/foo

    .. versionadded:: 2015.5.0

    .. code-block:: bash

        salt '*' mount.umount /mnt/foo /dev/xvdc1
    """
    if util == "guestfs":
        __salt__["guestfs.umount"](name, disk=device)
        return
    elif util == "qemu_nbd":
        # This functionality used to live in img.umount_image
        if "qemu_nbd.clear" in __salt__:
            if f"img.mnt_{name}" in __context__:
                __salt__["qemu_nbd.clear"](__context__[f"img.mnt_{name}"])
                return

    mnts = active()
    if name not in mnts:
        return f"{name} does not have anything mounted"

    if not device:
        cmd = f"umount '{name}'"
    else:
        cmd = f"umount '{device}'"
    out = __salt__["cmd.run_all"](cmd, runas=user, python_shell=False)
    if out["retcode"]:
        return out["stderr"]
    return True


def is_fuse_exec(cmd):
    """
    Returns true if the command passed is a fuse mountable application.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.is_fuse_exec sshfs
    """
    cmd_path = salt.utils.path.which(cmd)

    # No point in running ldd on a command that doesn't exist
    if not cmd_path:
        return False
    elif not salt.utils.path.which("ldd"):
        raise CommandNotFoundError("ldd")

    out = __salt__["cmd.run"](f"ldd {cmd_path}", python_shell=False)
    return "libfuse" in out


def swaps():
    """
    Return a dict containing information on active swap

    .. versionchanged:: 2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' mount.swaps
    """
    ret = {}
    if __grains__["kernel"] == "SunOS":
        for line in __salt__["cmd.run_stdout"]("swap -l").splitlines():
            if line.startswith("swapfile"):
                continue
            comps = line.split()
            ret[comps[0]] = {
                "type": "device" if comps[0].startswith(("/dev", "swap")) else "file",
                "size": int(comps[3]),
                "used": (int(comps[3]) - int(comps[4])),
                "priority": "-",
            }
    elif "AIX" in __grains__["kernel"]:
        for line in __salt__["cmd.run_stdout"]("swap -l").splitlines():
            if line.startswith("device"):
                continue
            comps = line.split()

            # AIX uses MB for units
            ret[comps[0]] = {
                "type": "device",
                "size": int(comps[3][:-2]) * 1024,
                "used": (int(comps[3][:-2]) - int(comps[4][:-2])) * 1024,
                "priority": "-",
            }
    elif __grains__["os"] != "OpenBSD":
        with salt.utils.files.fopen("/proc/swaps") as fp_:
            for line in fp_:
                line = salt.utils.stringutils.to_unicode(line)
                if line.startswith("Filename"):
                    continue
                comps = line.split()
                ret[comps[0]] = {
                    "type": comps[1],
                    "size": comps[2],
                    "used": comps[3],
                    "priority": comps[4],
                }
    else:
        for line in __salt__["cmd.run_stdout"]("swapctl -kl").splitlines():
            if line.startswith(("Device", "Total")):
                continue
            swap_type = "file"
            comps = line.split()
            if comps[0].startswith("/dev/"):
                swap_type = "partition"
            ret[comps[0]] = {
                "type": swap_type,
                "size": comps[1],
                "used": comps[2],
                "priority": comps[5],
            }
    return ret


def swapon(name, priority=None):
    """
    Activate a swap disk

    .. versionchanged:: 2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' mount.swapon /root/swapfile
    """
    ret = {}
    on_ = swaps()
    if name in on_:
        ret["stats"] = on_[name]
        ret["new"] = False
        return ret

    if __grains__["kernel"] == "SunOS":
        if __grains__["virtual"] != "zone":
            __salt__["cmd.run"](f"swap -a '{name}'", python_shell=False)
        else:
            return False
    else:
        cmd = f"swapon '{name}'"
        if priority and "AIX" not in __grains__["kernel"]:
            cmd += f" -p {priority}"
        __salt__["cmd.run"](cmd, python_shell=False)

    on_ = swaps()
    if name in on_:
        ret["stats"] = on_[name]
        ret["new"] = True
        return ret

    return ret


def swapoff(name):
    """
    Deactivate a named swap mount

    .. versionchanged:: 2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' mount.swapoff /root/swapfile
    """
    on_ = swaps()
    if name in on_:
        if __grains__["kernel"] == "SunOS":
            if __grains__["virtual"] != "zone":
                __salt__["cmd.run"](f"swap -a '{name}'", python_shell=False)
            else:
                return False
        elif __grains__["os"] != "OpenBSD":
            __salt__["cmd.run"](f"swapoff '{name}'", python_shell=False)
        else:
            __salt__["cmd.run"](f"swapctl -d '{name}'", python_shell=False)
        on_ = swaps()
        if name in on_:
            return False
        return True
    return None


def is_mounted(name):
    """
    .. versionadded:: 2014.7.0

    Provide information if the path is mounted

    CLI Example:

    .. code-block:: bash

        salt '*' mount.is_mounted /mnt/share
    """
    active_ = active()
    if name in active_:
        return True
    else:
        return False


def read_mount_cache(name):
    """
    .. versionadded:: 2018.3.0

    Provide information if the path is mounted

    CLI Example:

    .. code-block:: bash

        salt '*' mount.read_mount_cache /mnt/share
    """
    cache = salt.utils.mount.read_cache(__opts__)
    if cache:
        if "mounts" in cache and cache["mounts"]:
            if name in cache["mounts"]:
                return cache["mounts"][name]
    return {}


def write_mount_cache(real_name, device, mkmnt, fstype, mount_opts):
    """
    .. versionadded:: 2018.3.0

    Provide information if the path is mounted

    :param real_name:     The real name of the mount point where the device is mounted.
    :param device:        The device that is being mounted.
    :param mkmnt:         Whether or not the mount point should be created.
    :param fstype:        The file system that is used.
    :param mount_opts:    Additional options used when mounting the device.
    :return:              Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.write_mount_cache /mnt/share /dev/sda1 False ext4 defaults,nosuid
    """
    cache = salt.utils.mount.read_cache(__opts__)

    if not cache:
        cache = {}
        cache["mounts"] = {}
    else:
        if "mounts" not in cache:
            cache["mounts"] = {}

    cache["mounts"][real_name] = {
        "device": device,
        "fstype": fstype,
        "mkmnt": mkmnt,
        "opts": mount_opts,
    }

    cache_write = salt.utils.mount.write_cache(cache, __opts__)
    if cache_write:
        return True
    else:
        raise CommandExecutionError("Unable to write mount cache.")


def delete_mount_cache(real_name):
    """
    .. versionadded:: 2018.3.0

    Provide information if the path is mounted

    CLI Example:

    .. code-block:: bash

        salt '*' mount.delete_mount_cache /mnt/share
    """
    cache = salt.utils.mount.read_cache(__opts__)

    if cache:
        if "mounts" in cache:
            if real_name in cache["mounts"]:
                del cache["mounts"][real_name]
                cache_write = salt.utils.mount.write_cache(cache, __opts__)
                if not cache_write:
                    raise CommandExecutionError("Unable to write mount cache.")
    return True


def _filesystems(config="/etc/filesystems", leading_key=True):
    """
    Return the contents of the filesystems in an OrderedDict

    config
        File containing filesystem infomation

    leading_key
        True    return dictionary keyed by 'name' and value as dictionary with other keys, values (name excluded)
                OrderedDict({ '/dir' : OrderedDict({'dev': '/dev/hd8', .... }}))

        False   return dictionary  keyed by 'name' and value as dictionary with all keys, values (name included)
                OrderedDict({ '/dir' : OrderedDict({'name': '/dir', 'dev': '/dev/hd8', ... })})
    """
    ret = OrderedDict()
    lines = []
    parsing_block = False
    if not os.path.isfile(config) or "AIX" not in __grains__["kernel"]:
        return ret

    # read in block of filesystems, block starts with '/' till empty line
    with salt.utils.files.fopen(config) as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line)

            # skip till first entry
            if not line.startswith("/") and not parsing_block:
                continue

            if line.startswith("/"):
                parsing_block = True
                lines.append(line)
            elif not line.split():
                parsing_block = False
                try:
                    entry = _FileSystemsEntry.dict_from_lines(
                        lines, _FileSystemsEntry.compatibility_keys
                    )
                    lines = []
                    if "opts" in entry:
                        entry["opts"] = entry["opts"].split(",")
                    while entry["name"] in ret:
                        entry["name"] += "_"

                    if leading_key:
                        ret[entry.pop("name")] = entry
                    else:
                        ret[entry["name"]] = entry

                except _FileSystemsEntry.ParseError:
                    pass
            else:
                lines.append(line)

    return ret


def filesystems(config="/etc/filesystems"):
    """
    .. versionadded:: 2018.3.3

    List the contents of the filesystems

    CLI Example:

    .. code-block:: bash

        salt '*' mount.filesystems
    """
    ret = {}
    if "AIX" not in __grains__["kernel"]:
        return ret

    ret_dict = _filesystems(config)
    if ret_dict:
        ret_key = next(iter(ret_dict.keys()))
        ret = {ret_key: dict(ret_dict[ret_key])}

    return ret


def set_filesystems(
    name,
    device,
    vfstype,
    opts="-",
    mount="true",
    config="/etc/filesystems",
    test=False,
    match_on="auto",
    not_change=False,
    **kwargs,
):
    """
    .. versionadded:: 2018.3.3

    Verify that this mount is represented in the filesystems, change the mount
    to match the data passed, or add the mount if it is not present on AIX

    If the entry is found via `match_on` and `not_change` is True, the
    current line will be preserved.

        Provide information if the path is mounted

    :param name:          The name of the mount point where the device is mounted.
    :param device:        The device that is being mounted.
    :param vfstype:       The file system that is used (AIX has two fstypes, fstype and vfstype - similar to Linux fstype)
    :param opts:          Additional options used when mounting the device.
    :param mount:         Mount if not mounted, default True.
    :param config:        Configuration file, default /etc/filesystems.
    :param match:         File systems type to match on, default auto

    CLI Example:

    .. code-block:: bash

        salt '*' mount.set_filesystems /mnt/foo /dev/sdz1 jfs2
    """
    # Fix the opts type if it is a list
    if isinstance(opts, list):
        opts = ",".join(opts)

    # preserve arguments for updating
    entry_args = {
        "name": name,
        "dev": device.replace("\\ ", "\\040"),
        "vfstype": vfstype,
        "opts": opts,
        "mount": mount,
    }

    view_lines = []
    ret = None

    if "AIX" not in __grains__["kernel"]:
        return ret

    # Transform match_on into list--items will be checked later
    if isinstance(match_on, list):
        pass
    elif not isinstance(match_on, str):
        raise CommandExecutionError("match_on must be a string or list of strings")
    elif match_on == "auto":
        # Try to guess right criteria for auto....
        # added IBM types from sys/vmount.h after btrfs
        # NOTE: missing some special fstypes here
        specialFSes = frozenset(
            [
                "none",
                "tmpfs",
                "sysfs",
                "proc",
                "fusectl",
                "debugfs",
                "securityfs",
                "devtmpfs",
                "cgroup",
                "btrfs",
                "cdrfs",
                "procfs",
                "jfs",
                "jfs2",
                "nfs",
                "sfs",
                "nfs3",
                "cachefs",
                "udfs",
                "cifs",
                "namefs",
                "pmemfs",
                "ahafs",
                "nfs4",
                "autofs",
                "stnfs",
            ]
        )

        if vfstype in specialFSes:
            match_on = ["name"]
        else:
            match_on = ["dev"]
    else:
        match_on = [match_on]

    # generate entry and criteria objects, handle invalid keys in match_on
    entry_ip = _FileSystemsEntry.from_line(entry_args, kwargs)
    try:
        criteria = entry_ip.pick(match_on)

    except KeyError:

        def filterFn(key):
            return key not in _FileSystemsEntry.compatibility_keys

        invalid_keys = filter(filterFn, match_on)
        raise CommandExecutionError(f'Unrecognized keys in match_on: "{invalid_keys}"')

    # parse file, use ret to cache status
    if not os.path.isfile(config):
        raise CommandExecutionError(f'Bad config file "{config}"')

    # read in block of filesystem, block starts with '/' till empty line
    try:
        fsys_filedict = _filesystems(config, False)
        for fsys_view in fsys_filedict.items():
            if criteria.match(fsys_view):
                ret = "present"
                if entry_ip.match(fsys_view) or not_change:
                    view_lines.append(fsys_view)
                else:
                    ret = "change"
                    kv = entry_ip["name"]
                    view_lines.append((kv, entry_ip))
            else:
                view_lines.append(fsys_view)

    except OSError as exc:
        raise CommandExecutionError(f"Couldn't read from {config}: {exc}")

    # add line if not present or changed
    if ret is None:
        for dict_view in entry_ip.dict_from_entry().items():
            view_lines.append(dict_view)
        ret = "new"

    if ret != "present":  # ret in ['new', 'change']:
        try:
            with salt.utils.files.fopen(config, "wb") as ofile:
                # The line was changed, commit it!
                for fsys_view in view_lines:
                    entry = fsys_view[1]
                    list_strgs = _FileSystemsEntry.dict_to_list_lines(entry)
                    ofile.writelines(salt.utils.data.encode(list_strgs))

        except OSError:
            raise CommandExecutionError(f"File not writable {config}")
        except Exception as exc:
            raise CommandExecutionError("set_filesystems error exception {exc}")

    return ret


def rm_filesystems(name, device, config="/etc/filesystems"):
    """
    .. versionadded:: 2018.3.3

    Remove the mount point from the filesystems

    CLI Example:

    .. code-block:: bash

        salt '*' mount.rm_filesystems /mnt/foo /dev/sdg
    """
    modified = False
    view_lines = []

    if "AIX" not in __grains__["kernel"]:
        return modified

    criteria = _FileSystemsEntry(name=name, dev=device)
    try:
        fsys_filedict = _filesystems(config, False)
        for fsys_view in fsys_filedict.items():
            try:
                if criteria.match(fsys_view):
                    modified = True
                else:
                    view_lines.append(fsys_view)

            except _FileSystemsEntry.ParseError:
                view_lines.append(fsys_view)

    except OSError as exc:
        raise CommandExecutionError(f"Couldn't read from {config}: {exc}")

    if modified:
        try:
            with salt.utils.files.fopen(config, "wb") as ofile:
                for fsys_view in view_lines:
                    entry = fsys_view[1]
                    list_strgs = _FileSystemsEntry.dict_to_list_lines(entry)
                    ofile.writelines(salt.utils.data.encode(list_strgs))
        except OSError as exc:
            raise CommandExecutionError(f"Couldn't write to {config}: {exc}")
        except Exception as exc:
            raise CommandExecutionError("rm_filesystems error exception {exc}")

    return modified


def get_mount_from_path(path):
    """
    Return the mount providing a specified path.

    .. versionadded:: 3006.0

    path
        The path for the function to evaluate.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.get_mount_from_path /opt/some/nested/path
    """
    path = os.path.realpath(os.path.abspath(path))
    while path != os.path.sep:
        if os.path.ismount(path):
            return path
        path = os.path.abspath(os.path.join(path, os.pardir))
    return path


def get_device_from_path(path):
    """
    Return the underlying device for a specified path.

    .. versionadded:: 3006.0

    path
        The path for the function to evaluate.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.get_device_from_path /
    """
    mount = get_mount_from_path(path)
    mounts = active()
    return mounts.get(mount, {}).get("device")
