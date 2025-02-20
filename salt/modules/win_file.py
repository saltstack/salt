"""
Manage information about files on the minion, set/read user, group
data, modify the ACL of files/directories

:depends:   - win32api
            - win32file
            - win32con
            - salt.utils.win_dacl
"""

import errno
import logging
import os
import os.path
import pathlib
import stat
import sys
import tempfile

import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.user
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.modules.file import (
    __clean_tmp,
    _add_flags,
    _assert_occurrence,
    _binary_replace,
    _check_sig,
    _error,
    _get_bkroot,
    _get_eol,
    _get_flags,
    _mkstemp_copy,
    _regex_to_static,
    _set_line,
    _set_line_eol,
    _set_line_indent,
    _splitlines_preserving_trailing_newline,
    access,
    append,
    apply_template_on_contents,
    basename,
    blockreplace,
    check_file_meta,
    check_hash,
    check_managed,
    check_managed_changes,
    comment,
    comment_line,
    contains,
    contains_glob,
    contains_regex,
    copy,
    delete_backup,
    directory_exists,
    dirname,
    extract_hash,
    file_exists,
    find,
    get_diff,
    get_hash,
    get_managed,
    get_source_sum,
    get_sum,
    join,
    line,
    list_backups,
    list_backups_dir,
    lstat,
    manage_file,
)
from salt.modules.file import normpath as normpath_
from salt.modules.file import (
    pardir,
    patch,
    path_exists_glob,
    prepend,
    psed,
    read,
    readdir,
    readlink,
    rename,
    replace,
    restore_backup,
    rmdir,
    search,
    seek_read,
    seek_write,
    source_list,
    touch,
    truncate,
    uncomment,
    write,
)
from salt.utils.functools import namespaced_function

HAS_WINDOWS_MODULES = False
try:
    if salt.utils.platform.is_windows():
        import pywintypes
        import win32api
        import win32con
        import win32file
        import win32security

        import salt.platform.win

        HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

HAS_WIN_DACL = False
try:
    if salt.utils.platform.is_windows():
        import salt.utils.win_dacl

        HAS_WIN_DACL = True
except ImportError:
    HAS_WIN_DACL = False

if salt.utils.platform.is_windows():
    if HAS_WINDOWS_MODULES:
        # namespace functions from file.py
        replace = namespaced_function(replace, globals())
        search = namespaced_function(search, globals())
        _get_flags = namespaced_function(_get_flags, globals())
        _binary_replace = namespaced_function(_binary_replace, globals())
        _check_sig = namespaced_function(_check_sig, globals())
        _splitlines_preserving_trailing_newline = namespaced_function(
            _splitlines_preserving_trailing_newline, globals()
        )
        _error = namespaced_function(_error, globals())
        _get_bkroot = namespaced_function(_get_bkroot, globals())
        list_backups = namespaced_function(list_backups, globals())
        restore_backup = namespaced_function(restore_backup, globals())
        delete_backup = namespaced_function(delete_backup, globals())
        extract_hash = namespaced_function(extract_hash, globals())
        append = namespaced_function(append, globals())
        get_managed = namespaced_function(get_managed, globals())
        check_managed = namespaced_function(check_managed, globals())
        check_managed_changes = namespaced_function(check_managed_changes, globals())
        check_file_meta = namespaced_function(check_file_meta, globals())
        manage_file = namespaced_function(manage_file, globals())
        source_list = namespaced_function(source_list, globals())
        file_exists = namespaced_function(file_exists, globals())
        __clean_tmp = namespaced_function(__clean_tmp, globals())
        directory_exists = namespaced_function(directory_exists, globals())
        touch = namespaced_function(touch, globals())
        contains = namespaced_function(contains, globals())
        contains_regex = namespaced_function(contains_regex, globals())
        contains_glob = namespaced_function(contains_glob, globals())
        get_source_sum = namespaced_function(get_source_sum, globals())
        find = namespaced_function(find, globals())
        psed = namespaced_function(psed, globals())
        get_sum = namespaced_function(get_sum, globals())
        check_hash = namespaced_function(check_hash, globals())
        get_hash = namespaced_function(get_hash, globals())
        get_diff = namespaced_function(get_diff, globals())
        line = namespaced_function(line, globals())
        access = namespaced_function(access, globals())
        copy = namespaced_function(copy, globals())
        readdir = namespaced_function(readdir, globals())
        readlink = namespaced_function(readlink, globals())
        read = namespaced_function(read, globals())
        rmdir = namespaced_function(rmdir, globals())
        truncate = namespaced_function(truncate, globals())
        blockreplace = namespaced_function(blockreplace, globals())
        prepend = namespaced_function(prepend, globals())
        seek_read = namespaced_function(seek_read, globals())
        seek_write = namespaced_function(seek_write, globals())
        rename = namespaced_function(rename, globals())
        lstat = namespaced_function(lstat, globals())
        path_exists_glob = namespaced_function(path_exists_glob, globals())
        write = namespaced_function(write, globals())
        pardir = namespaced_function(pardir, globals())
        join = namespaced_function(join, globals())
        comment = namespaced_function(comment, globals())
        uncomment = namespaced_function(uncomment, globals())
        comment_line = namespaced_function(comment_line, globals())
        _regex_to_static = namespaced_function(_regex_to_static, globals())
        _set_line = namespaced_function(_set_line, globals())
        _set_line_indent = namespaced_function(_set_line_indent, globals())
        _set_line_eol = namespaced_function(_set_line_eol, globals())
        _get_eol = namespaced_function(_get_eol, globals())
        _mkstemp_copy = namespaced_function(_mkstemp_copy, globals())
        _add_flags = namespaced_function(_add_flags, globals())
        apply_template_on_contents = namespaced_function(
            apply_template_on_contents, globals()
        )
        dirname = namespaced_function(dirname, globals())
        basename = namespaced_function(basename, globals())
        list_backups_dir = namespaced_function(list_backups_dir, globals())
        normpath_ = namespaced_function(normpath_, globals())
        _assert_occurrence = namespaced_function(_assert_occurrence, globals())
        patch = namespaced_function(patch, globals())

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "file"


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows() or not HAS_WINDOWS_MODULES:
        return False, "Module win_file: Missing Win32 modules"
    if not HAS_WIN_DACL:
        return False, "Module win_file: Unable to load salt.utils.win_dacl"
    return __virtualname__


