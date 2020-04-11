# -*- coding: utf-8 -*-
"""
Manage the Windows System PATH

Note that not all Windows applications will rehash the PATH environment variable,
Only the ones that listen to the WM_SETTINGCHANGE message
http://support.microsoft.com/kb/104011
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import os

# Import Salt libs
import salt.utils.args
import salt.utils.data
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.win_functions

# Import 3rd-party libs
from salt.ext.six.moves import map

try:
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Settings
log = logging.getLogger(__name__)

HIVE = "HKEY_LOCAL_MACHINE"
KEY = "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment"
VNAME = "PATH"
VTYPE = "REG_EXPAND_SZ"
PATHSEP = str(os.pathsep)  # future lint: disable=blacklisted-function


def __virtual__():
    """
    Load only on Windows
    """
    if salt.utils.platform.is_windows() and HAS_WIN32:
        return "win_path"
    return (False, "Module win_path: module only works on Windows systems")


def _normalize_dir(string_):
    """
    Normalize the directory to make comparison possible
    """
    return os.path.normpath(salt.utils.stringutils.to_unicode(string_))


def rehash():
    """
    Send a WM_SETTINGCHANGE Broadcast to Windows to refresh the Environment
    variables for new processes.

    .. note::
        This will only affect new processes that aren't launched by services. To
        apply changes to the path to services, the host must be restarted. The
        ``salt-minion``, if running as a service, will not see changes to the
        environment until the system is restarted. See
        `MSDN Documentation <https://support.microsoft.com/en-us/help/821761/changes-that-you-make-to-environment-variables-do-not-affect-services>`_

    CLI Example:

    .. code-block:: bash

        salt '*' win_path.rehash
    """
    return salt.utils.win_functions.broadcast_setting_change("Environment")


def get_path():
    """
    Returns a list of items in the SYSTEM path

    CLI Example:

    .. code-block:: bash

        salt '*' win_path.get_path
    """
    ret = salt.utils.stringutils.to_unicode(
        __salt__["reg.read_value"](
            "HKEY_LOCAL_MACHINE",
            "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
            "PATH",
        )["vdata"]
    ).split(";")

    # Trim ending backslash
    return list(map(_normalize_dir, ret))


def exists(path):
    """
    Check if the directory is configured in the SYSTEM path
    Case-insensitive and ignores trailing backslash

    Returns:
        boolean True if path exists, False if not

    CLI Example:

    .. code-block:: bash

        salt '*' win_path.exists 'c:\\python27'
        salt '*' win_path.exists 'c:\\python27\\'
        salt '*' win_path.exists 'C:\\pyThon27'
    """
    path = _normalize_dir(path)
    sysPath = get_path()

    return path.lower() in (x.lower() for x in sysPath)


def _update_local_path(local_path):
    os.environ[str("PATH")] = PATHSEP.join(
        local_path
    )  # future lint: disable=blacklisted-function


def add(path, index=None, **kwargs):
    """
    Add the directory to the SYSTEM path in the index location. Returns
    ``True`` if successful, otherwise ``False``.

    path
        Directory to add to path

    index
        Optionally specify an index at which to insert the directory

    rehash : True
        If the registry was updated, and this value is set to ``True``, sends a
        WM_SETTINGCHANGE broadcast to refresh the environment variables. Set
        this to ``False`` to skip this broadcast.

    CLI Examples:

    .. code-block:: bash

        # Will add to the beginning of the path
        salt '*' win_path.add 'c:\\python27' 0

        # Will add to the end of the path
        salt '*' win_path.add 'c:\\python27' index='-1'
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    rehash_ = kwargs.pop("rehash", True)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    path = _normalize_dir(path)
    path_str = salt.utils.stringutils.to_str(path)
    system_path = get_path()

    # The current path should not have any unicode in it, but don't take any
    # chances.
    local_path = [
        salt.utils.stringutils.to_str(x) for x in os.environ["PATH"].split(PATHSEP)
    ]

    if index is not None:
        try:
            index = int(index)
        except (TypeError, ValueError):
            index = None

    def _check_path(dirs, path, index):
        """
        Check the dir list for the specified path, at the specified index, and
        make changes to the list if needed. Return True if changes were made to
        the list, otherwise return False.
        """
        dirs_lc = [x.lower() for x in dirs]
        try:
            # Check index with case normalized
            cur_index = dirs_lc.index(path.lower())
        except ValueError:
            cur_index = None

        num_dirs = len(dirs)

        # if pos is None, we don't care about where the directory is in the
        # PATH. If it is a number, then that number is the index to be used for
        # insertion (this number will be different from the index if the index
        # is less than -1, for reasons explained in the comments below). If it
        # is the string 'END', then the directory must be at the end of the
        # PATH, so it should be removed before appending if it is anywhere but
        # the end.
        pos = index
        if index is not None:
            if index >= num_dirs or index == -1:
                # Set pos to 'END' so we know that we're moving the directory
                # if it exists and isn't already at the end.
                pos = "END"
            elif index <= -num_dirs:
                # Negative index is too large, shift index to beginning of list
                index = pos = 0
            elif index < 0:
                # Negative indexes (other than -1 which is handled above) must
                # be inserted at index + 1 for the item  to end up in the
                # position you want, since list.insert() inserts before the
                # index passed to it. For example:
                #
                # >>> x = ['one', 'two', 'four', 'five']
                # >>> x.insert(-3, 'three')
                # >>> x
                # ['one', 'three', 'two', 'four', 'five']
                # >>> x = ['one', 'two', 'four', 'five']
                # >>> x.insert(-2, 'three')
                # >>> x
                # ['one', 'two', 'three', 'four', 'five']
                pos += 1

        if pos == "END":
            if cur_index is not None:
                if cur_index == num_dirs - 1:
                    # Directory is already in the desired location, no changes
                    # need to be made.
                    return False
                else:
                    # Remove from current location and add it to the end
                    dirs.pop(cur_index)
                    dirs.append(path)
                    return True
            else:
                # Doesn't exist in list, add it to the end
                dirs.append(path)
                return True
        elif index is None:
            # If index is None, that means that if the path is not already in
            # list, we will be appending it to the end instead of inserting it
            # somewhere in the middle.
            if cur_index is not None:
                # Directory is already in the PATH, no changes need to be made.
                return False
            else:
                # Directory not in the PATH, and we're not enforcing the index.
                # Append it to the list.
                dirs.append(path)
                return True
        else:
            if cur_index is not None:
                if (index < 0 and cur_index != (num_dirs + index)) or (
                    index >= 0 and cur_index != index
                ):
                    # Directory is present, but not at the desired index.
                    # Remove it from the non-normalized path list and insert it
                    # at the correct postition.
                    dirs.pop(cur_index)
                    dirs.insert(pos, path)
                    return True
                else:
                    # Directory is present and its position matches the desired
                    # index. No changes need to be made.
                    return False
            else:
                # Insert the path at the desired index.
                dirs.insert(pos, path)
                return True
        return False

    if _check_path(local_path, path_str, index):
        _update_local_path(local_path)

    if not _check_path(system_path, path, index):
        # No changes necessary
        return True

    # Move forward with registry update
    result = __salt__["reg.set_value"](
        HIVE, KEY, VNAME, ";".join(salt.utils.data.decode(system_path)), VTYPE
    )

    if result and rehash_:
        # Broadcast WM_SETTINGCHANGE to Windows if registry was updated
        return rehash()
    else:
        return result


