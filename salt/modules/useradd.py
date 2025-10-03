"""
Manage users with the useradd command

.. important::
    If you feel that Salt should be using this module to manage users on a
    minion, and it is using a different module (or gives an error similar to
    *'user.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import copy
import functools
import logging
import os

import salt.utils.data
import salt.utils.decorators.path
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.utils.user
from salt.exceptions import CommandExecutionError

try:
    import pwd

    HAS_PWD = True
except ImportError:
    HAS_PWD = False


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "user"


def __virtual__():
    """
    Set the user module if the kernel is Linux, OpenBSD, NetBSD or AIX
    """

    if HAS_PWD and __grains__["kernel"] in ("Linux", "OpenBSD", "NetBSD", "AIX"):
        return __virtualname__
    return (
        False,
        "useradd execution module not loaded: either pwd python library not available"
        " or system not one of Linux, OpenBSD, NetBSD or AIX",
    )


def _quote_username(name):
    """
    Usernames can only contain ascii chars, so make sure we return a str type
    """
    if not isinstance(name, str):
        return str(name)
    else:
        return salt.utils.stringutils.to_str(name)


def _get_gecos(name, root=None):
    """
    Retrieve GECOS field info and return it in dictionary form
    """
    if root is not None and __grains__["kernel"] != "AIX":
        getpwnam = functools.partial(_getpwnam, root=root)
    else:
        getpwnam = functools.partial(pwd.getpwnam)
    gecos_field = salt.utils.stringutils.to_unicode(
        getpwnam(_quote_username(name)).pw_gecos
    ).split(",", 4)

    if not gecos_field:
        return {}
    else:
        # Assign empty strings for any unspecified trailing GECOS fields
        while len(gecos_field) < 5:
            gecos_field.append("")
        return {
            "fullname": salt.utils.data.decode(gecos_field[0]),
            "roomnumber": salt.utils.data.decode(gecos_field[1]),
            "workphone": salt.utils.data.decode(gecos_field[2]),
            "homephone": salt.utils.data.decode(gecos_field[3]),
            "other": salt.utils.data.decode(gecos_field[4]),
        }


def _build_gecos(gecos_dict):
    """
    Accepts a dictionary entry containing GECOS field names and their values,
    and returns a full GECOS comment string, to be used with usermod.
    """
    return "{},{},{},{},{}".format(
        gecos_dict.get("fullname", ""),
        gecos_dict.get("roomnumber", ""),
        gecos_dict.get("workphone", ""),
        gecos_dict.get("homephone", ""),
        gecos_dict.get("other", ""),
    ).rstrip(",")


def _which(cmd):
    """
    Utility function wrapper to error out early if a command is not found
    """
    _cmd = salt.utils.path.which(cmd)
    if not _cmd:
        raise CommandExecutionError(f"Command '{cmd}' cannot be found")
    return _cmd


def _update_gecos(name, key, value, root=None):
    """
    Common code to change a user's GECOS information
    """
    if value is None:
        value = ""
    elif not isinstance(value, str):
        value = str(value)
    else:
        value = salt.utils.stringutils.to_unicode(value)
    pre_info = _get_gecos(name, root=root)
    if not pre_info:
        return False
    if value == pre_info[key]:
        return True
    gecos_data = copy.deepcopy(pre_info)
    gecos_data[key] = value

    cmd = [_which("usermod")]

    if root is not None and __grains__["kernel"] != "AIX":
        cmd.extend(("-R", root))
    cmd.extend(("-c", _build_gecos(gecos_data), name))

    __salt__["cmd.run"](cmd, python_shell=False)
    return _get_gecos(name, root=root).get(key) == value


def add(
    name,
    uid=None,
    gid=None,
    groups=None,
    home=None,
    shell=None,
    unique=True,
    system=False,
    fullname="",
    roomnumber="",
    workphone="",
    homephone="",
    other="",
    createhome=True,
    loginclass=None,
    nologinit=False,
    root=None,
    usergroup=None,
    local=False,
):
    """
    Add a user to the minion

    name
        Username LOGIN to add

    uid
        User ID of the new account

    gid
        Name or ID of the primary group of the new account

    groups
        List of supplementary groups of the new account

    home
        Home directory of the new account

    shell
        Login shell of the new account

    unique
        If not True, the user account can have a non-unique UID

    system
        Create a system account

    fullname
        GECOS field for the full name

    roomnumber
        GECOS field for the room number

    workphone
        GECOS field for the work phone

    homephone
        GECOS field for the home phone

    other
        GECOS field for other information

    createhome
        Create the user's home directory

    loginclass
        Login class for the new account (OpenBSD)

    nologinit
        Do not add the user to the lastlog and faillog databases

    root
        Directory to chroot into

    usergroup
        Create and add the user to a new primary group of the same name

    local (Only on systems with luseradd available)
        Specifically add the user locally rather than possibly through remote providers (e.g. LDAP)

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    """
    cmd = [_which("luseradd" if local else "useradd")]

    if shell:
        cmd.extend(["-s", shell])
    if uid not in (None, ""):
        cmd.extend(["-u", uid])
    if gid not in (None, ""):
        cmd.extend(["-g", gid])
    elif usergroup:
        if not local:
            cmd.append("-U")
            if __grains__["kernel"] != "Linux":
                log.warning("'usergroup' is only supported on GNU/Linux hosts.")
    elif groups is not None and name in groups:
        defs_file = "/etc/login.defs"
        if __grains__["kernel"] != "OpenBSD":
            try:
                with salt.utils.files.fopen(defs_file) as fp_:
                    for line in fp_:
                        line = salt.utils.stringutils.to_unicode(line)
                        if "USERGROUPS_ENAB" not in line[:15]:
                            continue

                        if "yes" in line:
                            cmd.extend(["-g", __salt__["file.group_to_gid"](name)])

                        # We found what we wanted, let's break out of the loop
                        break
            except OSError:
                log.debug(
                    "Error reading %s", defs_file, exc_info_on_loglevel=logging.DEBUG
                )
        else:
            usermgmt_file = "/etc/usermgmt.conf"
            try:
                with salt.utils.files.fopen(usermgmt_file) as fp_:
                    for line in fp_:
                        line = salt.utils.stringutils.to_unicode(line)
                        if "group" not in line[:5]:
                            continue

                        cmd.extend(["-g", line.split()[-1]])

                        # We found what we wanted, let's break out of the loop
                        break
            except OSError:
                # /etc/usermgmt.conf not present: defaults will be used
                pass

    # Setting usergroup to False adds a command argument. If
    # usergroup is None, no arguments are added to allow useradd to go
    # with the defaults defined for the OS.
    if usergroup is False:
        cmd.append("-n" if local else "-N")

    if createhome:
        if not local:
            cmd.append("-m")
    elif __grains__["kernel"] != "NetBSD" and __grains__["kernel"] != "OpenBSD":
        cmd.append("-M")

    if nologinit:
        cmd.append("-l")

    if home is not None:
        cmd.extend(["-d", home])

    if not unique and __grains__["kernel"] != "AIX":
        cmd.append("-o")

    if (
        system
        and __grains__["kernel"] != "NetBSD"
        and __grains__["kernel"] != "OpenBSD"
    ):
        cmd.append("-r")

    if __grains__["kernel"] == "OpenBSD":
        if loginclass is not None:
            cmd.extend(["-L", loginclass])

    cmd.append(name)

    if root is not None and not local and __grains__["kernel"] != "AIX":
        cmd.extend(("-R", root))

    ret = __salt__["cmd.run_all"](cmd, python_shell=False)

    if ret["retcode"] != 0:
        return False

    # At this point, the user was successfully created, so return true
    # regardless of the outcome of the below functions. If there is a
    # problem wth changing any of the user's info below, it will be raised
    # in a future highstate call. If anyone has a better idea on how to do
    # this, feel free to change it, but I didn't think it was a good idea
    # to return False when the user was successfully created since A) the
    # user does exist, and B) running useradd again would result in a
    # nonzero exit status and be interpreted as a False result.
    if groups:
        chgroups(name, groups, root=root)
    if fullname:
        chfullname(name, fullname, root=root)
    if roomnumber:
        chroomnumber(name, roomnumber, root=root)
    if workphone:
        chworkphone(name, workphone, root=root)
    if homephone:
        chhomephone(name, homephone, root=root)
    if other:
        chother(name, other, root=root)
    return True


def delete(name, remove=False, force=False, root=None, local=False):
    """
    Remove a user from the minion

    name
        Username to delete

    remove
        Remove home directory and mail spool

    force
        Force some actions that would fail otherwise

    root
        Directory to chroot into

    local (Only on systems with luserdel available):
        Ensure the user account is removed locally ignoring global
        account management (default is False).

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name remove=True force=True
    """
    cmd = [_which("luserdel" if local else "userdel")]

    if remove:
        cmd.append("-r")

    if (
        force
        and __grains__["kernel"] != "OpenBSD"
        and __grains__["kernel"] != "AIX"
        and not local
    ):
        cmd.append("-f")

    cmd.append(name)

    if root is not None and __grains__["kernel"] != "AIX" and not local:
        cmd.extend(("-R", root))

    ret = __salt__["cmd.run_all"](cmd, python_shell=False)

    if ret["retcode"] == 0:
        # Command executed with no errors
        return True

    if ret["retcode"] == 12:
        # There's a known bug in Debian based distributions, at least, that
        # makes the command exit with 12, see:
        #  https://bugs.launchpad.net/ubuntu/+source/shadow/+bug/1023509
        if __grains__["os_family"] not in ("Debian",):
            return False

        if "var/mail" in ret["stderr"] or "var/spool/mail" in ret["stderr"]:
            # We've hit the bug, let's log it and not fail
            log.debug(
                "While the userdel exited with code 12, this is a known bug on "
                "debian based distributions. See http://goo.gl/HH3FzT"
            )
            return True

    return False


def getent(refresh=False, root=None):
    """
    Return the list of all info for all users

    refresh
        Force a refresh of user information

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.getent
    """
    if "user.getent" in __context__ and not refresh:
        return __context__["user.getent"]

    ret = []
    if root is not None and __grains__["kernel"] != "AIX":
        getpwall = functools.partial(_getpwall, root=root)
    else:
        getpwall = functools.partial(pwd.getpwall)

    for data in getpwall():
        ret.append(_format_info(data))
    __context__["user.getent"] = ret
    return ret


def _chattrib(name, key, value, param, persist=False, root=None):
    """
    Change an attribute for a named user
    """
    pre_info = info(name, root=root)
    if not pre_info:
        raise CommandExecutionError(f"User '{name}' does not exist")

    if value == pre_info[key]:
        return True

    cmd = [_which("usermod")]

    if root is not None and __grains__["kernel"] != "AIX":
        cmd.extend(("-R", root))

    if persist and __grains__["kernel"] != "OpenBSD":
        cmd.append("-m")

    cmd.extend((param, value, name))

    __salt__["cmd.run"](cmd, python_shell=False)
    return info(name, root=root).get(key) == value


def chuid(name, uid, root=None):
    """
    Change the uid for a named user

    name
        User to modify

    uid
        New UID for the user account

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chuid foo 4376
    """
    return _chattrib(name, "uid", uid, "-u", root=root)


def chgid(name, gid, root=None):
    """
    Change the default group of the user

    name
        User to modify

    gid
        Force use GID as new primary group

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgid foo 4376
    """
    return _chattrib(name, "gid", gid, "-g", root=root)


def chshell(name, shell, root=None):
    """
    Change the default shell of the user

    name
        User to modify

    shell
        New login shell for the user account

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chshell foo /bin/zsh
    """
    return _chattrib(name, "shell", shell, "-s", root=root)


def chhome(name, home, persist=False, root=None):
    """
    Change the home directory of the user, pass True for persist to move files
    to the new home directory if the old home directory exist.

    name
        User to modify

    home
        New home directory for the user account

    persist
        Move contents of the home directory to the new location

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo /home/users/foo True
    """
    return _chattrib(name, "home", home, "-d", persist=persist, root=root)


def chgroups(name, groups, append=False, root=None):
    """
    Change the groups to which this user belongs

    name
        User to modify

    groups
        Groups to set for the user

    append : False
        If ``True``, append the specified group(s). Otherwise, this function
        will replace the user's groups with the specified group(s).

    root
        Directory to chroot into

    CLI Examples:

    .. code-block:: bash

        salt '*' user.chgroups foo wheel,root
        salt '*' user.chgroups foo wheel,root append=True
    """
    if isinstance(groups, str):
        groups = groups.split(",")
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True

    cmd = [_which("usermod")]

    if __grains__["kernel"] != "OpenBSD":
        if append and __grains__["kernel"] != "AIX":
            cmd.append("-a")
        cmd.append("-G")
    else:
        if append:
            cmd.append("-G")
        else:
            cmd.append("-S")

    if append and __grains__["kernel"] == "AIX":
        cmd.extend([",".join(ugrps) + "," + ",".join(groups), name])
    else:
        cmd.extend([",".join(groups), name])

    if root is not None and __grains__["kernel"] != "AIX":
        cmd.extend(("-R", root))

    result = __salt__["cmd.run_all"](cmd, python_shell=False)
    # try to fallback on gpasswd to add user to localgroups
    # for old lib-pamldap support
    if __grains__["kernel"] != "OpenBSD" and __grains__["kernel"] != "AIX":
        if result["retcode"] != 0 and "not found in" in result["stderr"]:
            ret = True
            for group in groups:
                cmd = ["gpasswd", "-a", name, group]
                if __salt__["cmd.retcode"](cmd, python_shell=False) != 0:
                    ret = False
            return ret
    return result["retcode"] == 0


def chfullname(name, fullname, root=None):
    """
    Change the user's Full Name

    name
        User to modify

    fullname
        GECOS field for the full name

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname foo "Foo Bar"
    """
    return _update_gecos(name, "fullname", fullname, root=root)


def chroomnumber(name, roomnumber, root=None):
    """
    Change the user's Room Number

    CLI Example:

    .. code-block:: bash

        salt '*' user.chroomnumber foo 123
    """
    return _update_gecos(name, "roomnumber", roomnumber, root=root)


def chworkphone(name, workphone, root=None):
    """
    Change the user's Work Phone

    name
        User to modify

    workphone
        GECOS field for the work phone

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chworkphone foo 7735550123
    """
    return _update_gecos(name, "workphone", workphone, root=root)


def chhomephone(name, homephone, root=None):
    """
    Change the user's Home Phone

    name
        User to modify

    homephone
        GECOS field for the home phone

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhomephone foo 7735551234
    """
    return _update_gecos(name, "homephone", homephone, root=root)


def chother(name, other, root=None):
    """
    Change the user's other GECOS attribute

    name
        User to modify

    other
        GECOS field for other information

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.chother foobar
    """
    return _update_gecos(name, "other", other, root=root)


def chloginclass(name, loginclass, root=None):
    """
    Change the default login class of the user

    name
        User to modify

    loginclass
        Login class for the new account

    root
        Directory to chroot into

    .. note::
        This function only applies to OpenBSD systems.

    CLI Example:

    .. code-block:: bash

        salt '*' user.chloginclass foo staff
    """
    if __grains__["kernel"] != "OpenBSD":
        return False

    if loginclass == get_loginclass(name):
        return True

    cmd = [_which("usermod"), "-L", loginclass, name]

    if root is not None and __grains__["kernel"] != "AIX":
        cmd.extend(("-R", root))

    __salt__["cmd.run"](cmd, python_shell=False)
    return get_loginclass(name) == loginclass


def info(name, root=None):
    """
    Return user information

    name
        User to get the information

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.info root
    """
    # If root is provided, we use a less portable solution that
    # depends on analyzing /etc/passwd manually. Of course we cannot
    # find users from NIS nor LDAP, but in those cases do not makes
    # sense to provide a root parameter.
    #
    # Please, note that if the non-root /etc/passwd file is long the
    # iteration can be slow.
    if root is not None and __grains__["kernel"] != "AIX":
        getpwnam = functools.partial(_getpwnam, root=root)
    else:
        getpwnam = functools.partial(pwd.getpwnam)

    try:
        data = getpwnam(_quote_username(name))
    except KeyError:
        return {}
    else:
        return _format_info(data)


def get_loginclass(name):
    """
    Get the login class of the user

    name
        User to get the information

    .. note::
        This function only applies to OpenBSD systems.

    CLI Example:

    .. code-block:: bash

        salt '*' user.get_loginclass foo
    """
    if __grains__["kernel"] != "OpenBSD":
        return False
    userinfo = __salt__["cmd.run_stdout"](["userinfo", name], python_shell=False)
    for line in userinfo.splitlines():
        if line.startswith("class"):
            try:
                ret = line.split(None, 1)[1]
                break
            except (ValueError, IndexError):
                continue
    else:
        ret = ""
    return ret


def _format_info(data):
    """
    Return user information in a pretty way
    """
    # Put GECOS info into a list
    gecos_field = salt.utils.stringutils.to_unicode(data.pw_gecos).split(",", 4)
    # Make sure our list has at least five elements
    while len(gecos_field) < 5:
        gecos_field.append("")

    return {
        "gid": data.pw_gid,
        "groups": list_groups(data.pw_name),
        "home": data.pw_dir,
        "name": data.pw_name,
        "passwd": data.pw_passwd,
        "shell": data.pw_shell,
        "uid": data.pw_uid,
        "fullname": gecos_field[0],
        "roomnumber": gecos_field[1],
        "workphone": gecos_field[2],
        "homephone": gecos_field[3],
        "other": gecos_field[4],
    }


@salt.utils.decorators.path.which("id")
def primary_group(name):
    """
    Return the primary group of the named user

    .. versionadded:: 2016.3.0

    name
        User to get the information

    CLI Example:

    .. code-block:: bash

        salt '*' user.primary_group saltadmin
    """
    return __salt__["cmd.run"](["id", "-g", "-n", name])


def list_groups(name):
    """
    Return a list of groups the named user belongs to

    name
        User to get the information

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    """
    return salt.utils.user.get_group_list(name)


def list_users(root=None):
    """
    Return a list of all users

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_users
    """
    if root is not None and __grains__["kernel"] != "AIX":
        getpwall = functools.partial(_getpwall, root=root)
    else:
        getpwall = functools.partial(pwd.getpwall)

    return sorted(user.pw_name for user in getpwall())


def rename(name, new_name, root=None):
    """
    Change the username for a named user

    name
        User to modify

    new_name
        New value of the login name

    root
        Directory to chroot into

    CLI Example:

    .. code-block:: bash

        salt '*' user.rename name new_name
    """
    if info(new_name, root=root):
        raise CommandExecutionError(f"User '{new_name}' already exists")

    return _chattrib(name, "name", new_name, "-l", root=root)


def _getpwnam(name, root=None):
    """
    Alternative implementation for getpwnam, that use only /etc/passwd
    """
    root = "/" if not root else root
    passwd = os.path.join(root, "etc/passwd")
    with salt.utils.files.fopen(passwd) as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            comps = line.strip().split(":")
            if comps[0] == name:
                # Generate a getpwnam compatible output
                comps[2], comps[3] = int(comps[2]), int(comps[3])
                return pwd.struct_passwd(comps)
    raise KeyError


def _getpwall(root=None):
    """
    Alternative implemetantion for getpwall, that use only /etc/passwd
    """
    root = "/" if not root else root
    passwd = os.path.join(root, "etc/passwd")
    with salt.utils.files.fopen(passwd) as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            comps = line.strip().split(":")
            # Generate a getpwall compatible output
            comps[2], comps[3] = int(comps[2]), int(comps[3])
            yield pwd.struct_passwd(comps)