__outputter__ = {
    "touch": "txt",
    "append": "txt",
}

__func_alias__ = {
    "makedirs_": "makedirs",
    "normpath_": "normpath",
}


def _resolve_symlink(path, max_depth=64):
    """
    Resolves the given symlink path to its real path, up to a maximum of the
    `max_depth` parameter which defaults to 64.

    If the path is not a symlink path, it is simply returned.
    """
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError(
            "Symlinks are only supported on Windows Vista or later."
        )

    # make sure we don't get stuck in a symlink loop!
    paths_seen = {path}
    cur_depth = 0
    while is_link(path):
        path = readlink(path)
        if path in paths_seen:
            raise CommandExecutionError("The given path is involved in a symlink loop.")
        paths_seen.add(path)
        cur_depth += 1
        if cur_depth > max_depth:
            raise CommandExecutionError("Too many levels of symbolic links.")

    return path


def gid_to_group(gid):
    """
    Convert the group id to the group name on this system

    Under Windows, because groups are just another ACL entity, this function
    behaves the same as uid_to_user.

    For maintaining Windows systems, this function is superfluous and only
    exists for API compatibility with Unix. Use the uid_to_user function
    instead; an info level log entry will be generated if this function is used
    directly.

    Args:
        gid (str): The gid of the group

    Returns:
        str: The name of the group

    CLI Example:

    .. code-block:: bash

        salt '*' file.gid_to_group S-1-5-21-626487655-2533044672-482107328-1010
    """
    func_name = f"{__virtualname__}.gid_to_group"
    if __opts__.get("fun", "") == func_name:
        log.info(
            "The function %s should not be used on Windows systems; "
            "see function docs for details.",
            func_name,
        )

    return uid_to_user(gid)


def group_to_gid(group):
    """
    Convert the group to the gid on this system

    Under Windows, because groups are just another ACL entity, this function
    behaves the same as user_to_uid, except if None is given, '' is returned.

    For maintaining Windows systems, this function is superfluous and only
    exists for API compatibility with Unix. Use the user_to_uid function
    instead; an info level log entry will be generated if this function is used
    directly.

    Args:
        group (str): The name of the group

    Returns:
        str: The gid of the group

    CLI Example:

    .. code-block:: bash

        salt '*' file.group_to_gid administrators
    """
    func_name = f"{__virtualname__}.group_to_gid"
    if __opts__.get("fun", "") == func_name:
        log.info(
            "The function %s should not be used on Windows systems; "
            "see function docs for details.",
            func_name,
        )

    if group is None:
        return ""

    return salt.utils.win_dacl.get_sid_string(group)


def get_pgid(path, follow_symlinks=True):
    """
    Return the id of the primary group that owns a given file (Windows only)

    This function will return the rarely used primary group of a file. This
    generally has no bearing on permissions unless intentionally configured
    and is most commonly used to provide Unix compatibility (e.g. Services
    For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The gid of the primary group

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_pgid c:\\temp\\test.txt
    """
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    group_name = salt.utils.win_dacl.get_primary_group(path)
    return salt.utils.win_dacl.get_sid_string(group_name)


def get_pgroup(path, follow_symlinks=True):
    """
    Return the name of the primary group that owns a given file (Windows only)

    This function will return the rarely used primary group of a file. This
    generally has no bearing on permissions unless intentionally configured
    and is most commonly used to provide Unix compatibility (e.g. Services
    For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    The return value may be 'None', e.g. if the user is not on a domain. This is
    a valid group - do not confuse this with the Salt/Python value of None which
    means no value was returned. To be certain, use the `get_pgid` function
    which will return the SID, including for the system 'None' group.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The name of the primary group

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_pgroup c:\\temp\\test.txt
    """
    return uid_to_user(get_pgid(path, follow_symlinks))


def get_gid(path, follow_symlinks=True):
    """
    Return the id of the group that owns a given file

    Under Windows, this will return the uid of the file.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps this function to provide functionality that
    somewhat resembles Unix behavior for API compatibility reasons. When
    managing Windows systems, this function is superfluous and will generate
    an info level log entry if used directly.

    If you do actually want to access the 'primary group' of a file, use
    `file.get_pgid`.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The gid of the owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_gid c:\\temp\\test.txt
    """
    func_name = f"{__virtualname__}.get_gid"
    if __opts__.get("fun", "") == func_name:
        log.info(
            "The function %s should not be used on Windows systems; "
            "see function docs for details. The value returned is the "
            "uid.",
            func_name,
        )

    return get_uid(path, follow_symlinks)


def get_group(path, follow_symlinks=True):
    """
    Return the group that owns a given file

    Under Windows, this will return the user (owner) of the file.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps this function to provide functionality that
    somewhat resembles Unix behavior for API compatibility reasons. When
    managing Windows systems, this function is superfluous and will generate
    an info level log entry if used directly.

    If you do actually want to access the 'primary group' of a file, use
    `file.get_pgroup`.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The name of the owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_group c:\\temp\\test.txt
    """
    func_name = f"{__virtualname__}.get_group"
    if __opts__.get("fun", "") == func_name:
        log.info(
            "The function %s should not be used on Windows systems; "
            "see function docs for details. The value returned is the "
            "user (owner).",
            func_name,
        )

    return get_user(path, follow_symlinks)


