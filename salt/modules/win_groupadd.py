# -*- coding: utf-8 -*-
"""
Manage groups on Windows

.. important::
    If you feel that Salt should be using this module to manage groups on a
    minion, and it is using a different module (or gives an error similar to
    *'group.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.winapi

try:
    import win32api
    import win32com.client
    import pywintypes

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "group"


def __virtual__():
    """
    Set the group module if the kernel is Windows
    """
    if salt.utils.platform.is_windows() and HAS_DEPENDENCIES:
        return __virtualname__
    return (False, "Module win_groupadd: module only works on Windows systems")


def _get_computer_object():
    """
    A helper function to get the object for the local machine

    Returns:
        object: Returns the computer object for the local machine
    """
    with salt.utils.winapi.Com():
        nt = win32com.client.Dispatch("AdsNameSpaces")
    return nt.GetObject("", "WinNT://.,computer")


def _get_group_object(name):
    """
    A helper function to get a specified group object

    Args:

        name (str): The name of the object

    Returns:
        object: The specified group object
    """
    with salt.utils.winapi.Com():
        nt = win32com.client.Dispatch("AdsNameSpaces")
    return nt.GetObject("", "WinNT://./" + name + ",group")


def _get_all_groups():
    """
    A helper function that gets a list of group objects for all groups on the
    machine

    Returns:
        iter: A list of objects for all groups on the machine
    """
    with salt.utils.winapi.Com():
        nt = win32com.client.Dispatch("AdsNameSpaces")
    results = nt.GetObject("", "WinNT://.")
    results.Filter = ["group"]
    return results


def _get_username(member):
    """
    Resolve the username from the member object returned from a group query

    Returns:
        str: The username converted to domain\\username format
    """
    return member.ADSPath.replace("WinNT://", "").replace("/", "\\")


def add(name, **kwargs):
    """
    Add the specified group

    Args:

        name (str):
            The name of the group to add

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' group.add foo
    """
    if not info(name):
        comp_obj = _get_computer_object()
        try:
            new_group = comp_obj.Create("group", name)
            new_group.SetInfo()
            log.info("Successfully created group {0}".format(name))
        except pywintypes.com_error as exc:
            msg = "Failed to create group {0}. {1}".format(
                name, win32api.FormatMessage(exc.excepinfo[5])
            )
            log.error(msg)
            return False
    else:
        log.warning("The group {0} already exists.".format(name))
        return False
    return True


def delete(name, **kwargs):
    """
    Remove the named group

    Args:

        name (str):
            The name of the group to remove

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    """
    if info(name):
        comp_obj = _get_computer_object()
        try:
            comp_obj.Delete("group", name)
            log.info("Successfully removed group {0}".format(name))
        except pywintypes.com_error as exc:
            msg = "Failed to remove group {0}. {1}".format(
                name, win32api.FormatMessage(exc.excepinfo[5])
            )
            log.error(msg)
            return False
    else:
        log.warning("The group {0} does not exists.".format(name))
        return False

    return True


def info(name):
    """
    Return information about a group

    Args:

        name (str):
            The name of the group for which to get information

    Returns:
        dict: A dictionary of information about the group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    """
    try:
        groupObj = _get_group_object(name)
        gr_name = groupObj.Name
        gr_mem = [_get_username(x) for x in groupObj.members()]
    except pywintypes.com_error as exc:
        msg = "Failed to access group {0}. {1}".format(
            name, win32api.FormatMessage(exc.excepinfo[5])
        )
        log.debug(msg)
        return False

    if not gr_name:
        return False

    return {"name": gr_name, "passwd": None, "gid": None, "members": gr_mem}


def getent(refresh=False):
    """
    Return info on all groups

    Args:

        refresh (bool):
            Refresh the info for all groups in ``__context__``. If False only
            the groups in ``__context__`` will be returned. If True the
            ``__context__`` will be refreshed with current data and returned.
            Default is False

    Returns:
        A list of groups and their information

    CLI Example:

    .. code-block:: bash

        salt '*' group.getent
    """
    if "group.getent" in __context__ and not refresh:
        return __context__["group.getent"]

    ret = []

    results = _get_all_groups()

    for result in results:
        group = {
            "gid": __salt__["file.group_to_gid"](result.Name),
            "members": [_get_username(x) for x in result.members()],
            "name": result.Name,
            "passwd": "x",
        }
        ret.append(group)
    __context__["group.getent"] = ret
    return ret


def adduser(name, username, **kwargs):
    """
    Add a user to a group

    Args:

        name (str):
            The name of the group to modify

        username (str):
            The name of the user to add to the group

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' group.adduser foo username
    """
    try:
        group_obj = _get_group_object(name)
    except pywintypes.com_error as exc:
        msg = "Failed to access group {0}. {1}".format(
            name, win32api.FormatMessage(exc.excepinfo[5])
        )
        log.error(msg)
        return False

    existing_members = [_get_username(x) for x in group_obj.members()]
    username = salt.utils.win_functions.get_sam_name(username)

    try:
        if username not in existing_members:
            group_obj.Add("WinNT://" + username.replace("\\", "/"))
            log.info("Added user {0}".format(username))
        else:
            log.warning("User {0} is already a member of {1}".format(username, name))
            return False
    except pywintypes.com_error as exc:
        msg = "Failed to add {0} to group {1}. {2}".format(
            username, name, win32api.FormatMessage(exc.excepinfo[5])
        )
        log.error(msg)
        return False

    return True


def deluser(name, username, **kwargs):
    """
    Remove a user from a group

    Args:

        name (str):
            The name of the group to modify

        username (str):
            The name of the user to remove from the group

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' group.deluser foo username
    """
    try:
        group_obj = _get_group_object(name)
    except pywintypes.com_error as exc:
        msg = "Failed to access group {0}. {1}".format(
            name, win32api.FormatMessage(exc.excepinfo[5])
        )
        log.error(msg)
        return False

    existing_members = [_get_username(x) for x in group_obj.members()]

    try:
        if salt.utils.win_functions.get_sam_name(username) in existing_members:
            group_obj.Remove("WinNT://" + username.replace("\\", "/"))
            log.info("Removed user {0}".format(username))
        else:
            log.warning("User {0} is not a member of {1}".format(username, name))
            return False
    except pywintypes.com_error as exc:
        msg = "Failed to remove {0} from group {1}. {2}".format(
            username, name, win32api.FormatMessage(exc.excepinfo[5])
        )
        log.error(msg)
        return False

    return True


def members(name, members_list, **kwargs):
    """
    Ensure a group contains only the members in the list

    Args:

        name (str):
            The name of the group to modify

        members_list (str):
            A single user or a comma separated list of users. The group will
            contain only the users specified in this list.

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' group.members foo 'user1,user2,user3'
    """
    members_list = [
        salt.utils.win_functions.get_sam_name(m) for m in members_list.split(",")
    ]
    if not isinstance(members_list, list):
        log.debug("member_list is not a list")
        return False

    try:
        obj_group = _get_group_object(name)
    except pywintypes.com_error as exc:
        # Group probably doesn't exist, but we'll log the error
        msg = "Failed to access group {0}. {1}".format(
            name, win32api.FormatMessage(exc.excepinfo[5])
        )
        log.error(msg)
        return False

    existing_members = [_get_username(x) for x in obj_group.members()]
    existing_members.sort()
    members_list.sort()

    if existing_members == members_list:
        log.info("{0} membership is correct".format(name))
        return True

    # add users
    success = True
    for member in members_list:
        if member not in existing_members:
            try:
                obj_group.Add("WinNT://" + member.replace("\\", "/"))
                log.info("User added: {0}".format(member))
            except pywintypes.com_error as exc:
                msg = "Failed to add {0} to {1}. {2}".format(
                    member, name, win32api.FormatMessage(exc.excepinfo[5])
                )
                log.error(msg)
                success = False

    # remove users not in members_list
    for member in existing_members:
        if member not in members_list:
            try:
                obj_group.Remove("WinNT://" + member.replace("\\", "/"))
                log.info("User removed: {0}".format(member))
            except pywintypes.com_error as exc:
                msg = "Failed to remove {0} from {1}. {2}".format(
                    member, name, win32api.FormatMessage(exc.excepinfo[5])
                )
                log.error(msg)
                success = False

    return success


def list_groups(refresh=False):
    """
    Return a list of groups

    Args:

        refresh (bool):
            Refresh the info for all groups in ``__context__``. If False only
            the groups in ``__context__`` will be returned. If True, the
            ``__context__`` will be refreshed with current data and returned.
            Default is False

    Returns:
        list: A list of groups on the machine

    CLI Example:

    .. code-block:: bash

        salt '*' group.list_groups
    """
    if "group.list_groups" in __context__ and not refresh:
        return __context__["group.list_groups"]

    results = _get_all_groups()

    ret = []

    for result in results:
        ret.append(result.Name)

    __context__["group.list_groups"] = ret

    return ret
