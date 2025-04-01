"""
Manage groups on FreeBSD

.. important::
    If you feel that Salt should be using this module to manage groups on a
    minion, and it is using a different module (or gives an error similar to
    *'group.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import logging

import salt.utils.args
import salt.utils.data

try:
    import grp
except ImportError:
    pass

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "group"


def __virtual__():
    """
    Set the user module if the kernel is FreeBSD or Dragonfly
    """
    if __grains__["kernel"] in ("FreeBSD", "DragonFly"):
        return __virtualname__
    return (
        False,
        "The pw_group execution module cannot be loaded: system is not supported.",
    )


def add(name, gid=None, **kwargs):
    """
    .. versionchanged:: 3006.0

    Add the specified group

    name
        Name of the new group

    gid
        Use GID for the new group

    CLI Example:

    .. code-block:: bash

        salt '*' group.add foo 3456
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    if salt.utils.data.is_true(kwargs.pop("system", False)):
        log.warning("pw_group module does not support the 'system' argument")
    if "non_unique" in kwargs:
        log.warning("The non_unique parameter is not supported on this platform.")
    if kwargs:
        log.warning("Invalid kwargs passed to group.add")

    cmd = "pw groupadd "
    if gid:
        cmd += f"-g {gid} "
    cmd = f"{cmd} -n {name}"
    ret = __salt__["cmd.run_all"](cmd, python_shell=False)

    return not ret["retcode"]


def delete(name):
    """
    Remove the named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    """
    ret = __salt__["cmd.run_all"](f"pw groupdel {name}", python_shell=False)

    return not ret["retcode"]


def info(name):
    """
    Return information about a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    """
    try:
        grinfo = grp.getgrnam(name)
    except KeyError:
        return {}
    else:
        return {
            "name": grinfo.gr_name,
            "passwd": grinfo.gr_passwd,
            "gid": grinfo.gr_gid,
            "members": grinfo.gr_mem,
        }


def getent(refresh=False):
    """
    Return info on all groups

    CLI Example:

    .. code-block:: bash

        salt '*' group.getent
    """
    if "group.getent" in __context__ and not refresh:
        return __context__["group.getent"]

    ret = []
    for grinfo in grp.getgrall():
        ret.append(info(grinfo.gr_name))
    __context__["group.getent"] = ret
    return ret


def chgid(name, gid):
    """
    Change the gid for a named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.chgid foo 4376
    """
    pre_gid = __salt__["file.group_to_gid"](name)
    if gid == pre_gid:
        return True
    cmd = f"pw groupmod {name} -g {gid}"
    __salt__["cmd.run"](cmd, python_shell=False)
    post_gid = __salt__["file.group_to_gid"](name)
    if post_gid != pre_gid:
        return post_gid == gid
    return False


def adduser(name, username):
    """
    Add a user in the group.

    CLI Example:

    .. code-block:: bash

         salt '*' group.adduser foo bar

    Verifies if a valid username 'bar' as a member of an existing group 'foo',
    if not then adds it.
    """
    # Note: pw exits with code 65 if group is unknown
    retcode = __salt__["cmd.retcode"](
        f"pw groupmod {name} -m {username}", python_shell=False
    )

    return not retcode


def deluser(name, username):
    """
    Remove a user from the group.

    CLI Example:

    .. code-block:: bash

         salt '*' group.deluser foo bar

    Removes a member user 'bar' from a group 'foo'. If group is not present
    then returns True.
    """
    grp_info = __salt__["group.info"](name)

    if username not in grp_info["members"]:
        return True

    # Note: pw exits with code 65 if group is unknown
    retcode = __salt__["cmd.retcode"](
        f"pw groupmod {name} -d {username}", python_shell=False
    )

    return not retcode


def members(name, members_list):
    """
    Replaces members of the group with a provided list.

    .. versionadded:: 2015.5.4

    CLI Example:

    .. code-block:: bash

        salt '*' group.members foo 'user1,user2,user3,...'

    Replaces a membership list for a local group 'foo'.
        foo:x:1234:user1,user2,user3,...
    """

    retcode = __salt__["cmd.retcode"](
        f"pw groupmod {name} -M {members_list}", python_shell=False
    )

    return not retcode
