# -*- coding: utf-8 -*-
'''
Platform independent versions of some os/os.path functions. Gets around PY2's
lack of support for reading NTFS links.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import collections
import errno
import logging
import os
import pathlib
import posixpath
import re
import stat
import string
import struct
import sys

# Import Salt libs
import salt.utils.args
import salt.utils.files
import salt.utils.group
import salt.utils.hashutils
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.pycrypto
from salt.exceptions import CommandNotFoundError
from salt.utils.decorators import memoize as real_memoize
from salt.utils.decorators.jinja import jinja_filter

# Import 3rd-party libs
from salt.ext import six

try:
    import win32file
    from pywintypes import error as pywinerror

    HAS_WIN32FILE = True
except ImportError:
    HAS_WIN32FILE = False

log = logging.getLogger(__name__)


def __list_clean_sorted(list_to_treat):
    ret = []
    for ele in list_to_treat:
        if ele not in ret:
            ret.append(ele)
    return sorted(ret)


def set_link(src, path, hard=False, resolve=True):
    '''
    Create soft link or hard link.
    :param src: The file or
    :param path:
    :param hard:
    :param resolve:
    :return:
    '''
    ret = False
    abs_src = get_link(src, resolve=resolve)
    abs_path = get_link(path, resolve=False)

    if is_symlink(abs_path):
        log.error("The path {} is already a link.".format(abs_path))
    elif exist(abs_path):
        log.error("The path {} already exist.".format(abs_path))
    elif hard:
        pathlib.Path(abs_path).link_to(abs_src)
        ret = True
    else:
        pathlib.Path(abs_path).symlink_to(abs_src)
        ret = True

    return ret


def get_link(path, resolve=True, canonicalize=False):
    '''
    Return the path pointing by a symlink.
    :param path: The symlink to managed.
    :param resolve: True to return the pointing path.
    :param canonicalize: True to return the real end pointing path (In case of multiple symlink).
    :return: The pointing path.
    '''
    ret = ''
    if canonicalize:
        ret = os.path.realpath(path)
    else:
        ret = str(get_absolute(path, resolve))
    return ret


def is_symlink(path):
    '''
    Test if the path is a symlink.
    :param path: Absolute path.
    :return: True if the path is a symlink, else False.
    '''
    return True if pathlib.Path(path).is_symlink() else False


def get_absolute(path, resolve=False, follow_symlinks=False):
    '''
    Return the absolute path in parameter.
    The path does not necessary exist on the file system.
    If the input path is 'foo', return '/tmp/foo' if the execution is from '/tmp' directory.
    If the input path is './foo', return '/tmp/foo' if the execution is from '/tmp' directory.
    If the input path is '../foo', return '/foo' if the execution is from '/tmp' directory.
    If the input path is '~/foo', return '/root/foo' if the execution is by the user 'root' with the home '/root'.
    If the input path is '/bar/fo*', return '/bar/foo'.
    :param path: The path to managed.
    :param resolve: 'True' to resolve '/bar/../foo' to '/foo', else 'False' to resolve '/bar/../foo' to '/bar/../foo'.
    :param follow_symlinks:
    :return: The absolute path.
    '''
    ret = ''

    if follow_symlinks and is_symlink(path):
        path = str(pathlib.Path(path).resolve())

    if resolve and is_symlink(path):
        ret = pathlib.Path(path).absolute()
    elif resolve or (follow_symlinks and is_symlink(path)):
        ret = pathlib.Path(path).resolve()
    elif is_absolute(path):
        ret = path
    return str(ret)


def is_absolute(path):
    '''
    Test if the path absolute.
    :param path: Absolute path.
    :return: True if the path is absolute, else False.
    '''
    return pathlib.PurePath(path).is_absolute()


def get_basename(path, resolve=True):
    '''
    Return the final component to the path.
    :param path: Absolute path to managed.
    :param resolve: See the get_absolute definition.
    :return: The basename.
    '''
    abs_path = get_absolute(path, resolve)
    return str(pathlib.PurePath(abs_path).name)


def get_parent(path, resolve=True):
    '''
    Return the parent of the path.
    :param path: Absolute path to managed.
    :param resolve: See the get_absolute definition.
    :return: The parent path.
    '''
    abs_path = get_absolute(path, resolve)
    return str(pathlib.PurePath(abs_path).parent)


def is_dir(path):
    '''
    Test if the path is a directory.
    :param path: Absolute path.
    :return: True if the path is a directory, else False.
    '''
    return True if exist(path) and pathlib.Path(path).is_dir() else False


def is_file(path):
    '''
    Test if the path is a file.
    :param path: Absolute path.
    :return: True if the path is a file, else False.
    '''
    return True if exist(path) and pathlib.Path(path).is_file() else False


def is_mount(path):
    '''
    Test if the path is a mount.
    :param path: Absolute path.
    :return: True if the path is a mount, else False.
    '''
    return True if exist(path) and pathlib.Path(path).is_mount() else False


def is_socket(path):
    '''
    Test if the path is a socket.
    :param path: Absolute path.
    :return: True if the path is a socket, else False.
    '''
    return True if exist(path) and pathlib.Path(path).is_socket() else False


def is_fifo(path):
    '''
    Test if the path is a FiFo.
    :param path: Absolute path.
    :return: True if the path is a FiFo, else False.
    '''
    return True if exist(path) and pathlib.Path(path).is_fifo() else False


def is_block_device(path):
    '''
    Test if the path is a block device.
    :param path: Absolute path.
    :return: True if the path is a block device, else False.
    '''
    return True if exist(path) and pathlib.Path(path).is_block_device() else False


def is_char_device(path):
    '''
    Test if the path is a char device.
    :param path: Absolute path.
    :return: True if the path is a char device, else False.
    '''
    return True if exist(path) and pathlib.Path(path).is_char_device() else False


def get_user(path):
    '''

    :param path:
    :return:
    '''
    ret = ''
    try:
        ret = pathlib.Path(path).owner()
    except KeyError as exc:
        log.info("Can't get user name for {}. Error: {}".format(path, exc))
    return ret


def set_user(path, user):
    '''

    :param path:
    :param user:
    :return:
    '''
    ret = False
    if (is_file(path) or is_dir(path)) and not is_symlink(path):
        try:
            os.chown(path, salt.utils.user.user_to_uid(user), -1)
            ret = True
        except PermissionError as exc:
            log.info(exc)
    return ret


def get_uid(path):
    '''

    :param path:
    :return:
    '''
    return salt.utils.user.user_to_uid(get_user(path))


def get_group(path):
    '''

    :param path:
    :return:
    '''
    ret = ''
    try:
        ret = pathlib.Path(path).group()
    except KeyError as exc:
        log.info("Can't get group name for {}. Error: {}".format(path, exc))
    return ret


def set_group(path, group):
    '''

    :param path:
    :param group:
    :return:
    '''
    ret = False
    if (is_file(path) or is_dir(path)) and not is_symlink(path):
        try:
            os.chown(path, -1, salt.utils.group.group_to_gid(group))
            ret = True
        except PermissionError as exc:
            log.info(exc)
    return ret


def get_gid(path):
    '''

    :param path:
    :return:
    '''
    return salt.utils.group.group_to_gid(get_group(path))


def get_type(path):
    '''

    :param path:
    :return:
    '''
    ret = ''
    abs_path = get_absolute(path)
    if is_symlink(abs_path):
        ret = 'link'
    elif is_char_device(abs_path):
        ret = 'char'
    elif is_block_device(abs_path):
        ret = 'block'
    elif is_fifo(abs_path):
        ret = 'pipe'
    elif is_socket(abs_path):
        ret = 'socket'
    elif is_file(abs_path):
        ret = 'file'
    elif is_dir(abs_path):
        ret = 'dir'
    return ret


def get_size(path):
    '''

    :param path:
    :return:
    '''
    return stats(path).get('size')


def get_mode(path):
    '''

    :param path:
    :return:
    '''
    return stats(path).get('mode')


def dir_to_list(path, recursive=False, follow_symlinks=False, __first_inc=True):
    '''
    List the content of a directory.
    :param path: Absolute path to the directory to managed.
    :param recursive:
    :param follow_symlinks:
    :return: List of directory contents.
    '''
    ret = []
    abs_path = get_absolute(path, follow_symlinks=follow_symlinks)
    if is_dir(abs_path) and not is_symlink(abs_path):
        for element in pathlib.Path(abs_path).iterdir():
            element = str(element)
            ret.append(element)
            if (recursive and is_dir(element)) or (follow_symlinks and is_symlink(element)):
                ret.extend(dir_to_list(element, recursive, follow_symlinks, __first_inc=False))
    if not __first_inc:
        ret.append(abs_path)

    return __list_clean_sorted(ret)


def dir_to_dict(path, recursive=False, follow_symlinks=False):
    '''

    :param path:
    :param recursive:
    :param follow_symlinks:
    :return:
    '''
    ret = {}
    for ele in dir_to_list(path, recursive, follow_symlinks):
        ele_type = get_type(ele)
        if ele_type not in ret.keys():
            ret.update({ele_type: [ele]})
        else:
            ret[ele_type].append(ele)
    return ret


def dir_is_empty(path):
    '''
    Check if the directory empty on the host file system.
    :param path: Absolute path to the directory to managed.
    :return: 'True' if the path is empty, else 'False'.
    '''
    return len(dir_to_list(path)) == 0


def dir_is_present(path, parents=True):
    '''
    Make the directory if it's not present. 'mkdir' like.
    :param path: Absolute path to the directory to create.
    :param parents: Make the parents directories.
    :return: True if the directory is present, else False.
    '''
    path = get_absolute(path)
    if not exist(path):
        pathlib.Path(path).mkdir(parents=parents, exist_ok=True)
    return is_dir(path)


def dir_is_absent(path):
    '''
    Remove the directory if it's empty. 'rm' like.
    :param path:
    :return:
    '''
    if is_dir(path) and dir_is_empty(path) and not is_symlink(path):
        pathlib.Path(get_absolute(path)).rmdir()
    return not exist(path)


def file_is_present(path):
    '''
    Touch the file if it's not present. 'touch' like.
    :param path: Absolute path to the file to create.
    :return: True if the file is present, else False.
    '''
    path = get_absolute(path)
    if not exist(path):
        pathlib.Path(path).touch()
    return is_file(path)


def file_is_absent(path):
    '''

    :param path:
    :return:
    '''
    # Requiered to check if it's a link, in case of broken link.
    if is_symlink(path) or is_file(path):
        pathlib.Path(path).unlink()
    return not exist(path)


def remove(path, recursive=False, follow_symlinks=False):
    '''
    :param path:
    :param recursive:
    :param follow_symlinks:
    :return:
    '''
    ret = []

    if recursive and is_dir(path) and not is_symlink(path):
        for ele in dir_to_list(path, recursive, follow_symlinks):
            ret.extend(remove(ele, recursive, follow_symlinks))
    if file_is_absent(path) or dir_is_absent(path):
        ret.append(path)

    return __list_clean_sorted(ret)


def random_tmp_file(tmp_dir='/tmp'):
    '''
    Create a temporary file with a random name.
    :param tmp_dir: Absolute path to the directory to create the random file.
    :return: The path to the file created.
    '''
    ret = None
    if is_absolute(tmp_dir):
        tmp_file = join(tmp_dir, salt.utils.pycrypto.secure_password())
        if file_is_present(tmp_file):
            ret = tmp_file
    return ret


def stats(path, hash_type="sha256", follow_symlinks=True):
    '''
    Return a dict containing the stats for a given path.
    :param path:
    :param hash_type:
    :param follow_symlinks:
    :return:
    '''
    ret = {}
    path = get_absolute(path, follow_symlinks=follow_symlinks)
    if exist(path):
        path_stat = pathlib.Path(path).stat()

        ret['target'] = path
        ret['inode'] = path_stat.st_ino
        ret['uid'] = get_uid(path)
        ret['user'] = get_user(path)
        ret['gid'] = get_gid(path)
        ret['group'] = get_group(path)
        ret['atime'] = path_stat.st_atime
        ret['mtime'] = path_stat.st_mtime
        ret['ctime'] = path_stat.st_ctime
        ret['size'] = path_stat.st_size
        ret['mode'] = salt.utils.files.normalize_mode(oct(stat.S_IMODE(path_stat.st_mode)))
        ret['type'] = get_type(path)

        if is_file(path):
            ret['sum'] = salt.utils.hashutils.get_hash(path, hash_type)

    return ret


def exist(path):
    '''
    Test if the path exist.
    :param path: Absolute path.
    :return: True if the path exist, else False.
    '''
    return pathlib.Path(path).exists()


def rename(src, path, safe=False):
    '''

    :param src:
    :param path:
    :param safe:
    :return:
    '''
    ret = False
    abs_src = get_absolute(src)
    abs_path = get_absolute(path)

    if exist(abs_path):
        if safe:
            log.error("The destination {} already exist.".format(abs_path))
        elif get_type(abs_src) == get_type(abs_path):
            pathlib.Path(abs_src).replace(abs_path)
            ret = True
        else:
            log.error(
                "The source path_type '{}' is different to the destination path_type '{}'.".format(abs_src, abs_path))
    else:
        pathlib.Path(abs_src).replace(abs_path)
        ret = True

    return ret


def copy(src, path, recursive=False, remove_existing=False, safe=True):
    '''

    :param src:
    :param path:
    :param recursive:
    :param remove_existing:
    :param safe:
    :return:
    '''
    ret = {'added': [], 'removed': [], 'unchanged': [], 'changed': []}
    abs_src = get_absolute(src, resolve=True)
    abs_path = get_absolute(path, resolve=True)

    # clean destination
    if exist(abs_path):
        if safe:
            log.error("The destination {} already exist.".format(abs_path))
        elif remove_existing and (get_type(abs_src) == get_type(abs_path)):
            ret['removed'].extend(remove(abs_path, recursive=recursive))
        else:
            log.error(
                "The source path_type '{}' is different to the destination path_type '{}'.".format(abs_src, abs_path))

    abs_src_user = get_user(abs_src)
    abs_src_uid = get_uid(abs_src)
    abs_src_group = get_group(abs_src)
    abs_src_gid = get_gid(abs_src)
    abs_src_mode = get_mode(abs_src)

    return ret


def copy(src, dst, recurse=False, remove_existing=False):
    src = os.path.expanduser(src)
    dst = os.path.expanduser(dst)

    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    if not os.path.exists(src):
        raise CommandExecutionError('No such file or directory \'{0}\''.format(src))

    if not salt.utils.platform.is_windows():
        pre_user = get_user(src)
        pre_group = get_group(src)
        pre_mode = salt.utils.files.normalize_mode(get_mode(src))

    try:
        if (os.path.exists(dst) and os.path.isdir(dst)) or os.path.isdir(src):
            if not recurse:
                raise SaltInvocationError(
                    "Cannot copy overwriting a directory without recurse flag set to true!")
            if remove_existing:
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                salt.utils.files.recursive_copy(src, dst)
        else:
            shutil.copyfile(src, dst)
    except OSError:
        raise CommandExecutionError(
            'Could not copy \'{0}\' to \'{1}\''.format(src, dst)
        )

    if not salt.utils.platform.is_windows():
        check_perms(dst, None, pre_user, pre_group, pre_mode)
    return True


def recursive_copy(source, dest):
    '''
    Recursively copy the source directory to the destination,
    leaving files with the source does not explicitly overwrite.

    (identical to cp -r on a unix machine)
    '''
    for root, _, files in salt.utils.path.os_walk(source):
        path_from_source = root.replace(source, '').lstrip(os.sep)
        target_directory = os.path.join(dest, path_from_source)
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
        for name in files:
            file_path_from_source = os.path.join(source, path_from_source, name)
            target_path = os.path.join(target_directory, name)
            shutil.copyfile(file_path_from_source, target_path)


def move():
    pass


def islink(path):
    '''
    [DEPRECATED] use 'is_symlink()'
    Equivalent to os.path.islink()
    '''
    if six.PY3 or not salt.utils.platform.is_windows():
        return os.path.islink(path)

    if not HAS_WIN32FILE:
        log.error('Cannot check if %s is a link, missing required modules', path)

    if not _is_reparse_point(path):
        return False

    # check that it is a symlink reparse point (in case it is something else,
    # like a mount point)
    reparse_data = _get_reparse_data(path)

    # sanity check - this should not happen
    if not reparse_data:
        # not a reparse point
        return False

    # REPARSE_DATA_BUFFER structure - see
    # http://msdn.microsoft.com/en-us/library/ff552012.aspx

    # parse the structure header to work out which type of reparse point this is
    header_parser = struct.Struct('L')
    ReparseTag, = header_parser.unpack(reparse_data[:header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        return False
    else:
        return True


def readlink(path):
    '''
    Equivalent to os.readlink()
    '''
    if six.PY3 or not salt.utils.platform.is_windows():
        return os.readlink(path)

    if not HAS_WIN32FILE:
        log.error('Cannot read %s, missing required modules', path)

    reparse_data = _get_reparse_data(path)

    if not reparse_data:
        # Reproduce *NIX behavior when os.readlink is performed on a path that
        # is not a symbolic link.
        raise OSError(errno.EINVAL, 'Invalid argument: \'{0}\''.format(path))

    # REPARSE_DATA_BUFFER structure - see
    # http://msdn.microsoft.com/en-us/library/ff552012.aspx

    # parse the structure header to work out which type of reparse point this is
    header_parser = struct.Struct('L')
    ReparseTag, = header_parser.unpack(reparse_data[:header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        raise OSError(
            errno.EINVAL,
            '{0} is not a symlink, but another type of reparse point '
            '(0x{0:X}).'.format(ReparseTag)
        )

    # parse as a symlink reparse point structure (the structure for other
    # reparse points is different)
    data_parser = struct.Struct('LHHHHHHL')
    ReparseTag, ReparseDataLength, Reserved, SubstituteNameOffset, \
    SubstituteNameLength, PrintNameOffset, \
    PrintNameLength, Flags = data_parser.unpack(reparse_data[:data_parser.size])

    path_buffer_offset = data_parser.size
    absolute_substitute_name_offset = path_buffer_offset + SubstituteNameOffset
    target_bytes = reparse_data[absolute_substitute_name_offset:absolute_substitute_name_offset + SubstituteNameLength]
    target = target_bytes.decode('UTF-16')

    if target.startswith('\\??\\'):
        target = target[4:]

    try:
        # comes out in 8.3 form; convert it to LFN to make it look nicer
        target = win32file.GetLongPathName(target)
    except pywinerror as exc:
        # If target is on a UNC share, the decoded target will be in the format
        # "UNC\hostanme\sharename\additional\subdirs\under\share". So, in
        # these cases, return the target path in the proper UNC path format.
        if target.startswith('UNC\\'):
            return re.sub(r'^UNC\\+', r'\\\\', target)
        # if file is not found (i.e. bad symlink), return it anyway like on *nix
        if exc.winerror == 2:
            return target
        raise

    return target


def _is_reparse_point(path):
    '''
    Returns True if path is a reparse point; False otherwise.
    '''
    result = win32file.GetFileAttributesW(path)

    if result == -1:
        return False

    return True if result & 0x400 else False


def _get_reparse_data(path):
    '''
    Retrieves the reparse point data structure for the given path.

    If the path is not a reparse point, None is returned.

    See http://msdn.microsoft.com/en-us/library/ff552012.aspx for details on the
    REPARSE_DATA_BUFFER structure returned.
    '''
    # ensure paths are using the right slashes
    path = os.path.normpath(path)

    if not _is_reparse_point(path):
        return None

    fileHandle = None
    try:
        fileHandle = win32file.CreateFileW(
            path,
            0x80000000,  # GENERIC_READ
            1,  # share with other readers
            None,  # no inherit, default security descriptor
            3,  # OPEN_EXISTING
            0x00200000 | 0x02000000  # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
        )

        reparseData = win32file.DeviceIoControl(
            fileHandle,
            0x900a8,  # FSCTL_GET_REPARSE_POINT
            None,  # in buffer
            16384  # out buffer size (MAXIMUM_REPARSE_DATA_BUFFER_SIZE)
        )

    finally:
        if fileHandle:
            win32file.CloseHandle(fileHandle)

    return reparseData


@jinja_filter('which')
def which(exe=None):
    '''
    Python clone of /usr/bin/which
    '''

    def _is_executable_file_or_link(exe):
        # check for os.X_OK doesn't suffice because directory may executable
        return (os.access(exe, os.X_OK) and
                (os.path.isfile(exe) or os.path.islink(exe)))

    if exe:
        if _is_executable_file_or_link(exe):
            # executable in cwd or fullpath
            return exe

        ext_list = salt.utils.stringutils.to_str(
            os.environ.get('PATHEXT', str('.EXE'))
        ).split(str(';'))

        @real_memoize
        def _exe_has_ext():
            '''
            Do a case insensitive test if exe has a file extension match in
            PATHEXT
            '''
            for ext in ext_list:
                try:
                    pattern = r'.*\.{0}$'.format(
                        salt.utils.stringutils.to_unicode(ext).lstrip('.')
                    )
                    re.match(
                        pattern,
                        salt.utils.stringutils.to_unicode(exe),
                        re.I).groups()
                    return True
                except AttributeError:
                    continue
            return False

        # Enhance POSIX path for the reliability at some environments, when $PATH is changing
        # This also keeps order, where 'first came, first win' for cases to find optional alternatives
        system_path = salt.utils.stringutils.to_unicode(os.environ.get('PATH', ''))
        search_path = system_path.split(os.pathsep)
        if not salt.utils.platform.is_windows():
            search_path.extend([
                x for x in ('/bin', '/sbin', '/usr/bin',
                            '/usr/sbin', '/usr/local/bin')
                if x not in search_path
            ])

        for path in search_path:
            full_path = join(path, exe)
            if _is_executable_file_or_link(full_path):
                return full_path
            elif salt.utils.platform.is_windows() and not _exe_has_ext():
                # On Windows, check for any extensions in PATHEXT.
                # Allows both 'cmd' and 'cmd.exe' to be matched.
                for ext in ext_list:
                    # Windows filesystem is case insensitive so we
                    # safely rely on that behavior
                    if _is_executable_file_or_link(full_path + ext):
                        return full_path + ext
        log.trace(
            '\'%s\' could not be found in the following search path: \'%s\'',
            exe, search_path
        )
    else:
        log.error('No executable was passed to be searched by salt.utils.path.which()')

    return None


def which_bin(exes):
    '''
    Scan over some possible executables and return the first one that is found
    '''
    if not isinstance(exes, collections.Iterable):
        return None
    for exe in exes:
        path = which(exe)
        if not path:
            continue
        return path
    return None


@jinja_filter('path_join')
def join(*parts, **kwargs):
    '''
    This functions tries to solve some issues when joining multiple absolute
    paths on both *nix and windows platforms.

    See tests/unit/utils/path_join_test.py for some examples on what's being
    talked about here.

    The "use_posixpath" kwarg can be be used to force joining using poxixpath,
    which is useful for Salt fileserver paths on Windows masters.
    '''
    if six.PY3:
        new_parts = []
        for part in parts:
            new_parts.append(salt.utils.stringutils.to_str(part))
        parts = new_parts

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    use_posixpath = kwargs.pop('use_posixpath', False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    pathlib = posixpath if use_posixpath else os.path

    # Normalize path converting any os.sep as needed
    parts = [pathlib.normpath(p) for p in parts]

    try:
        root = parts.pop(0)
    except IndexError:
        # No args passed to func
        return ''

    root = salt.utils.stringutils.to_unicode(root)
    if not parts:
        ret = root
    else:
        stripped = [p.lstrip(os.sep) for p in parts]
        ret = pathlib.join(root, *salt.utils.data.decode(stripped))
    return pathlib.normpath(ret)


def check_or_die(command):
    '''
    Simple convenience function for modules to use for gracefully blowing up
    if a required tool is not available in the system path.

    Lazily import `salt.modules.cmdmod` to avoid any sort of circular
    dependencies.
    '''
    if command is None:
        raise CommandNotFoundError('\'None\' is not a valid command.')

    if not which(command):
        raise CommandNotFoundError('\'{0}\' is not in the path'.format(command))


def sanitize_win_path(winpath):
    '''
    Remove illegal path characters for windows
    '''
    intab = '<>:|?*'
    if isinstance(winpath, six.text_type):
        winpath = winpath.translate(dict((ord(c), '_') for c in intab))
    elif isinstance(winpath, six.string_types):
        outtab = '_' * len(intab)
        trantab = ''.maketrans(intab, outtab) if six.PY3 else string.maketrans(intab,
                                                                               outtab)  # pylint: disable=no-member
        winpath = winpath.translate(trantab)
    return winpath


def safe_path(path, allow_path=None):
    r'''
    .. versionadded:: 2017.7.3

    Checks that the path is safe for modification by Salt. For example, you
    wouldn't want to have salt delete the contents of ``C:\Windows``. The
    following directories are considered unsafe:

    - C:\, D:\, E:\, etc.
    - \
    - C:\Windows

    Args:

        path (str): The path to check

        allow_paths (str, list): A directory or list of directories inside of
            path that may be safe. For example: ``C:\Windows\TEMP``

    Returns:
        bool: True if safe, otherwise False
    '''
    # Create regex definitions for directories that may be unsafe to modify
    system_root = os.environ.get('SystemRoot', 'C:\\Windows')
    deny_paths = (
        r'[a-z]\:\\$',  # C:\, D:\, etc
        r'\\$',  # \
        re.escape(system_root)  # C:\Windows
    )

    # Make allow_path a list
    if allow_path and not isinstance(allow_path, list):
        allow_path = [allow_path]

    # Create regex definition for directories we may want to make exceptions for
    allow_paths = list()
    if allow_path:
        for item in allow_path:
            allow_paths.append(re.escape(item))

    # Check the path to make sure it's not one of the bad paths
    good_path = True
    for d_path in deny_paths:
        if re.match(d_path, path, flags=re.IGNORECASE) is not None:
            # Found deny path
            good_path = False

    # If local_dest is one of the bad paths, check for exceptions
    if not good_path:
        for a_path in allow_paths:
            if re.match(a_path, path, flags=re.IGNORECASE) is not None:
                # Found exception
                good_path = True

    return good_path


def os_walk(top, *args, **kwargs):
    '''
    This is a helper than ensures that all paths returned from os.walk are
    unicode.
    '''
    if six.PY2 and salt.utils.platform.is_windows():
        top_query = top
    else:
        top_query = salt.utils.stringutils.to_str(top)
    for item in os.walk(top_query, *args, **kwargs):
        yield salt.utils.data.decode(item, preserve_tuples=True)
