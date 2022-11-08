"""
Manage groups on Linux, OpenBSD and NetBSD

.. important::
    If you feel that Salt should be using this module to manage groups on a
    minion, and it is using a different module (or gives an error similar to
    *'group.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import functools
import logging
import os

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

try:
    import grp
except ImportError:
    pass

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = "group"


def __virtual__():
    """
    Set the user module if the kernel is Linux or OpenBSD
    """
    if __grains__["kernel"] in ("Linux", "OpenBSD", "NetBSD"):
        return __virtualname__
    return (
        False,
        "The groupadd execution module cannot be loaded: "
        " only available on Linux, OpenBSD and NetBSD",
    )


def _which(cmd):
    """
    Utility function wrapper to error out early if a command is not found
    """
    _cmd = salt.utils.path.which(cmd)
    if not _cmd:
        raise CommandExecutionError("Command '{}' cannot be found".format(cmd))
    return _cmd


def add(name, gid=None, system=False, root=None, non_unique=False):
    """
    .. versionchanged:: 3006.0

    Add the specified group

    name
        Name of the new group

    gid
        Use GID for the new group

    system
        Create a system account

    root
        Directory to chroot into

    non_unique
        Allow creating groups with duplicate (non-unique) GIDs

        .. versionadded:: 3006.0

    CLI Example:

    .. code-block:: bash

        salt '*' group.add foo 3456
    """
    cmd = [_which("groupadd")]
    if gid:
        cmd.append("-g {}".format(gid))
        if non_unique:
            cmd.append("-o")
    if system and __grains__["kernel"] != "OpenBSD":
        cmd.append("-r")

    if root is not None:
        cmd.extend(("-R", root))

    cmd.append(name)

    ret = __salt__["cmd.run_all"](cmd, python_shell=False)

    return not ret["retcode"]


def delete(name, root=None):
    """
    Remove the named group

    name
        Name group to delete

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    """
    cmd = [_which("groupdel")]

    if root is not None:
        cmd.extend(("-R", root))

    cmd.append(name)

    ret = __salt__["cmd.run_all"](cmd, python_shell=False)

    return not ret["retcode"]


def info(name, root=None):
    """
    Return information about a group

    name
        Name of the group

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    """
    if root is not None:
        getgrnam = functools.partial(_getgrnam, root=root)
    else:
        getgrnam = functools.partial(grp.getgrnam)

    try:
        grinfo = getgrnam(name)
    except KeyError:
        return {}
    else:
        return _format_info(grinfo)


def _format_info(data):
    """
    Return formatted information in a pretty way.
    """
    return {
        "name": data.gr_name,
        "passwd": data.gr_passwd,
        "gid": data.gr_gid,
        "members": data.gr_mem,
    }


def getent(refresh=False, root=None):
    """
    Return info on all groups

    refresh
        Force a refresh of group information

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' group.getent
    """
    if "group.getent" in __context__ and not refresh:
        return __context__["group.getent"]

    ret = []
    if root is not None:
        getgrall = functools.partial(_getgrall, root=root)
    else:
        getgrall = functools.partial(grp.getgrall)

    for grinfo in getgrall():
        ret.append(_format_info(grinfo))
    __context__["group.getent"] = ret
    return ret


def _chattrib(name, key, value, param, root=None):
    """
    Change an attribute for a named user
    """
    pre_info = info(name, root=root)
    if not pre_info:
        return False

    if value == pre_info[key]:
        return True

    cmd = [_which("groupmod")]

    if root is not None:
        cmd.extend(("-R", root))

    cmd.extend((param, value, name))

    __salt__["cmd.run"](cmd, python_shell=False)
    return info(name, root=root).get(key) == value


def chgid(name, gid, root=None, non_unique=False):
    """
    .. versionchanged:: 3006.0

    Change the gid for a named group

    name
        Name of the group to modify

    gid
        Change the group ID to GID

    root
        Directory to chroot into

    non_unique
        Allow modifying groups with duplicate (non-unique) GIDs

        .. versionadded:: 3006.0

    CLI Example:

    .. code-block:: bash

        salt '*' group.chgid foo 4376
    """
    param = "-g"
    if non_unique:
        param = "-og"
    return _chattrib(name, "gid", gid, param, root=root)


def adduser(name, username, root=None):
    """
    Add a user in the group.

    name
        Name of the group to modify

    username
        Username to add to the group

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

         salt '*' group.adduser foo bar

    Verifies if a valid username 'bar' as a member of an existing group 'foo',
    if not then adds it.
    """
    on_redhat_5 = (
        __grains__.get("os_family") == "RedHat"
        and __grains__.get("osmajorrelease") == "5"
    )
    on_suse_11 = (
        __grains__.get("os_family") == "Suse"
        and __grains__.get("osmajorrelease") == "11"
    )

    if __grains__["kernel"] == "Linux":
        if on_redhat_5:
            cmd = [_which("gpasswd"), "-a", username, name]
        elif on_suse_11:
            cmd = [_which("usermod"), "-A", name, username]
        else:
            cmd = [_which("gpasswd"), "--add", username, name]
        if root is not None:
            cmd.extend(("--root", root))
    else:
        cmd = [_which("usermod"), "-G", name, username]
        if root is not None:
            cmd.extend(("-R", root))

    retcode = __salt__["cmd.retcode"](cmd, python_shell=False)

    return not retcode


def deluser(name, username, root=None):
    """
    Remove a user from the group.

    name
        Name of the group to modify

    username
        Username to delete from the group

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

         salt '*' group.deluser foo bar

    Removes a member user 'bar' from a group 'foo'. If group is not present
    then returns True.
    """
    on_redhat_5 = (
        __grains__.get("os_family") == "RedHat"
        and __grains__.get("osmajorrelease") == "5"
    )
    on_suse_11 = (
        __grains__.get("os_family") == "Suse"
        and __grains__.get("osmajorrelease") == "11"
    )

    grp_info = __salt__["group.info"](name)
    try:
        if username in grp_info["members"]:
            if __grains__["kernel"] == "Linux":
                if on_redhat_5:
                    cmd = [_which("gpasswd"), "-d", username, name]
                elif on_suse_11:
                    cmd = [_which("usermod"), "-R", name, username]
                else:
                    cmd = [_which("gpasswd"), "--del", username, name]
                if root is not None:
                    cmd.extend(("--root", root))
                retcode = __salt__["cmd.retcode"](cmd, python_shell=False)
            elif __grains__["kernel"] == "OpenBSD":
                out = __salt__["cmd.run_stdout"](
                    "id -Gn {}".format(username), python_shell=False
                )
                cmd = [_which("usermod"), "-S"]
                cmd.append(",".join([g for g in out.split() if g != str(name)]))
                cmd.append("{}".format(username))
                retcode = __salt__["cmd.retcode"](cmd, python_shell=False)
            else:
                log.error("group.deluser is not yet supported on this platform")
                return False
            return not retcode
        else:
            return True
    except CommandExecutionError:
        raise
    except Exception:  # pylint: disable=broad-except
        return True


def members(name, members_list, root=None):
    """
    Replaces members of the group with a provided list.

    name
        Name of the group to modify

    members_list
        Username list to set into the group

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' group.members foo 'user1,user2,user3,...'

    Replaces a membership list for a local group 'foo'.
        foo:x:1234:user1,user2,user3,...
    """
    on_redhat_5 = (
        __grains__.get("os_family") == "RedHat"
        and __grains__.get("osmajorrelease") == "5"
    )
    on_suse_11 = (
        __grains__.get("os_family") == "Suse"
        and __grains__.get("osmajorrelease") == "11"
    )

    if __grains__["kernel"] == "Linux":
        if on_redhat_5:
            cmd = [_which("gpasswd"), "-M", members_list, name]
        elif on_suse_11:
            for old_member in __salt__["group.info"](name).get("members"):
                __salt__["cmd.run"](
                    "{} -R {} {}".format(_which("groupmod"), old_member, name),
                    python_shell=False,
                )
            cmd = [_which("groupmod"), "-A", members_list, name]
        else:
            cmd = [_which("gpasswd"), "--members", members_list, name]
        if root is not None:
            cmd.extend(("--root", root))
        retcode = __salt__["cmd.retcode"](cmd, python_shell=False)
    elif __grains__["kernel"] == "OpenBSD":
        retcode = 1
        grp_info = __salt__["group.info"](name)
        if grp_info and name in grp_info["name"]:
            __salt__["cmd.run"](
                "{} {}".format(_which("groupdel"), name), python_shell=False
            )
            __salt__["cmd.run"](
                "{} -g {} {}".format(_which("groupadd"), grp_info["gid"], name),
                python_shell=False,
            )
            for user in members_list.split(","):
                if user:
                    retcode = __salt__["cmd.retcode"](
                        [_which("usermod"), "-G", name, user], python_shell=False
                    )
                    if not retcode == 0:
                        break
                # provided list is '': users previously deleted from group
                else:
                    retcode = 0
    else:
        log.error("group.members is not yet supported on this platform")
        return False

    return not retcode


def _getgrnam(name, root=None):
    """
    Alternative implementation for getgrnam, that use only /etc/group
    """
    root = root or "/"
    passwd = os.path.join(root, "etc/group")
    with salt.utils.files.fopen(passwd) as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            comps = line.strip().split(":")
            if len(comps) < 4:
                log.debug("Ignoring group line: %s", line)
                continue
            if comps[0] == name:
                # Generate a getpwnam compatible output
                comps[2] = int(comps[2])
                comps[3] = comps[3].split(",") if comps[3] else []
                return grp.struct_group(comps)
    raise KeyError("getgrnam(): name not found: {}".format(name))


def _getgrall(root=None):
    """
    Alternative implemetantion for getgrall, that use only /etc/group
    """
    root = root or "/"
    passwd = os.path.join(root, "etc/group")
    with salt.utils.files.fopen(passwd) as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            comps = line.strip().split(":")
            if len(comps) < 4:
                log.debug("Ignoring group line: %s", line)
                continue
            # Generate a getgrall compatible output
            comps[2] = int(comps[2])
            comps[3] = comps[3].split(",") if comps[3] else []
            yield grp.struct_group(comps)
