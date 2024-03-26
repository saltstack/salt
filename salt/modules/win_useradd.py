"""
Module for managing Windows Users.

.. important::
    If you feel that Salt should be using this module to manage users on a
    minion, and it is using a different module (or gives an error similar to
    *'user.info' is not available*), see :ref:`here
    <module-provider-override>`.

:depends:
        - pywintypes
        - win32api
        - win32con
        - win32net
        - win32netcon
        - win32profile
        - win32security
        - win32ts
        - wmi

.. note::
    This currently only works with local user accounts, not domain accounts
"""

import logging
import shlex
import time
from datetime import datetime

import salt.utils.args
import salt.utils.dateutils
import salt.utils.platform
import salt.utils.winapi
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

try:
    import pywintypes
    import win32api
    import win32con
    import win32net
    import win32netcon
    import win32profile
    import win32security
    import win32ts
    import wmi

    HAS_WIN32NET_MODS = True
except ImportError:
    HAS_WIN32NET_MODS = False

# Define the module's virtual name
__virtualname__ = "user"


def __virtual__():
    """
    Requires Windows and Windows Modules
    """
    if not salt.utils.platform.is_windows():
        return False, "Module win_useradd: Windows Only"

    if not HAS_WIN32NET_MODS:
        return False, "Module win_useradd: Missing Win32 Modules"

    return __virtualname__


def add(
    name,
    password=None,
    fullname=None,
    description=None,
    groups=None,
    home=None,
    homedrive=None,
    profile=None,
    logonscript=None,
):
    """
    Add a user to the minion.

    Args:
        name (str): User name

        password (str, optional): User's password in plain text.

        fullname (str, optional): The user's full name.

        description (str, optional): A brief description of the user account.

        groups (str, optional): A list of groups to add the user to.
            (see chgroups)

        home (str, optional): The path to the user's home directory.

        homedrive (str, optional): The drive letter to assign to the home
            directory. Must be the Drive Letter followed by a colon. ie: U:

        profile (str, optional): An explicit path to a profile. Can be a UNC or
            a folder on the system. If left blank, windows uses its default
            profile directory.

        logonscript (str, optional): Path to a login script to run when the user
            logs on.

    Returns:
        bool: True if successful. False is unsuccessful.

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name password
    """
    user_info = {}
    if name:
        user_info["name"] = name
    else:
        return False
    user_info["password"] = password
    user_info["priv"] = win32netcon.USER_PRIV_USER
    user_info["home_dir"] = home
    user_info["comment"] = description
    user_info["flags"] = win32netcon.UF_SCRIPT
    user_info["script_path"] = logonscript

    try:
        win32net.NetUserAdd(None, 1, user_info)
    except win32net.error as exc:
        log.error("Failed to create user %s", name)
        log.error("nbr: %s", exc.winerror)
        log.error("ctx: %s", exc.funcname)
        log.error("msg: %s", exc.strerror)
        return exc.strerror

    update(name=name, homedrive=homedrive, profile=profile, fullname=fullname)

    ret = chgroups(name, groups) if groups else True

    return ret