def uid_to_user(uid):
    """
    Convert a uid to a user name

    Args:
        uid (str): The user id to lookup

    Returns:
        str: The name of the user

    CLI Example:

    .. code-block:: bash

        salt '*' file.uid_to_user S-1-5-21-626487655-2533044672-482107328-1010
    """
    if uid is None or uid == "":
        return ""

    return salt.utils.win_dacl.get_name(uid)


def user_to_uid(user):
    """
    Convert user name to a uid

    Args:
        user (str): The user to lookup

    Returns:
        str: The user id of the user

    CLI Example:

    .. code-block:: bash

        salt '*' file.user_to_uid myusername
    """
    if user is None:
        user = salt.utils.user.get_user()

    return salt.utils.win_dacl.get_sid_string(user)


def get_uid(path, follow_symlinks=True):
    """
    Return the id of the user that owns a given file

    Symlinks are followed by default to mimic Unix behavior. Specify
    `follow_symlinks=False` to turn off this behavior.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The uid of the owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_uid c:\\temp\\test.txt
        salt '*' file.get_uid c:\\temp\\test.txt follow_symlinks=False
    """
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    owner_sid = salt.utils.win_dacl.get_owner(path)
    return salt.utils.win_dacl.get_sid_string(owner_sid)


def get_user(path, follow_symlinks=True):
    """
    Return the user that owns a given file

    Symlinks are followed by default to mimic Unix behavior. Specify
    `follow_symlinks=False` to turn off this behavior.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The name of the owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_user c:\\temp\\test.txt
        salt '*' file.get_user c:\\temp\\test.txt follow_symlinks=False
    """
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    return salt.utils.win_dacl.get_owner(path)


def get_mode(path):
    """
    Return the mode of a file

    Right now we're just returning None because Windows' doesn't have a mode
    like Linux

    Args:
        path (str): The path to the file or directory

    Returns:
        None

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_mode /etc/passwd
    """
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    func_name = f"{__virtualname__}.get_mode"
    if __opts__.get("fun", "") == func_name:
        log.info(
            "The function %s should not be used on Windows systems; "
            "see function docs for details. The value returned is "
            "always None.",
            func_name,
        )

    return None


def lchown(path, user, group=None, pgroup=None):
    """
    Chown a file, pass the file the desired user and group without following any
    symlinks.

    Under Windows, the group parameter will be ignored.

    This is because while files in Windows do have a 'primary group'
    property, this is rarely used.  It generally has no bearing on
    permissions unless intentionally configured and is most commonly used to
    provide Unix compatibility (e.g. Services For Unix, NFS services).

    If you do want to change the 'primary group' property and understand the
    implications, pass the Windows only parameter, pgroup, instead.

    To set the primary group to 'None', it must be specified in quotes.
    Otherwise Salt will interpret it as the Python value of None and no primary
    group changes will occur. See the example below.

    Args:
        path (str): The path to the file or directory
        user (str): The name of the user to own the file
        group (str): The group (not used)
        pgroup (str): The primary group to assign

    Returns:
        bool: True if successful, otherwise error

    CLI Example:

    .. code-block:: bash

        salt '*' file.lchown c:\\temp\\test.txt myusername
        salt '*' file.lchown c:\\temp\\test.txt myusername pgroup=Administrators
        salt '*' file.lchown c:\\temp\\test.txt myusername "pgroup='None'"
    """
    if group:
        func_name = f"{__virtualname__}.lchown"
        if __opts__.get("fun", "") == func_name:
            log.info(
                "The group parameter has no effect when using %s on "
                "Windows systems; see function docs for details.",
                func_name,
            )
        log.debug("win_file.py %s Ignoring the group parameter for %s", func_name, path)
        group = None

    return chown(path, user, group, pgroup, follow_symlinks=False)


def chown(path, user, group=None, pgroup=None, follow_symlinks=True):
    """
    Chown a file, pass the file the desired user and group

    Under Windows, the group parameter will be ignored.

    This is because while files in Windows do have a 'primary group'
    property, this is rarely used.  It generally has no bearing on
    permissions unless intentionally configured and is most commonly used to
    provide Unix compatibility (e.g. Services For Unix, NFS services).

    If you do want to change the 'primary group' property and understand the
    implications, pass the Windows only parameter, pgroup, instead.

    Args:
        path (str): The path to the file or directory
        user (str): The name of the user to own the file
        group (str): The group (not used)
        pgroup (str): The primary group to assign
        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        bool: True if successful, otherwise error

    CLI Example:

    .. code-block:: bash

        salt '*' file.chown c:\\temp\\test.txt myusername
        salt '*' file.chown c:\\temp\\test.txt myusername pgroup=Administrators
        salt '*' file.chown c:\\temp\\test.txt myusername "pgroup='None'"
    """
    # the group parameter is not used; only provided for API compatibility
    if group is not None:
        func_name = f"{__virtualname__}.chown"
        if __opts__.get("fun", "") == func_name:
            log.info(
                "The group parameter has no effect when using %s on "
                "Windows systems; see function docs for details.",
                func_name,
            )
        log.debug("win_file.py %s Ignoring the group parameter for %s", func_name, path)

    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    salt.utils.win_dacl.set_owner(path, user)
    if pgroup:
        salt.utils.win_dacl.set_primary_group(path, pgroup)

    return True


def chpgrp(path, group):
    """
    Change the group of a file

    Under Windows, this will set the rarely used primary group of a file.
    This generally has no bearing on permissions unless intentionally
    configured and is most commonly used to provide Unix compatibility (e.g.
    Services For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    Args:
        path (str): The path to the file or directory
        pgroup (str): The primary group to assign

    Returns:
        bool: True if successful, otherwise error

    CLI Example:

    .. code-block:: bash

        salt '*' file.chpgrp c:\\temp\\test.txt Administrators
        salt '*' file.chpgrp c:\\temp\\test.txt "'None'"
    """
    return salt.utils.win_dacl.set_primary_group(path, group)


