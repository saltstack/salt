"""
Functions for querying and modifying a user account and the groups to which it
belongs.
"""


import ctypes
import getpass
import logging
import os
import sys

import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from salt.utils.decorators.jinja import jinja_filter

# Conditional imports
try:
    import pwd

    HAS_PWD = True
except ImportError:
    HAS_PWD = False

try:
    import grp

    HAS_GRP = True
except ImportError:
    HAS_GRP = False

try:
    import pysss

    HAS_PYSSS = True
except ImportError:
    HAS_PYSSS = False

try:
    import salt.utils.win_functions

    HAS_WIN_FUNCTIONS = True
except ImportError:
    HAS_WIN_FUNCTIONS = False

log = logging.getLogger(__name__)


def get_user():
    """
    Get the current user
    """
    if HAS_PWD:
        ret = pwd.getpwuid(os.geteuid()).pw_name
    elif HAS_WIN_FUNCTIONS and salt.utils.win_functions.HAS_WIN32:
        ret = salt.utils.win_functions.get_current_user()
    else:
        raise CommandExecutionError(
            "Required external library (pwd or win32api) not installed"
        )
    return salt.utils.stringutils.to_unicode(ret)


@jinja_filter("get_uid")
def get_uid(user=None):
    """
    Get the uid for a given user name. If no user given, the current euid will
    be returned. If the user does not exist, None will be returned. On systems
    which do not support pwd or os.geteuid, None will be returned.
    """
    if not HAS_PWD:
        return None
    elif user is None:
        try:
            return os.geteuid()
        except AttributeError:
            return None
    else:
        try:
            return pwd.getpwnam(user).pw_uid
        except KeyError:
            return None


def _win_user_token_is_admin(user_token):
    """
    Using the win32 api, determine if the user with token 'user_token' has
    administrator rights.

    See MSDN entry here:
        http://msdn.microsoft.com/en-us/library/aa376389(VS.85).aspx
    """

    class SID_IDENTIFIER_AUTHORITY(ctypes.Structure):
        _fields_ = [
            ("byte0", ctypes.c_byte),
            ("byte1", ctypes.c_byte),
            ("byte2", ctypes.c_byte),
            ("byte3", ctypes.c_byte),
            ("byte4", ctypes.c_byte),
            ("byte5", ctypes.c_byte),
        ]

    nt_authority = SID_IDENTIFIER_AUTHORITY()
    nt_authority.byte5 = 5

    SECURITY_BUILTIN_DOMAIN_RID = 0x20
    DOMAIN_ALIAS_RID_ADMINS = 0x220
    administrators_group = ctypes.c_void_p()
    if (
        ctypes.windll.advapi32.AllocateAndInitializeSid(
            ctypes.byref(nt_authority),
            2,
            SECURITY_BUILTIN_DOMAIN_RID,
            DOMAIN_ALIAS_RID_ADMINS,
            0,
            0,
            0,
            0,
            0,
            0,
            ctypes.byref(administrators_group),
        )
        == 0
    ):
        raise Exception("AllocateAndInitializeSid failed")

    try:
        is_admin = ctypes.wintypes.BOOL()
        if (
            ctypes.windll.advapi32.CheckTokenMembership(
                user_token, administrators_group, ctypes.byref(is_admin)
            )
            == 0
        ):
            raise Exception("CheckTokenMembership failed")
        return is_admin.value != 0

    finally:
        ctypes.windll.advapi32.FreeSid(administrators_group)


def _win_current_user_is_admin():
    """
    ctypes.windll.shell32.IsUserAnAdmin() is intentionally avoided due to this
    function being deprecated.
    """
    return _win_user_token_is_admin(0)


def get_specific_user():
    """
    Get a user name for publishing. If you find the user is "root" attempt to be
    more specific
    """
    user = get_user()
    if salt.utils.platform.is_windows():
        if _win_current_user_is_admin():
            return "sudo_{}".format(user)
    else:
        env_vars = ("SUDO_USER",)
        if user == "root":
            for evar in env_vars:
                if evar in os.environ:
                    return "sudo_{}".format(os.environ[evar])
    return user


