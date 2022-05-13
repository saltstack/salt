"""
Manage users on Mac OS 10.7+

.. important::
    If you feel that Salt should be using this module to manage users on a
    minion, and it is using a different module (or gives an error similar to
    *'user.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import logging
import time

import salt.utils.args
import salt.utils.data
import salt.utils.decorators.path
import salt.utils.files
import salt.utils.stringutils
import salt.utils.user
from salt.exceptions import CommandExecutionError, SaltInvocationError

try:
    import pwd
except ImportError:
    pass


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "user"


def __virtual__():
    if __grains__.get("kernel") != "Darwin" or __grains__["osrelease_info"] < (10, 7):
        return (False, "Only available on Mac OS 10.7+ systems")
    else:
        return __virtualname__


def _flush_dscl_cache():
    """
    Flush dscl cache
    """
    __salt__["cmd.run"](["dscacheutil", "-flushcache"], python_shell=False)


def _dscl(cmd, ctype="create"):
    """
    Run a dscl -create command
    """
    if __grains__["osrelease_info"] < (10, 8):
        source, noderoot = ".", ""
    else:
        source, noderoot = "localhost", "/Local/Default"
    if noderoot:
        cmd[0] = noderoot + cmd[0]

    return __salt__["cmd.run_all"](
        ["dscl", source, "-" + ctype] + cmd,
        output_loglevel="quiet" if ctype == "passwd" else "debug",
        python_shell=False,
    )


def _first_avail_uid():
    uids = {x.pw_uid for x in pwd.getpwall()}
    for idx in range(501, 2 ** 24):
        if idx not in uids:
            return idx


def add(
    name,
    uid=None,
    gid=None,
    groups=None,
    home=None,
    shell=None,
    fullname=None,
    createhome=True,
    **kwargs
):
    """
    Add a user to the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    """
    if info(name):
        raise CommandExecutionError("User '{}' already exists".format(name))

    if salt.utils.stringutils.contains_whitespace(name):
        raise SaltInvocationError("Username cannot contain whitespace")

    if uid is None:
        uid = _first_avail_uid()
    if gid is None:
        gid = 20  # gid 20 == 'staff', the default group
    if home is None:
        home = "/Users/{}".format(name)
    if shell is None:
        shell = "/bin/bash"
    if fullname is None:
        fullname = ""

    if not isinstance(uid, int):
        raise SaltInvocationError("uid must be an integer")
    if not isinstance(gid, int):
        raise SaltInvocationError("gid must be an integer")

    name_path = "/Users/{}".format(name)
    _dscl([name_path, "UniqueID", uid])
    _dscl([name_path, "PrimaryGroupID", gid])
    _dscl([name_path, "UserShell", shell])
    _dscl([name_path, "NFSHomeDirectory", home])
    _dscl([name_path, "RealName", fullname])

    # Make sure home directory exists
    if createhome:
        __salt__["file.mkdir"](home, user=uid, group=gid)

    # dscl buffers changes, sleep before setting group membership
    time.sleep(1)
    if groups:
        chgroups(name, groups)
    return True


def delete(name, remove=False, force=False):
    """
    Remove a user from the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name remove=True force=True
    """
    if salt.utils.stringutils.contains_whitespace(name):
        raise SaltInvocationError("Username cannot contain whitespace")
    if not info(name):
        return True

    # force is added for compatibility with user.absent state function
    if force:
        log.warning("force option is unsupported on MacOS, ignoring")

    # remove home directory from filesystem
    if remove:
        __salt__["file.remove"](info(name)["home"])

    # Remove from any groups other than primary group. Needs to be done since
    # group membership is managed separately from users and an entry for the
    # user will persist even after the user is removed.
    chgroups(name, ())
    return _dscl(["/Users/{}".format(name)], ctype="delete")["retcode"] == 0


def getent(refresh=False):
    """
    Return the list of all info for all users

    CLI Example:

    .. code-block:: bash

        salt '*' user.getent
    """
    if "user.getent" in __context__ and not refresh:
        return __context__["user.getent"]

    ret = []
    for data in pwd.getpwall():
        ret.append(_format_info(data))
    __context__["user.getent"] = ret
    return ret


def chuid(name, uid):
    """
    Change the uid for a named user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chuid foo 4376
    """
    if not isinstance(uid, int):
        raise SaltInvocationError("uid must be an integer")
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError("User '{}' does not exist".format(name))
    if uid == pre_info["uid"]:
        return True
    _dscl(["/Users/{}".format(name), "UniqueID", pre_info["uid"], uid], ctype="change")
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get("uid") == uid


def chgid(name, gid):
    """
    Change the default group of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgid foo 4376
    """
    if not isinstance(gid, int):
        raise SaltInvocationError("gid must be an integer")
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError("User '{}' does not exist".format(name))
    if gid == pre_info["gid"]:
        return True
    _dscl(
        ["/Users/{}".format(name), "PrimaryGroupID", pre_info["gid"], gid],
        ctype="change",
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get("gid") == gid


def chshell(name, shell):
    """
    Change the default shell of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chshell foo /bin/zsh
    """
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError("User '{}' does not exist".format(name))
    if shell == pre_info["shell"]:
        return True
    _dscl(
        ["/Users/{}".format(name), "UserShell", pre_info["shell"], shell],
        ctype="change",
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get("shell") == shell


def chhome(name, home, **kwargs):
    """
    Change the home directory of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo /Users/foo
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    persist = kwargs.pop("persist", False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)
    if persist:
        log.info("Ignoring unsupported 'persist' argument to user.chhome")

    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError("User '{}' does not exist".format(name))
    if home == pre_info["home"]:
        return True
    _dscl(
        ["/Users/{}".format(name), "NFSHomeDirectory", pre_info["home"], home],
        ctype="change",
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get("home") == home


def chfullname(name, fullname):
    """
    Change the user's Full Name

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname foo 'Foo Bar'
    """
    fullname = salt.utils.data.decode(fullname)
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError("User '{}' does not exist".format(name))
    pre_info["fullname"] = salt.utils.data.decode(pre_info["fullname"])
    if fullname == pre_info["fullname"]:
        return True
    _dscl(
        ["/Users/{}".format(name), "RealName", fullname],
        # use a 'create' command, because a 'change' command would fail if
        # current fullname is an empty string. The 'create' will just overwrite
        # this field.
        ctype="create",
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)

    current = salt.utils.data.decode(info(name).get("fullname"))
    return current == fullname


def chgroups(name, groups, append=False):
    """
    Change the groups to which the user belongs. Note that the user's primary
    group does not have to be one of the groups passed, membership in the
    user's primary group is automatically assumed.

    groups
        Groups to which the user should belong, can be passed either as a
        python list or a comma-separated string

    append
        Instead of removing user from groups not included in the ``groups``
        parameter, just add user to any groups for which they are not members

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgroups foo wheel,root
    """
    ### NOTE: **args isn't used here but needs to be included in this
    ### function for compatibility with the user.present state
    uinfo = info(name)
    if not uinfo:
        raise CommandExecutionError("User '{}' does not exist".format(name))
    if isinstance(groups, str):
        groups = groups.split(",")

    bad_groups = [x for x in groups if salt.utils.stringutils.contains_whitespace(x)]
    if bad_groups:
        raise SaltInvocationError(
            "Invalid group name(s): {}".format(", ".join(bad_groups))
        )
    ugrps = set(list_groups(name))
    desired = {str(x) for x in groups if bool(str(x))}
    primary_group = __salt__["file.gid_to_group"](uinfo["gid"])
    if primary_group:
        desired.add(primary_group)
    if ugrps == desired:
        return True
    # Add groups from which user is missing
    for group in desired - ugrps:
        _dscl(["/Groups/{}".format(group), "GroupMembership", name], ctype="append")
    if not append:
        # Remove from extra groups
        for group in ugrps - desired:
            _dscl(["/Groups/{}".format(group), "GroupMembership", name], ctype="delete")
    time.sleep(1)
    return set(list_groups(name)) == desired


def info(name):
    """
    Return user information

    CLI Example:

    .. code-block:: bash

        salt '*' user.info root
    """
    try:
        # pwd.getpwnam seems to cache weirdly, after an account is
        # deleted, it still returns data. Let's not use it
        data = next(iter(x for x in pwd.getpwall() if x.pw_name == name))
    except StopIteration:
        return {}
    else:
        return _format_info(data)


def _format_info(data):
    """
    Return user information in a pretty way
    """
    return {
        "gid": data.pw_gid,
        "groups": list_groups(data.pw_name),
        "home": data.pw_dir,
        "name": data.pw_name,
        "shell": data.pw_shell,
        "uid": data.pw_uid,
        "fullname": data.pw_gecos,
    }


@salt.utils.decorators.path.which("id")
def primary_group(name):
    """
    Return the primary group of the named user

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' user.primary_group saltadmin
    """
    return __salt__["cmd.run"](["id", "-g", "-n", name])


def list_groups(name):
    """
    Return a list of groups the named user belongs to.

    name

        The name of the user for which to list groups. Starting in Salt 2016.11.0,
        all groups for the user, including groups beginning with an underscore
        will be listed.

        .. versionchanged:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    """
    groups = [group for group in salt.utils.user.get_group_list(name)]
    return groups


def list_users():
    """
    Return a list of all users

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_users
    """
    users = _dscl(["/users"], "list")["stdout"]
    return users.split()


def rename(name, new_name):
    """
    Change the username for a named user

    CLI Example:

    .. code-block:: bash

        salt '*' user.rename name new_name
    """
    current_info = info(name)
    if not current_info:
        raise CommandExecutionError("User '{}' does not exist".format(name))
    new_info = info(new_name)
    if new_info:
        raise CommandExecutionError("User '{}' already exists".format(new_name))
    _dscl(["/Users/{}".format(name), "RecordName", name, new_name], ctype="change")
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(new_name).get("RecordName") == new_name


def get_auto_login():
    """
    .. versionadded:: 2016.3.0

    Gets the current setting for Auto Login

    :return: If enabled, returns the user name, otherwise returns False
    :rtype: str, bool

    CLI Example:

    .. code-block:: bash

        salt '*' user.get_auto_login
    """
    cmd = [
        "defaults",
        "read",
        "/Library/Preferences/com.apple.loginwindow.plist",
        "autoLoginUser",
    ]
    ret = __salt__["cmd.run_all"](cmd, ignore_retcode=True)
    return False if ret["retcode"] else ret["stdout"]


def _kcpassword(password):
    """
    Internal function for obfuscating the password used for AutoLogin
    This is later written as the contents of the ``/etc/kcpassword`` file

    .. versionadded:: 2017.7.3

    Adapted from:
    https://github.com/timsutton/osx-vm-templates/blob/master/scripts/support/set_kcpassword.py

    Args:

        password(str):
            The password to obfuscate

    Returns:
        str: The obfuscated password
    """
    # The magic 11 bytes - these are just repeated
    # 0x7D 0x89 0x52 0x23 0xD2 0xBC 0xDD 0xEA 0xA3 0xB9 0x1F
    key = [125, 137, 82, 35, 210, 188, 221, 234, 163, 185, 31]
    key_len = len(key)

    # Convert each character to a byte
    password = list(map(ord, password))

    # pad password length out to an even multiple of key length
    remainder = len(password) % key_len
    if remainder > 0:
        password = password + [0] * (key_len - remainder)

    # Break the password into chunks the size of len(key) (11)
    for chunk_index in range(0, len(password), len(key)):
        # Reset the key_index to 0 for each iteration
        key_index = 0

        # Do an XOR on each character of that chunk of the password with the
        # corresponding item in the key
        # The length of the password, or the length of the key, whichever is
        # smaller
        for password_index in range(
            chunk_index, min(chunk_index + len(key), len(password))
        ):
            password[password_index] = password[password_index] ^ key[key_index]
            key_index += 1

    # Convert each byte back to a character
    password = list(map(chr, password))
    return b"".join(salt.utils.data.encode(password))


def enable_auto_login(name, password):
    """
    .. versionadded:: 2016.3.0

    Configures the machine to auto login with the specified user

    Args:

        name (str): The user account use for auto login

        password (str): The password to user for auto login

            .. versionadded:: 2017.7.3

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' user.enable_auto_login stevej
    """
    # Make the entry into the defaults file
    cmd = [
        "defaults",
        "write",
        "/Library/Preferences/com.apple.loginwindow.plist",
        "autoLoginUser",
        name,
    ]
    __salt__["cmd.run"](cmd)
    current = get_auto_login()

    # Create/Update the kcpassword file with an obfuscated password
    o_password = _kcpassword(password=password)
    with salt.utils.files.set_umask(0o077):
        with salt.utils.files.fopen("/etc/kcpassword", "wb") as fd:
            fd.write(o_password)

    return current if isinstance(current, bool) else current.lower() == name.lower()


def disable_auto_login():
    """
    .. versionadded:: 2016.3.0

    Disables auto login on the machine

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' user.disable_auto_login
    """
    # Remove the kcpassword file
    cmd = "rm -f /etc/kcpassword"
    __salt__["cmd.run"](cmd)

    # Remove the entry from the defaults file
    cmd = [
        "defaults",
        "delete",
        "/Library/Preferences/com.apple.loginwindow.plist",
        "autoLoginUser",
    ]
    __salt__["cmd.run"](cmd)
    return True if not get_auto_login() else False