def chgrp(path, group):
    """
    Change the group of a file

    Under Windows, this will do nothing.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps this function to do nothing while still being
    compatible with Unix behavior. When managing Windows systems,
    this function is superfluous and will generate an info level log entry if
    used directly.

    If you do actually want to set the 'primary group' of a file, use ``file
    .chpgrp``.

    To set group permissions use ``file.set_perms``

    Args:
        path (str): The path to the file or directory
        group (str): The group (unused)

    Returns:
        None

    CLI Example:

    .. code-block:: bash

        salt '*' file.chgrp c:\\temp\\test.txt administrators
    """
    func_name = f"{__virtualname__}.chgrp"
    if __opts__.get("fun", "") == func_name:
        log.info(
            "The function %s should not be used on Windows systems; see "
            "function docs for details.",
            func_name,
        )
    log.debug("win_file.py %s Doing nothing for %s", func_name, path)

    return None


def stats(path, hash_type="sha256", follow_symlinks=True):
    """
    Return a dict containing the stats about a given file

    Under Windows, `gid` will equal `uid` and `group` will equal `user`.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps these properties to keep some kind of
    compatibility with Unix behavior. If the 'primary group' is required, it
    can be accessed in the `pgroup` and `pgid` properties.

    Args:
        path (str): The path to the file or directory
        hash_type (str): The type of hash to return
        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        dict: A dictionary of file/directory stats

    CLI Example:

    .. code-block:: bash

        salt '*' file.stats /etc/passwd
    """
    # This is to mirror the behavior of file.py. `check_file_meta` expects an
    # empty dictionary when the file does not exist
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    pstat = os.stat(path)

    ret = {}
    ret["inode"] = pstat.st_ino
    # don't need to resolve symlinks again because we've already done that
    ret["uid"] = get_uid(path, follow_symlinks=False)
    # maintain the illusion that group is the same as user as states need this
    ret["gid"] = ret["uid"]
    ret["user"] = uid_to_user(ret["uid"])
    ret["group"] = ret["user"]
    ret["pgid"] = get_pgid(path, follow_symlinks)
    ret["pgroup"] = gid_to_group(ret["pgid"])
    ret["atime"] = pstat.st_atime
    ret["mtime"] = pstat.st_mtime
    ret["ctime"] = pstat.st_ctime
    ret["size"] = pstat.st_size
    ret["mode"] = salt.utils.files.normalize_mode(oct(stat.S_IMODE(pstat.st_mode)))
    if hash_type:
        ret["sum"] = get_sum(path, hash_type)
    ret["type"] = "file"
    if stat.S_ISDIR(pstat.st_mode):
        ret["type"] = "dir"
    if stat.S_ISCHR(pstat.st_mode):
        ret["type"] = "char"
    if stat.S_ISBLK(pstat.st_mode):
        ret["type"] = "block"
    if stat.S_ISREG(pstat.st_mode):
        ret["type"] = "file"
    if stat.S_ISLNK(pstat.st_mode):
        ret["type"] = "link"
    if stat.S_ISFIFO(pstat.st_mode):
        ret["type"] = "pipe"
    if stat.S_ISSOCK(pstat.st_mode):
        ret["type"] = "socket"
    ret["target"] = os.path.realpath(path)
    return ret


def _get_version_os(flags):
    """
    Helper function to parse the OS data

    Args:
        flags: The flags as returned by the GetFileVersionInfo function

    Returns:
        list: A list of Operating system properties found in the flag
    """
    file_os = []
    file_os_flags = {
        0x00000001: "16-bit Windows",
        0x00000002: "16-bit Presentation Manager",
        0x00000003: "32-bit Presentation Manager",
        0x00000004: "32-bit Windows",
        0x00010000: "MS-DOS",
        0x00020000: "16-bit OS/2",
        0x00030000: "32-bit OS/2",
        0x00040000: "Windows NT",
    }
    for item in file_os_flags:
        if item & flags == item:
            file_os.append(file_os_flags[item])
    return file_os


def _get_version_type(file_type, file_subtype):
    ret_type = None
    file_types = {
        0x00000001: "Application",
        0x00000002: "DLL",
        0x00000003: "Driver",
        0x00000004: "Font",
        0x00000005: "Virtual Device",
        0x00000007: "Static Link Library",
    }
    driver_subtypes = {
        0x00000001: "Printer",
        0x00000002: "Keyboard",
        0x00000003: "Language",
        0x00000004: "Display",
        0x00000005: "Mouse",
        0x00000006: "Network",
        0x00000007: "System",
        0x00000008: "Installable",
        0x00000009: "Sound",
        0x0000000A: "Communications",
        0x0000000C: "Versioned Printer",
    }
    font_subtypes = {
        0x00000001: "Raster",
        0x00000002: "Vector",
        0x00000003: "TrueType",
    }
    if file_type in file_types:
        ret_type = file_types[file_type]

    if ret_type == "Driver":
        if file_subtype in driver_subtypes:
            ret_type = f"{driver_subtypes[file_subtype]} Driver"
    if ret_type == "Font":
        if file_subtype in font_subtypes:
            ret_type = f"{font_subtypes[file_subtype]} Font"
    if ret_type == "Virtual Device":
        # The Virtual Device Identifier
        ret_type = f"Virtual Device: {file_subtype}"
    return ret_type