def update(
    name,
    password=None,
    fullname=None,
    description=None,
    home=None,
    homedrive=None,
    logonscript=None,
    profile=None,
    expiration_date=None,
    expired=None,
    account_disabled=None,
    unlock_account=None,
    password_never_expires=None,
    disallow_change_password=None,
):
    # pylint: disable=anomalous-backslash-in-string
    """
    Updates settings for the windows user. Name is the only required parameter.
    Settings will only be changed if the parameter is passed a value.

    .. versionadded:: 2015.8.0

    Args:
        name (str): The user name to update.

        password (str, optional): New user password in plain text.

        fullname (str, optional): The user's full name.

        description (str, optional): A brief description of the user account.

        home (str, optional): The path to the user's home directory.

        homedrive (str, optional): The drive letter to assign to the home
            directory. Must be the Drive Letter followed by a colon. ie: U:

        logonscript (str, optional): The path to the logon script.

        profile (str, optional): The path to the user's profile directory.

        expiration_date (date, optional): The date and time when the account
            expires. Can be a valid date/time string. To set to never expire
            pass the string 'Never'.

        expired (bool, optional): Pass `True` to expire the account. The user
            will be prompted to change their password at the next logon. Pass
            `False` to mark the account as 'not expired'. You can't use this to
            negate the expiration if the expiration was caused by the account
            expiring. You'll have to change the `expiration_date` as well.

        account_disabled (bool, optional): True disables the account. False
            enables the account.

        unlock_account (bool, optional): True unlocks a locked user account.
            False is ignored.

        password_never_expires (bool, optional): True sets the password to never
            expire. False allows the password to expire.

        disallow_change_password (bool, optional): True blocks the user from
            changing the password. False allows the user to change the password.

    Returns:
        bool: True if successful. False is unsuccessful.

    CLI Example:

    .. code-block:: bash

        salt '*' user.update bob password=secret profile=C:\\Users\\Bob
                 home=\\server\\homeshare\\bob homedrive=U:
    """
    # pylint: enable=anomalous-backslash-in-string
    # Make sure the user exists
    # Return an object containing current settings for the user
    try:
        user_info = win32net.NetUserGetInfo(None, name, 4)
    except win32net.error as exc:
        log.error("Failed to update user %s", name)
        log.error("nbr: %s", exc.winerror)
        log.error("ctx: %s", exc.funcname)
        log.error("msg: %s", exc.strerror)
        return exc.strerror

    # Check parameters to update
    # Update the user object with new settings
    if password:
        user_info["password"] = password
    if home:
        user_info["home_dir"] = home
    if homedrive:
        user_info["home_dir_drive"] = homedrive
    if description:
        user_info["comment"] = description
    if logonscript:
        user_info["script_path"] = logonscript
    if fullname:
        user_info["full_name"] = fullname
    if profile:
        user_info["profile"] = profile
    if expiration_date:
        if expiration_date == "Never":
            user_info["acct_expires"] = win32netcon.TIMEQ_FOREVER
        else:
            try:
                dt_obj = salt.utils.dateutils.date_cast(expiration_date)
            except (ValueError, RuntimeError):
                return f"Invalid Date/Time Format: {expiration_date}"
            user_info["acct_expires"] = time.mktime(dt_obj.timetuple())
    if expired is not None:
        if expired:
            user_info["password_expired"] = 1
        else:
            user_info["password_expired"] = 0
    if account_disabled is not None:
        if account_disabled:
            user_info["flags"] |= win32netcon.UF_ACCOUNTDISABLE
        else:
            user_info["flags"] &= ~win32netcon.UF_ACCOUNTDISABLE
    if unlock_account is not None:
        if unlock_account:
            user_info["flags"] &= ~win32netcon.UF_LOCKOUT
    if password_never_expires is not None:
        if password_never_expires:
            user_info["flags"] |= win32netcon.UF_DONT_EXPIRE_PASSWD
        else:
            user_info["flags"] &= ~win32netcon.UF_DONT_EXPIRE_PASSWD
    if disallow_change_password is not None:
        if disallow_change_password:
            user_info["flags"] |= win32netcon.UF_PASSWD_CANT_CHANGE
        else:
            user_info["flags"] &= ~win32netcon.UF_PASSWD_CANT_CHANGE

    # Apply new settings
    try:
        win32net.NetUserSetInfo(None, name, 4, user_info)
    except win32net.error as exc:
        log.error("Failed to update user %s", name)
        log.error("nbr: %s", exc.winerror)
        log.error("ctx: %s", exc.funcname)
        log.error("msg: %s", exc.strerror)
        return exc.strerror

    return True


def delete(name, purge=False, force=False):
    """
    Remove a user from the minion

    Args:
        name (str): The name of the user to delete

        purge (bool, optional): Boolean value indicating that the user profile
            should also be removed when the user account is deleted. If set to
            True the profile will be removed. Default is False.

        force (bool, optional): Boolean value indicating that the user account
            should be deleted even if the user is logged in. True will log the
            user out and delete user.

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name
    """
    # Check if the user exists
    try:
        user_info = win32net.NetUserGetInfo(None, name, 4)
    except win32net.error as exc:
        log.error("User not found: %s", name)
        log.error("nbr: %s", exc.winerror)
        log.error("ctx: %s", exc.funcname)
        log.error("msg: %s", exc.strerror)
        return exc.strerror

    # Check if the user is logged in
    # Return a list of logged in users
    try:
        sess_list = win32ts.WTSEnumerateSessions()
    except win32ts.error as exc:
        log.error("No logged in users found")
        log.error("nbr: %s", exc.winerror)
        log.error("ctx: %s", exc.funcname)
        log.error("msg: %s", exc.strerror)

    # Is the user one that is logged in
    logged_in = False
    session_id = None
    for sess in sess_list:
        if (
            win32ts.WTSQuerySessionInformation(
                None, sess["SessionId"], win32ts.WTSUserName
            )
            == name
        ):
            session_id = sess["SessionId"]
            logged_in = True

    # If logged in and set to force, log the user out and continue
    # If logged in and not set to force, return false
    if logged_in:
        if force:
            try:
                win32ts.WTSLogoffSession(
                    win32ts.WTS_CURRENT_SERVER_HANDLE, session_id, True
                )
            except win32ts.error as exc:
                log.error("User not found: %s", name)
                log.error("nbr: %s", exc.winerror)
                log.error("ctx: %s", exc.funcname)
                log.error("msg: %s", exc.strerror)
                return exc.strerror
        else:
            log.error("User %s is currently logged in.", name)
            return False

    # Remove the User Profile directory
    if purge:
        try:
            sid = getUserSid(name)
            win32profile.DeleteProfile(sid)
        except pywintypes.error as exc:
            (number, context, message) = exc.args
            if number == 2:  # Profile Folder Not Found
                pass
            else:
                log.error("Failed to remove profile for %s", name)
                log.error("nbr: %s", exc.winerror)
                log.error("ctx: %s", exc.funcname)
                log.error("msg: %s", exc.strerror)
                return exc.strerror

    # And finally remove the user account
    try:
        win32net.NetUserDel(None, name)
    except win32net.error as exc:
        log.error("Failed to delete user %s", name)
        log.error("nbr: %s", exc.winerror)
        log.error("ctx: %s", exc.funcname)
        log.error("msg: %s", exc.strerror)
        return exc.strerror

    return True