def chugid(runas, group=None):
    """
    Change the current process to belong to the specified user (and the groups
    to which it belongs)
    """
    uinfo = pwd.getpwnam(runas)
    supgroups = []
    supgroups_seen = set()

    if group:
        try:
            target_pw_gid = grp.getgrnam(group).gr_gid
        except KeyError as err:
            raise CommandExecutionError(
                "Failed to fetch the GID for {}. Error: {}".format(group, err)
            )
    else:
        target_pw_gid = uinfo.pw_gid

    # The line below used to exclude the current user's primary gid.
    # However, when root belongs to more than one group
    # this causes root's primary group of '0' to be dropped from
    # his grouplist.  On FreeBSD, at least, this makes some
    # command executions fail with 'access denied'.
    #
    # The Python documentation says that os.setgroups sets only
    # the supplemental groups for a running process.  On FreeBSD
    # this does not appear to be strictly true.
    group_list = get_group_dict(runas, include_default=True)
    if sys.platform == "darwin":
        group_list = {k: v for k, v in group_list.items() if not k.startswith("_")}
    for group_name in group_list:
        gid = group_list[group_name]
        if gid not in supgroups_seen and not supgroups_seen.add(gid):
            supgroups.append(gid)

    if os.getgid() != target_pw_gid:
        try:
            os.setgid(target_pw_gid)
        except OSError as err:
            raise CommandExecutionError(
                "Failed to change from gid {} to {}. Error: {}".format(
                    os.getgid(), target_pw_gid, err
                )
            )

    # Set supplemental groups
    if sorted(os.getgroups()) != sorted(supgroups):
        try:
            os.setgroups(supgroups)
        except OSError as err:
            raise CommandExecutionError(
                "Failed to set supplemental groups to {}. Error: {}".format(
                    supgroups, err
                )
            )

    if os.getuid() != uinfo.pw_uid:
        try:
            os.setuid(uinfo.pw_uid)
        except OSError as err:
            raise CommandExecutionError(
                "Failed to change from uid {} to {}. Error: {}".format(
                    os.getuid(), uinfo.pw_uid, err
                )
            )


def chugid_and_umask(runas, umask, group=None):
    """
    Helper method for for subprocess.Popen to initialise uid/gid and umask
    for the new process.
    """
    set_runas = False
    set_grp = False

    current_user = getpass.getuser()
    current_grp = grp.getgrgid(pwd.getpwnam(getpass.getuser()).pw_gid).gr_name

    if runas and runas != current_user:
        set_runas = True
        runas_user = runas
    else:
        runas_user = current_user

    if group:
        runas_grp = group
        if group != current_grp:
            set_grp = True
    else:
        if runas and runas != current_user:
            runas_grp = grp.getgrgid(pwd.getpwnam(runas_user).pw_gid).gr_name
            set_grp = True
        else:
            runas_grp = current_grp

    if set_runas or set_grp:
        chugid(runas_user, runas_grp)
    if umask is not None:
        os.umask(umask)  # pylint: disable=blacklisted-function


def get_default_group(user):
    """
    Returns the specified user's default group. If the user doesn't exist, a
    KeyError will be raised.
    """
    return (
        grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name if HAS_GRP and HAS_PWD else None
    )


def get_group_list(user, include_default=True):
    """
    Returns a list of all of the system group names of which the user
    is a member.
    """
    if HAS_GRP is False or HAS_PWD is False:
        return []
    group_names = None
    ugroups = set()
    if hasattr(os, "getgrouplist"):
        # Try os.getgrouplist, available in python >= 3.3
        log.trace("Trying os.getgrouplist for '%s'", user)
        try:
            group_names = [
                grp.getgrgid(grpid).gr_name
                for grpid in os.getgrouplist(user, pwd.getpwnam(user).pw_gid)
            ]
        except Exception:  # pylint: disable=broad-except
            pass
    elif HAS_PYSSS:
        # Try pysss.getgrouplist
        log.trace("Trying pysss.getgrouplist for '%s'", user)
        try:
            group_names = list(pysss.getgrouplist(user))
        except Exception:  # pylint: disable=broad-except
            pass

    if group_names is None:
        # Fall back to generic code
        # Include the user's default group to match behavior of
        # os.getgrouplist() and pysss.getgrouplist()
        log.trace("Trying generic group list for '%s'", user)
        group_names = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
        try:
            default_group = get_default_group(user)
            if default_group not in group_names:
                group_names.append(default_group)
        except KeyError:
            # If for some reason the user does not have a default group
            pass

    if group_names is not None:
        ugroups.update(group_names)

    if include_default is False:
        # Historically, saltstack code for getting group lists did not
        # include the default group. Some things may only want
        # supplemental groups, so include_default=False omits the users
        # default group.
        try:
            default_group = grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
            ugroups.remove(default_group)
        except KeyError:
            # If for some reason the user does not have a default group
            pass
    log.trace("Group list for user '%s': %s", user, sorted(ugroups))
    return sorted(ugroups)


def get_group_dict(user=None, include_default=True):
    """
    Returns a dict of all of the system groups as keys, and group ids
    as values, of which the user is a member.
    E.g.: {'staff': 501, 'sudo': 27}
    """
    if HAS_GRP is False or HAS_PWD is False:
        return {}
    group_dict = {}
    group_names = get_group_list(user, include_default=include_default)
    for group in group_names:
        group_dict.update({group: grp.getgrnam(group).gr_gid})
    return group_dict


def get_gid_list(user, include_default=True):
    """
    Returns a list of all of the system group IDs of which the user
    is a member.
    """
    if HAS_GRP is False or HAS_PWD is False:
        return []
    gid_list = list(get_group_dict(user, include_default=include_default).values())
    return sorted(set(gid_list))


def get_gid(group=None):
    """
    Get the gid for a given group name. If no group given, the current egid
    will be returned. If the group does not exist, None will be returned. On
    systems which do not support grp or os.getegid it will return None.
    """
    if not HAS_GRP:
        return None
    if group is None:
        try:
            return os.getegid()
        except AttributeError:
            return None
    else:
        try:
            return grp.getgrnam(group).gr_gid
        except KeyError:
            return None