def _get_version(path, fixed_info=None):
    """
    Get's the version of the file passed in path, or the fixed_info object if
    passed.

    Args:

        path (str): The path to the file

        fixed_info (obj): The fixed info object returned by the
            GetFileVersionInfo function

    Returns:
        str: The version of the file
    """
    if not fixed_info:
        try:
            # Backslash returns a VS_FIXEDFILEINFO structure
            # https://docs.microsoft.com/en-us/windows/win32/api/verrsrc/ns-verrsrc-vs_fixedfileinfo
            fixed_info = win32api.GetFileVersionInfo(path, "\\")
        except pywintypes.error:
            log.debug("No version info found: %s", path)
            return ""

    return "{}.{}.{}.{}".format(
        win32api.HIWORD(fixed_info["FileVersionMS"]),
        win32api.LOWORD(fixed_info["FileVersionMS"]),
        win32api.HIWORD(fixed_info["FileVersionLS"]),
        win32api.LOWORD(fixed_info["FileVersionLS"]),
    )


def version(path):
    r"""
    .. versionadded:: 3005

    Get the version of a file.

    .. note::
        Not all files have version information. The following are common file
        types that contain version information:

            - .exe
            - .dll
            - .sys

    Args:
        path (str): The path to the file.

    Returns:
        str: The version of the file if the file contains it. Otherwise, an
            empty string will be returned.

    Raises:
        CommandExecutionError: If the file does not exist
        CommandExecutionError: If the path is not a file

    CLI Example:

    .. code-block:: bash

        salt * file.version C:\Windows\notepad.exe
    """
    # Input validation
    if not os.path.exists(path):
        raise CommandExecutionError(f"File not found: {path}")
    if os.path.isdir(path):
        raise CommandExecutionError(f"Not a file: {path}")
    return _get_version(path)


def version_details(path):
    r"""
    .. versionadded:: 3005

    Get file details for a file. Similar to what's in the details tab on the
    file properties.

    .. note::
        Not all files have version information. The following are common file
        types that contain version information:

            - .exe
            - .dll
            - .sys

    Args:
        path (str): The path to the file.

    Returns:
        dict: A dictionary containing details about the file related to version.
            An empty dictionary if the file contains no version information.

    Raises:
        CommandExecutionError: If the file does not exist
        CommandExecutionError: If the path is not a file

    CLI Example:

    .. code-block:: bash

        salt * file.version_details C:\Windows\notepad.exe
    """
    # Input validation
    if not os.path.exists(path):
        raise CommandExecutionError(f"File not found: {path}")
    if os.path.isdir(path):
        raise CommandExecutionError(f"Not a file: {path}")

    ret = {}
    try:
        # Backslash returns a VS_FIXEDFILEINFO structure
        # https://docs.microsoft.com/en-us/windows/win32/api/verrsrc/ns-verrsrc-vs_fixedfileinfo
        fixed_info = win32api.GetFileVersionInfo(path, "\\")
    except pywintypes.error:
        log.debug("No version info found: %s", path)
        return ret

    ret["Version"] = _get_version(path, fixed_info)
    ret["OperatingSystem"] = _get_version_os(fixed_info["FileOS"])
    ret["FileType"] = _get_version_type(
        fixed_info["FileType"], fixed_info["FileSubtype"]
    )

    try:
        # \VarFileInfo\Translation returns a list of available
        # (language, codepage) pairs that can be used to retrieve string info.
        # We only care about the first pair.
        # https://docs.microsoft.com/en-us/windows/win32/menurc/varfileinfo-block
        language, codepage = win32api.GetFileVersionInfo(
            path, "\\VarFileInfo\\Translation"
        )[0]
    except pywintypes.error:
        log.debug("No extended version info found: %s", path)
        return ret

    # All other properties are in the StringFileInfo block
    # \StringFileInfo\<hex language><hex codepage>\<property name>
    # https://docs.microsoft.com/en-us/windows/win32/menurc/stringfileinfo-block
    property_names = (
        "Comments",
        "CompanyName",
        "FileDescription",
        "FileVersion",
        "InternalName",
        "LegalCopyright",
        "LegalTrademarks",
        "OriginalFilename",
        "PrivateBuild",
        "ProductName",
        "ProductVersion",
        "SpecialBuild",
    )
    for prop_name in property_names:
        str_info_path = "\\StringFileInfo\\{:04X}{:04X}\\{}".format(
            language, codepage, prop_name
        )
        try:
            ret[prop_name] = win32api.GetFileVersionInfo(path, str_info_path)
        except pywintypes.error:
            pass

    return ret


def get_attributes(path):
    """
    Return a dictionary object with the Windows
    file attributes for a file.

    Args:
        path (str): The path to the file or directory

    Returns:
        dict: A dictionary of file attributes

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_attributes c:\\temp\\a.txt
    """
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    # set up dictionary for attribute values
    attributes = {}

    # Get cumulative int value of attributes
    intAttributes = win32file.GetFileAttributes(path)

    # Assign individual attributes
    attributes["archive"] = (intAttributes & 32) == 32
    attributes["reparsePoint"] = (intAttributes & 1024) == 1024
    attributes["compressed"] = (intAttributes & 2048) == 2048
    attributes["directory"] = (intAttributes & 16) == 16
    attributes["encrypted"] = (intAttributes & 16384) == 16384
    attributes["hidden"] = (intAttributes & 2) == 2
    attributes["normal"] = (intAttributes & 128) == 128
    attributes["notIndexed"] = (intAttributes & 8192) == 8192
    attributes["offline"] = (intAttributes & 4096) == 4096
    attributes["readonly"] = (intAttributes & 1) == 1
    attributes["system"] = (intAttributes & 4) == 4
    attributes["temporary"] = (intAttributes & 256) == 256

    # check if it's a Mounted Volume
    attributes["mountedVolume"] = False
    if attributes["reparsePoint"] is True and attributes["directory"] is True:
        fileIterator = win32file.FindFilesIterator(path)
        findDataTuple = next(fileIterator)
        if findDataTuple[6] == 0xA0000003:
            attributes["mountedVolume"] = True
    # check if it's a soft (symbolic) link

    # Note:  os.path.islink() does not work in
    #   Python 2.7 for the Windows NTFS file system.
    #   The following code does, however, work (tested in Windows 8)

    attributes["symbolicLink"] = False
    if attributes["reparsePoint"] is True:
        fileIterator = win32file.FindFilesIterator(path)
        findDataTuple = next(fileIterator)
        if findDataTuple[6] == 0xA000000C:
            attributes["symbolicLink"] = True

    return attributes