def getUserSid(username):
    """
    Get the Security ID for the user

    Args:
        username (str): The user name for which to look up the SID

    Returns:
        str: The user SID

    CLI Example:

    .. code-block:: bash

        salt '*' user.getUserSid jsnuffy
    """
    domain = win32api.GetComputerName()
    if username.find("\\") != -1:
        domain = username.split("\\")[0]
        username = username.split("\\")[-1]
    domain = domain.upper()
    return win32security.ConvertSidToStringSid(
        win32security.LookupAccountName(None, domain + "\\" + username)[0]
    )


def setpassword(name, password):
    """
    Set the user's password

    Args:
        name (str): The user name for which to set the password

        password (str): The new password

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.setpassword jsnuffy sup3rs3cr3t
    """
    return update(name=name, password=password)


def addgroup(name, group):
    """
    Add user to a group

    Args:
        name (str): The user name to add to the group

        group (str): The name of the group to which to add the user

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.addgroup jsnuffy 'Power Users'
    """
    name = shlex.quote(name)
    group = shlex.quote(group).lstrip("'").rstrip("'")

    user = info(name)
    if not user:
        return False
    if group in user["groups"]:
        return True

    cmd = f'net localgroup "{group}" {name} /add'
    ret = __salt__["cmd.run_all"](cmd, python_shell=True)

    return ret["retcode"] == 0


def removegroup(name, group):
    """
    Remove user from a group

    Args:
        name (str): The user name to remove from the group

        group (str): The name of the group from which to remove the user

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.removegroup jsnuffy 'Power Users'
    """
    name = shlex.quote(name)
    group = shlex.quote(group).lstrip("'").rstrip("'")

    user = info(name)

    if not user:
        return False

    if group not in user["groups"]:
        return True

    cmd = f'net localgroup "{group}" {name} /delete'
    ret = __salt__["cmd.run_all"](cmd, python_shell=True)

    return ret["retcode"] == 0