def remove(path, **kwargs):
    r"""
    Remove the directory from the SYSTEM path

    Returns:
        boolean True if successful, False if unsuccessful

    rehash : True
        If the registry was updated, and this value is set to ``True``, sends a
        WM_SETTINGCHANGE broadcast to refresh the environment variables. Set
        this to ``False`` to skip this broadcast.

    CLI Example:

    .. code-block:: bash

        # Will remove C:\Python27 from the path
        salt '*' win_path.remove 'c:\\python27'
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    rehash_ = kwargs.pop("rehash", True)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    path = _normalize_dir(path)
    path_str = salt.utils.stringutils.to_str(path)
    system_path = get_path()

    # The current path should not have any unicode in it, but don't take any
    # chances.
    local_path = [
        salt.utils.stringutils.to_str(x) for x in os.environ["PATH"].split(PATHSEP)
    ]

    def _check_path(dirs, path):
        """
        Check the dir list for the specified path, and make changes to the list
        if needed. Return True if changes were made to the list, otherwise
        return False.
        """
        dirs_lc = [x.lower() for x in dirs]
        path_lc = path.lower()
        new_dirs = []
        for index, dirname in enumerate(dirs_lc):
            if path_lc != dirname:
                new_dirs.append(dirs[index])

        if len(new_dirs) != len(dirs):
            dirs[:] = new_dirs[:]
            return True
        else:
            return False

    if _check_path(local_path, path_str):
        _update_local_path(local_path)

    if not _check_path(system_path, path):
        # No changes necessary
        return True

    result = __salt__["reg.set_value"](
        HIVE, KEY, VNAME, ";".join(salt.utils.data.decode(system_path)), VTYPE
    )

    if result and rehash_:
        # Broadcast WM_SETTINGCHANGE to Windows if registry was updated
        return rehash()
    else:
        return result