def set_attributes(
    path,
    archive=None,
    hidden=None,
    normal=None,
    notIndexed=None,
    readonly=None,
    system=None,
    temporary=None,
):
    """
    Set file attributes for a file.  Note that the normal attribute
    means that all others are false.  So setting it will clear all others.

    Args:
        path (str): The path to the file or directory
        archive (bool): Sets the archive attribute. Default is None
        hidden (bool): Sets the hidden attribute. Default is None
        normal (bool):
            Resets the file attributes. Cannot be used in conjunction with any
            other attribute. Default is None
        notIndexed (bool): Sets the indexed attribute. Default is None
        readonly (bool): Sets the readonly attribute. Default is None
        system (bool): Sets the system attribute. Default is None
        temporary (bool): Sets the temporary attribute. Default is None

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_attributes c:\\temp\\a.txt normal=True
        salt '*' file.set_attributes c:\\temp\\a.txt readonly=True hidden=True
    """
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    if normal:
        if archive or hidden or notIndexed or readonly or system or temporary:
            raise CommandExecutionError(
                "Normal attribute may not be used with any other attributes"
            )
        ret = win32file.SetFileAttributes(path, 128)
        return True if ret is None else False

    # Get current attributes
    intAttributes = win32file.GetFileAttributes(path)

    # individually set or clear bits for appropriate attributes
    if archive is not None:
        if archive:
            intAttributes |= 0x20
        else:
            intAttributes &= 0xFFDF
    if hidden is not None:
        if hidden:
            intAttributes |= 0x2
        else:
            intAttributes &= 0xFFFD
    if notIndexed is not None:
        if notIndexed:
            intAttributes |= 0x2000
        else:
            intAttributes &= 0xDFFF
    if readonly is not None:
        if readonly:
            intAttributes |= 0x1
        else:
            intAttributes &= 0xFFFE
    if system is not None:
        if system:
            intAttributes |= 0x4
        else:
            intAttributes &= 0xFFFB
    if temporary is not None:
        if temporary:
            intAttributes |= 0x100
        else:
            intAttributes &= 0xFEFF

    ret = win32file.SetFileAttributes(path, intAttributes)
    return True if ret is None else False


def set_mode(path, mode):
    """
    Set the mode of a file

    This just calls get_mode, which returns None because we don't use mode on
    Windows

    Args:
        path: The path to the file or directory
        mode: The mode (not used)

    Returns:
        None

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_mode /etc/passwd 0644
    """
    func_name = f"{__virtualname__}.set_mode"
    if __opts__.get("fun", "") == func_name:
        log.info(
            "The function %s should not be used on Windows systems; "
            "see function docs for details. The value returned is "
            "always None. Use set_perms instead.",
            func_name,
        )

    return get_mode(path)


def remove(path, force=False):
    """
    Remove the named file or directory

    Args:
        path (str): The path to the file or directory to remove.
        force (bool): Remove even if marked Read-Only. Default is False

    Returns:
        bool: True if successful, False if unsuccessful

    CLI Example:

    .. code-block:: bash

        salt '*' file.remove C:\\Temp
    """
    # This must be a recursive function in windows to properly deal with
    # Symlinks. The shutil.rmtree function will remove the contents of
    # the Symlink source in windows.

    path = pathlib.Path(os.path.expanduser(path))

    if not path.is_absolute():
        raise SaltInvocationError(f"File path must be absolute: {path}")

    # Does the file/folder exists
    if not path.exists() and not path.is_symlink():
        raise CommandExecutionError(f"Path not found: {path}")

    # Remove ReadOnly Attribute
    file_attributes = win32api.GetFileAttributes(str(path))
    if force:
        # Get current file attributes
        win32api.SetFileAttributes(str(path), win32con.FILE_ATTRIBUTE_NORMAL)

    try:
        if path.is_file() or path.is_symlink():
            # A file and a symlinked file are removed the same way
            path.unlink()
        else:
            # Twangboy: This is for troubleshooting
            is_dir = os.path.isdir(path)
            exists = os.path.exists(path)
            # This is a directory, list its contents and remove them recursively
            for child in path.iterdir():
                # If it's a normal directory, recurse to remove its contents
                remove(str(child), force)
            # rmdir will work now because the directory is empty
            path.rmdir()
    except OSError as exc:
        if force:
            # Reset attributes to the original if delete fails.
            win32api.SetFileAttributes(str(path), file_attributes)
        raise CommandExecutionError(f"Could not remove '{path}': {exc}")

    return True