def chhome(name, home, **kwargs):
    """
    Change the home directory of the user, pass True for persist to move files
    to the new home directory if the old home directory exist.

    Args:
        name (str): The name of the user whose home directory you wish to change

        home (str): The new location of the home directory

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo \\\\fileserver\\home\\foo True
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    persist = kwargs.pop("persist", False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)
    if persist:
        log.info("Ignoring unsupported 'persist' argument to user.chhome")

    pre_info = info(name)

    if not pre_info:
        return False

    if home == pre_info["home"]:
        return True

    if not update(name=name, home=home):
        return False

    post_info = info(name)
    if post_info["home"] != pre_info["home"]:
        return post_info["home"] == home

    return False


def chprofile(name, profile):
    """
    Change the profile directory of the user

    Args:
        name (str): The name of the user whose profile you wish to change

        profile (str): The new location of the profile

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.chprofile foo \\\\fileserver\\profiles\\foo
    """
    return update(name=name, profile=profile)


def chfullname(name, fullname):
    """
    Change the full name of the user

    Args:
        name (str): The user name for which to change the full name

        fullname (str): The new value for the full name

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname user 'First Last'
    """
    return update(name=name, fullname=fullname)


def chgroups(name, groups, append=True):
    """
    Change the groups this user belongs to, add append=False to make the user a
    member of only the specified groups

    Args:
        name (str): The user name for which to change groups

        groups (str, list): A single group or a list of groups to assign to the
            user. For multiple groups this can be a comma delimited string or a
            list.

        append (bool, optional): True adds the passed groups to the user's
            current groups. False sets the user's groups to the passed groups
            only. Default is True.

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgroups jsnuffy Administrators,Users True
    """
    if isinstance(groups, str):
        groups = groups.split(",")

    groups = [x.strip(" *") for x in groups]
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True

    name = shlex.quote(name)

    if not append:
        for group in ugrps:
            group = shlex.quote(group).lstrip("'").rstrip("'")
            if group not in groups:
                cmd = f'net localgroup "{group}" {name} /delete'
                __salt__["cmd.run_all"](cmd, python_shell=True)

    for group in groups:
        if group in ugrps:
            continue
        group = shlex.quote(group).lstrip("'").rstrip("'")
        cmd = f'net localgroup "{group}" {name} /add'
        out = __salt__["cmd.run_all"](cmd, python_shell=True)
        if out["retcode"] != 0:
            log.error(out["stdout"])
            return False

    agrps = set(list_groups(name))
    return len(ugrps - agrps) == 0


def info(name):
    """
    Return user information

    Args:
        name (str): Username for which to display information

    Returns:
        dict: A dictionary containing user information
            - fullname
            - username
            - SID
            - passwd (will always return None)
            - comment (same as description, left here for backwards compatibility)
            - description
            - active
            - logonscript
            - profile
            - home
            - homedrive
            - groups
            - password_changed
            - successful_logon_attempts
            - failed_logon_attempts
            - last_logon
            - account_disabled
            - account_locked
            - password_never_expires
            - disallow_change_password
            - gid

    CLI Example:

    .. code-block:: bash

        salt '*' user.info jsnuffy
    """
    ret = {}
    items = {}
    try:
        items = win32net.NetUserGetInfo(None, name, 4)
    except win32net.error:
        pass

    if items:
        groups = []
        try:
            groups = win32net.NetUserGetLocalGroups(None, name)
        except win32net.error:
            pass

        ret["fullname"] = items["full_name"]
        ret["name"] = items["name"]
        ret["uid"] = win32security.ConvertSidToStringSid(items["user_sid"])
        ret["passwd"] = items["password"]
        ret["comment"] = items["comment"]
        ret["description"] = items["comment"]
        ret["active"] = not bool(items["flags"] & win32netcon.UF_ACCOUNTDISABLE)
        ret["logonscript"] = items["script_path"]
        ret["profile"] = items["profile"]
        ret["failed_logon_attempts"] = items["bad_pw_count"]
        ret["successful_logon_attempts"] = items["num_logons"]
        secs = time.mktime(datetime.now().timetuple()) - items["password_age"]
        ret["password_changed"] = datetime.fromtimestamp(secs).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if items["last_logon"] == 0:
            ret["last_logon"] = "Never"
        else:
            ret["last_logon"] = datetime.fromtimestamp(items["last_logon"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ret["expiration_date"] = datetime.fromtimestamp(items["acct_expires"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        ret["expired"] = items["password_expired"] == 1
        if not ret["profile"]:
            ret["profile"] = _get_userprofile_from_registry(name, ret["uid"])
        ret["home"] = items["home_dir"]
        ret["homedrive"] = items["home_dir_drive"]
        if not ret["home"]:
            ret["home"] = ret["profile"]
        ret["groups"] = groups
        if items["flags"] & win32netcon.UF_DONT_EXPIRE_PASSWD == 0:
            ret["password_never_expires"] = False
        else:
            ret["password_never_expires"] = True
        if items["flags"] & win32netcon.UF_ACCOUNTDISABLE == 0:
            ret["account_disabled"] = False
        else:
            ret["account_disabled"] = True
        if items["flags"] & win32netcon.UF_LOCKOUT == 0:
            ret["account_locked"] = False
        else:
            ret["account_locked"] = True
        if items["flags"] & win32netcon.UF_PASSWD_CANT_CHANGE == 0:
            ret["disallow_change_password"] = False
        else:
            ret["disallow_change_password"] = True

        ret["gid"] = ""

        return ret

    else:

        return {}


def _get_userprofile_from_registry(user, sid):
    """
    In case net user doesn't return the userprofile we can get it from the
    registry

    Args:
        user (str): The user name, used in debug message

        sid (str): The sid to lookup in the registry

    Returns:
        str: Profile directory
    """
    profile_dir = __utils__["reg.read_value"](
        "HKEY_LOCAL_MACHINE",
        f"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList\\{sid}",
        "ProfileImagePath",
    )["vdata"]
    log.debug('user %s with sid=%s profile is located at "%s"', user, sid, profile_dir)
    return profile_dir


def list_groups(name):
    """
    Return a list of groups the named user belongs to

    Args:
        name (str): The user name for which to list groups

    Returns:
        list: A list of groups to which the user belongs

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    """
    ugrp = set()
    try:
        user = info(name)["groups"]
    except KeyError:
        return False
    for group in user:
        ugrp.add(group.strip(" *"))

    return sorted(list(ugrp))


def getent(refresh=False):
    """
    Return the list of all info for all users

    Args:
        refresh (bool, optional): Refresh the cached user information. Useful
            when used from within a state function. Default is False.

    Returns:
        dict: A dictionary containing information about all users on the system

    CLI Example:

    .. code-block:: bash

        salt '*' user.getent
    """
    if "user.getent" in __context__ and not refresh:
        return __context__["user.getent"]

    ret = []
    for user in __salt__["user.list_users"]():
        stuff = {}
        user_info = __salt__["user.info"](user)

        stuff["gid"] = ""
        stuff["groups"] = user_info["groups"]
        stuff["home"] = user_info["home"]
        stuff["name"] = user_info["name"]
        stuff["passwd"] = user_info["passwd"]
        stuff["shell"] = ""
        stuff["uid"] = user_info["uid"]

        ret.append(stuff)

    __context__["user.getent"] = ret
    return ret


def list_users():
    """
    Return a list of all users on Windows

    Returns:
        list: A list of all users on the system

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_users
    """
    res = 0
    user_list = []
    dowhile = True
    try:
        while res or dowhile:
            dowhile = False
            (users, _, res) = win32net.NetUserEnum(
                None,
                0,
                win32netcon.FILTER_NORMAL_ACCOUNT,
                res,
                win32netcon.MAX_PREFERRED_LENGTH,
            )
            for user in users:
                user_list.append(user["name"])
        return user_list
    except win32net.error:
        pass


def rename(name, new_name):
    """
    Change the username for a named user

    Args:
        name (str): The user name to change

        new_name (str): The new name for the current user

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' user.rename jsnuffy jshmoe
    """
    # Load information for the current name
    current_info = info(name)
    if not current_info:
        raise CommandExecutionError(f"User '{name}' does not exist")

    # Look for an existing user with the new name
    new_info = info(new_name)
    if new_info:
        raise CommandExecutionError(f"User '{new_name}' already exists")

    # Rename the user account
    # Connect to WMI
    with salt.utils.winapi.Com():
        c = wmi.WMI(find_classes=0)

        # Get the user object
        try:
            user = c.Win32_UserAccount(Name=name)[0]
        except IndexError:
            raise CommandExecutionError(f"User '{name}' does not exist")

        # Rename the user
        result = user.Rename(new_name)[0]

        # Check the result (0 means success)
        if not result == 0:
            # Define Error Dict
            error_dict = {
                0: "Success",
                1: "Instance not found",
                2: "Instance required",
                3: "Invalid parameter",
                4: "User not found",
                5: "Domain not found",
                6: (
                    "Operation is allowed only on the primary domain controller of the"
                    " domain"
                ),
                7: "Operation is not allowed on the last administrative account",
                8: (
                    "Operation is not allowed on specified special groups: user, admin,"
                    " local, or guest"
                ),
                9: "Other API error",
                10: "Internal error",
            }
            raise CommandExecutionError(
                "There was an error renaming '{}' to '{}'. Error: {}".format(
                    name, new_name, error_dict[result]
                )
            )

    return info(new_name).get("name") == new_name


def current(sam=False):
    """
    Get the username that salt-minion is running under. If salt-minion is
    running as a service it should return the Local System account. If salt is
    running from a command prompt it should return the username that started the
    command prompt.

    .. versionadded:: 2015.5.6

    Args:
        sam (bool, optional): False returns just the username without any domain
            notation. True returns the domain with the username in the SAM
            format. Ie: ``domain\\username``

    Returns:
        str: Returns username

    CLI Example:

    .. code-block:: bash

        salt '*' user.current
    """
    try:
        if sam:
            user_name = win32api.GetUserNameEx(win32con.NameSamCompatible)
        else:
            user_name = win32api.GetUserName()
    except pywintypes.error as exc:
        log.error("Failed to get current user")
        log.error("nbr: %s", exc.winerror)
        log.error("ctx: %s", exc.funcname)
        log.error("msg: %s", exc.strerror)
        raise CommandExecutionError("Failed to get current user", info=exc)

    if not user_name:
        raise CommandExecutionError("Failed to get current user")

    return user_name