def symlink(src, link, force=False, atomic=False, follow_symlinks=True):
    """
    Create a symbolic link to a file

    This is only supported with Windows Vista or later and must be executed by
    a user with the SeCreateSymbolicLink privilege.

    The behavior of this function matches the Unix equivalent, with one
    exception - invalid symlinks cannot be created. The source path must exist.
    If it doesn't, an error will be raised.

    Args:

        src (str): The path to a file or directory

        link (str): The path to the link. Must be an absolute path

        force (bool):
            Overwrite an existing symlink with the same name
            .. versionadded:: 3005

        atomic (bool):
            Use atomic file operations to create the symlink
            .. versionadded:: 3006.0

        follow_symlinks (bool):
            If set to ``False``, use ``os.path.lexists()`` for existence checks
            instead of ``os.path.exists()``.
            .. versionadded:: 3007.0

    Returns:

        bool: ``True`` if successful, otherwise raises ``CommandExecutionError``

    CLI Example:

    .. code-block:: bash

        salt '*' file.symlink /path/to/file /path/to/link
    """
    # When Python 3.2 or later becomes the minimum version, this function can be
    # replaced with the built-in os.symlink function, which supports Windows.
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError(
            "Symlinks are only supported on Windows Vista or later."
        )

    if not os.path.isabs(link):
        raise SaltInvocationError(f"Link path must be absolute: {link}")

    if follow_symlinks:
        exists = os.path.exists
    else:
        exists = os.path.lexists

    if os.path.islink(link):
        try:
            if os.path.normpath(salt.utils.path.readlink(link)) == os.path.normpath(
                src
            ):
                log.debug("link already in correct state: %s -> %s", link, src)
                return True
        except OSError:
            pass

        if not force and not atomic:
            msg = f"Found existing symlink: {link}"
            raise CommandExecutionError(msg)

    if exists(link) and not force and not atomic:
        msg = f"Existing path is not a symlink: {link}"
        raise CommandExecutionError(msg)

    # ensure paths are using the right slashes
    src = os.path.normpath(src)
    link = os.path.normpath(link)

    is_dir = os.path.isdir(src)

    # Elevate the token from the current process
    desired_access = win32security.TOKEN_QUERY | win32security.TOKEN_ADJUST_PRIVILEGES
    th = win32security.OpenProcessToken(win32api.GetCurrentProcess(), desired_access)
    salt.platform.win.elevate_token(th)

    if (os.path.islink(link) or exists(link)) and force and not atomic:
        os.unlink(link)
    elif atomic:
        link_dir = os.path.dirname(link)
        retry = 0
        while retry < 5:
            temp_link = tempfile.mktemp(dir=link_dir)
            try:
                win32file.CreateSymbolicLink(temp_link, src, int(is_dir))
                break
            except win32file.error:
                retry += 1
        try:
            win32file.MoveFileEx(
                temp_link,
                link,
                win32file.MOVEFILE_REPLACE_EXISTING | win32file.MOVEFILE_WRITE_THROUGH,
            )
            return True
        except win32file.error:
            os.remove(temp_link)
            raise CommandExecutionError(f"Could not create '{link}'")

    try:
        win32file.CreateSymbolicLink(link, src, int(is_dir))
        return True
    except win32file.error as exc:
        raise CommandExecutionError(
            f"Could not create '{link}' - [{exc.winerror}] {exc.strerror}"
        )


def is_link(path):
    """
    Check if the path is a symlink

    This is only supported on Windows Vista or later.

    Inline with Unix behavior, this function will raise an error if the path
    is not a symlink, however, the error raised will be a SaltInvocationError,
    not an OSError.

    Args:
        path (str): The path to a file or directory

    Returns:
        bool: True if path is a symlink, otherwise False

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_link /path/to/link
    """
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError(
            "Symlinks are only supported on Windows Vista or later."
        )

    try:
        return salt.utils.path.islink(path)
    except Exception as exc:  # pylint: disable=broad-except
        raise CommandExecutionError(exc)


def mkdir(
    path, owner=None, grant_perms=None, deny_perms=None, inheritance=True, reset=False
):
    """
    Ensure that the directory is available and permissions are set.

    Args:

        path (str):
            The full path to the directory.

        owner (str):
            The owner of the directory. If not passed, it will be the account
            that created the directory, likely SYSTEM

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default is
            ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter,
            ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

        inheritance (bool):
            If True the object will inherit permissions from the parent, if
            ``False``, inheritance will be disabled. Inheritance setting will
            not apply to parent directories if they must be created.

        reset (bool):
            If ``True`` the existing DACL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If unsuccessful

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.mkdir C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.mkdir C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.mkdir C:\\Temp\\ Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_only'}}"
    """
    # Make sure the drive is valid
    drive = os.path.splitdrive(path)[0]
    if not os.path.isdir(drive):
        raise CommandExecutionError(f"Drive {drive} is not mapped")

    path = os.path.expanduser(path)
    path = os.path.expandvars(path)

    if not os.path.isdir(path):

        try:
            # Make the directory
            os.mkdir(path)

            # Set owner
            if owner:
                salt.utils.win_dacl.set_owner(obj_name=path, principal=owner)

            # Set permissions
            salt.utils.win_dacl.set_perms(
                obj_name=path,
                obj_type="file",
                grant_perms=grant_perms,
                deny_perms=deny_perms,
                inheritance=inheritance,
                reset=reset,
            )

        except OSError as exc:
            raise CommandExecutionError(exc)

    return True


def makedirs_(
    path, owner=None, grant_perms=None, deny_perms=None, inheritance=True, reset=False
):
    """
    Ensure that the parent directory containing this path is available.

    Args:

        path (str):
            The full path to the directory.

            .. note::

                The path must end with a trailing slash otherwise the
                directory(s) will be created up to the parent directory. For
                example if path is ``C:\\temp\\test``, then it would be treated
                as ``C:\\temp\\`` but if the path ends with a trailing slash
                like ``C:\\temp\\test\\``, then it would be treated as
                ``C:\\temp\\test\\``.

        owner (str):
            The owner of the directory. If not passed, it will be the account
            that created the directory, likely SYSTEM.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default is
            ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter, ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

        inheritance (bool):
            If True the object will inherit permissions from the parent, if
            False, inheritance will be disabled. Inheritance setting will not
            apply to parent directories if they must be created.

        reset (bool):
            If ``True`` the existing DACL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If unsuccessful

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.makedirs C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.makedirs C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.makedirs C:\\Temp\\ Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_only'}}"
    """
    path = os.path.expanduser(path)

    # walk up the directory structure until we find the first existing
    # directory
    dirname = os.path.normpath(os.path.dirname(path))

    if os.path.isdir(dirname):
        # There's nothing for us to do
        msg = f"Directory '{dirname}' already exists"
        log.debug(msg)
        return msg

    if os.path.exists(dirname):
        msg = f"The path '{dirname}' already exists and is not a directory"
        log.debug(msg)
        return msg

    directories_to_create = []
    while True:
        if os.path.isdir(dirname):
            break

        directories_to_create.append(dirname)
        current_dirname = dirname
        dirname = os.path.dirname(dirname)

        if current_dirname == dirname:
            raise SaltInvocationError(
                "Recursive creation for path '{}' would result in an "
                "infinite loop. Please use an absolute path.".format(dirname)
            )

    # create parent directories from the topmost to the most deeply nested one
    directories_to_create.reverse()
    for directory_to_create in directories_to_create:
        # all directories have the user, group and mode set!!
        log.debug("Creating directory: %s", directory_to_create)
        mkdir(
            path=directory_to_create,
            owner=owner,
            grant_perms=grant_perms,
            deny_perms=deny_perms,
            inheritance=inheritance,
            reset=reset,
        )

    return True


def makedirs_perms(
    path, owner=None, grant_perms=None, deny_perms=None, inheritance=True, reset=True
):
    """
    Set owner and permissions for each directory created.

    Args:

        path (str):
            The full path to the directory.

        owner (str):
            The owner of the directory. If not passed, it will be the account
            that created the directory, likely SYSTEM.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default is
            ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter, ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

        inheritance (bool):
            If ``True`` the object will inherit permissions from the parent, if
            ``False``, inheritance will be disabled. Inheritance setting will
            not apply to parent directories if they must be created

        reset (bool):
            If ``True`` the existing DACL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful, otherwise raises an error

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.makedirs_perms C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.makedirs_perms C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.makedirs_perms C:\\Temp\\ Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_files'}}"
    """
    # Expand any environment variables
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)

    # Get parent directory (head)
    head, tail = os.path.split(path)

    # If tail is empty, split head
    if not tail:
        head, tail = os.path.split(head)

    # If head and tail are defined and head is not there, recurse
    if head and tail and not os.path.exists(head):
        try:
            # Create the directory here, set inherited True because this is a
            # parent directory, the inheritance setting will only apply to the
            # target directory. Reset will be False as we only want to reset
            # the permissions on the target directory
            makedirs_perms(
                path=head,
                owner=owner,
                grant_perms=grant_perms,
                deny_perms=deny_perms,
                inheritance=True,
                reset=False,
            )
        except OSError as exc:
            # be happy if someone already created the path
            if exc.errno != errno.EEXIST:
                raise
        if tail == os.curdir:  # xxx/newdir/. exists if xxx/newdir exists
            return {}

    # Make the directory
    mkdir(
        path=path,
        owner=owner,
        grant_perms=grant_perms,
        deny_perms=deny_perms,
        inheritance=inheritance,
        reset=reset,
    )

    return True


def check_perms(
    path,
    ret=None,
    owner=None,
    grant_perms=None,
    deny_perms=None,
    inheritance=True,
    reset=False,
):
    """
    Check owner and permissions for the passed directory. This function checks
    the permissions and sets them, returning the changes made. Used by the file
    state to populate the return dict

    Args:

        path (str):
            The full path to the directory.

        ret (dict):
            A dictionary to append changes to and return. If not passed, will
            create a new dictionary to return.

        owner (str):
            The owner to set for the directory.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            check/grant, ie: ``{'user': {'perms': 'basic_permission'}}``.
            Default is ``None``.

        deny_perms (dict):
            A dictionary containing the user/group and permissions to
            check/deny. Default is ``None``.

        inheritance (bool):
            ``True will check if inheritance is enabled and enable it. ``False``
            will check if inheritance is disabled and disable it. Default is
            ``True``.

        reset (bool):
            ``True`` will show what permissions will be removed by resetting the
            DACL. ``False`` will do nothing. Default is ``False``.

    Returns:
        dict: A dictionary of changes that have been made

    CLI Example:

    .. code-block:: bash

        # To see changes to ``C:\\Temp`` if the 'Users' group is given 'read & execute' permissions.
        salt '*' file.check_perms C:\\Temp\\ {} Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.check_perms C:\\Temp\\ {} Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.check_perms C:\\Temp\\ {} Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'files_only'}}"
    """
    if not os.path.exists(path):
        raise CommandExecutionError(f"Path not found: {path}")

    path = os.path.expanduser(path)

    return salt.utils.win_dacl.check_perms(
        obj_name=path,
        obj_type="file",
        ret=ret,
        owner=owner,
        grant_perms=grant_perms,
        deny_perms=deny_perms,
        inheritance=inheritance,
        reset=reset,
        test_mode=__opts__["test"],
    )


def set_perms(path, grant_perms=None, deny_perms=None, inheritance=True, reset=False):
    """
    Set permissions for the given path

    Args:

        path (str):
            The full path to the directory.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here for directories. The default for
            ``applies_to`` is ``this_folder_subfolders_files``. Specify another
            ``applies_to`` setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter,
            ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

            To see a list of available attributes and applies to settings see
            the documentation for salt.utils.win_dacl.

            A value of ``None`` will make no changes to the ``grant`` portion of
            the DACL. Default is ``None``.

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

            A value of ``None`` will make no changes to the ``deny`` portion of
            the DACL. Default is ``None``.

        inheritance (bool):
            If ``True`` the object will inherit permissions from the parent, if
            ``False``, inheritance will be disabled. Inheritance setting will
            not apply to parent directories if they must be created. Default is
            ``False``.

        reset (bool):
            If ``True`` the existing DCL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If unsuccessful

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.set_perms C:\\Temp\\ "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.set_perms C:\\Temp\\ "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.set_perms C:\\Temp\\ "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_only'}}"
    """
    return salt.utils.win_dacl.set_perms(
        obj_name=path,
        obj_type="file",
        grant_perms=grant_perms,
        deny_perms=deny_perms,
        inheritance=inheritance,
        reset=reset,
    )
