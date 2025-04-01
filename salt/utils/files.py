"""
Functions for working with files
"""

import codecs
import contextlib
import errno
import io
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.parse

import salt.modules.selinux
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, FileLockError, MinionError
from salt.utils.decorators.jinja import jinja_filter

try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    # fcntl is not available on windows
    HAS_FCNTL = False

log = logging.getLogger(__name__)

LOCAL_PROTOS = ("", "file")
REMOTE_PROTOS = ("http", "https", "ftp", "swift", "s3")
VALID_PROTOS = ("salt", "file") + REMOTE_PROTOS
TEMPFILE_PREFIX = "__salt.tmp."

HASHES = {
    "sha512": 128,
    "sha384": 96,
    "sha256": 64,
    "sha224": 56,
    "sha1": 40,
    "md5": 32,
}
HASHES_REVMAP = {y: x for x, y in HASHES.items()}


def __clean_tmp(tmp):
    """
    Remove temporary files
    """
    try:
        rm_rf(tmp)
    except Exception as exc:  # pylint: disable=broad-except
        log.error(
            "Exception while removing temp directory: %s",
            exc,
            exc_info_on_loglevel=logging.DEBUG,
        )


def guess_archive_type(name):
    """
    Guess an archive type (tar, zip, or rar) by its file extension
    """
    name = name.lower()
    for ending in (
        "tar",
        "tar.gz",
        "tgz",
        "tar.bz2",
        "tbz2",
        "tbz",
        "tar.xz",
        "txz",
        "tar.lzma",
        "tlz",
    ):
        if name.endswith("." + ending):
            return "tar"
    for ending in ("zip", "rar"):
        if name.endswith("." + ending):
            return ending
    return None


def mkstemp(*args, **kwargs):
    """
    Helper function which does exactly what ``tempfile.mkstemp()`` does but
    accepts another argument, ``close_fd``, which, by default, is true and closes
    the fd before returning the file path. Something commonly done throughout
    Salt's code.
    """
    if "prefix" not in kwargs:
        kwargs["prefix"] = "__salt.tmp."
    close_fd = kwargs.pop("close_fd", True)
    fd_, f_path = tempfile.mkstemp(*args, **kwargs)
    if close_fd is False:
        return fd_, f_path
    os.close(fd_)
    del fd_
    return f_path


def recursive_copy(source, dest):
    """
    Recursively copy the source directory to the destination,
    leaving files with the source does not explicitly overwrite.

    (identical to cp -r on a unix machine)
    """
    for root, _, files in salt.utils.path.os_walk(source):
        path_from_source = root.replace(source, "").lstrip(os.sep)
        target_directory = os.path.join(dest, path_from_source)
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
        for name in files:
            file_path_from_source = os.path.join(source, path_from_source, name)
            target_path = os.path.join(target_directory, name)
            shutil.copyfile(file_path_from_source, target_path)


def copyfile(source, dest, backup_mode="", cachedir=""):
    """
    Copy files from a source to a destination in an atomic way, and if
    specified cache the file.
    """
    if not os.path.isfile(source):
        raise OSError(f"[Errno 2] No such file or directory: {source}")
    if not os.path.isdir(os.path.dirname(dest)):
        raise OSError(f"[Errno 2] No such file or directory: {dest}")
    bname = os.path.basename(dest)
    dname = os.path.dirname(os.path.abspath(dest))
    tgt = mkstemp(prefix=bname, dir=dname)
    shutil.copyfile(source, tgt)
    bkroot = ""
    if cachedir:
        bkroot = os.path.join(cachedir, "file_backup")
    if backup_mode == "minion" or backup_mode == "both" and bkroot:
        if os.path.exists(dest):
            backup_minion(dest, bkroot)
    if backup_mode == "master" or backup_mode == "both" and bkroot:
        # TODO, backup to master
        pass
    # Get current file stats to they can be replicated after the new file is
    # moved to the destination path.
    fstat = None
    if not salt.utils.platform.is_windows():
        try:
            fstat = os.stat(dest)
        except OSError:
            pass

    # The move could fail if the dest has xattr protections, so delete the
    # temp file in this case
    try:
        shutil.move(tgt, dest)
    except Exception:  # pylint: disable=broad-except
        __clean_tmp(tgt)
        raise

    if fstat is not None:
        os.chown(dest, fstat.st_uid, fstat.st_gid)
        os.chmod(dest, fstat.st_mode)
    # If SELINUX is available run a restorecon on the file
    rcon = salt.utils.path.which("restorecon")
    if rcon:
        policy = False
        try:
            policy = salt.modules.selinux.getenforce()
        except (ImportError, CommandExecutionError):
            pass
        if policy == "Enforcing":
            with fopen(os.devnull, "w") as dev_null:
                cmd = [rcon, dest]
                subprocess.call(cmd, stdout=dev_null, stderr=dev_null)
    if os.path.isfile(tgt):
        # The temp file failed to move
        __clean_tmp(tgt)


def rename(src, dst):
    """
    On Windows, os.rename() will fail with a WindowsError exception if a file
    exists at the destination path. This function checks for this error and if
    found, it deletes the destination path first.
    """
    try:
        os.rename(src, dst)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        try:
            os.remove(dst)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise MinionError(f"Error: Unable to remove {dst}: {exc.strerror}")
        os.rename(src, dst)


def process_read_exception(exc, path, ignore=None):
    """
    Common code for raising exceptions when reading a file fails

    The ignore argument can be an iterable of integer error codes (or a single
    integer error code) that should be ignored.
    """
    if ignore is not None:
        if isinstance(ignore, int):
            ignore = (ignore,)
    else:
        ignore = ()

    if exc.errno in ignore:
        return

    if exc.errno == errno.ENOENT:
        raise CommandExecutionError(f"{path} does not exist")
    elif exc.errno == errno.EACCES:
        raise CommandExecutionError(f"Permission denied reading from {path}")
    else:
        raise CommandExecutionError(
            "Error {} encountered reading from {}: {}".format(
                exc.errno, path, exc.strerror
            )
        )


@contextlib.contextmanager
def wait_lock(path, lock_fn=None, timeout=5, sleep=0.1, time_start=None):
    """
    Obtain a write lock. If one exists, wait for it to release first
    """
    if not isinstance(path, str):
        raise FileLockError("path must be a string")
    if lock_fn is None:
        lock_fn = path + ".w"
    if time_start is None:
        time_start = time.time()
    obtained_lock = False

    def _raise_error(msg, race=False):
        """
        Raise a FileLockError
        """
        raise FileLockError(msg, time_start=time_start)

    try:
        if os.path.exists(lock_fn) and not os.path.isfile(lock_fn):
            _raise_error(f"lock_fn {lock_fn} exists and is not a file")

        open_flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        while time.time() - time_start < timeout:
            try:
                # Use os.open() to obtain filehandle so that we can force an
                # exception if the file already exists. Concept found here:
                # http://stackoverflow.com/a/10979569
                fh_ = os.open(lock_fn, open_flags)
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    _raise_error(
                        "Error {} encountered obtaining file lock {}: {}".format(
                            exc.errno, lock_fn, exc.strerror
                        )
                    )
                log.trace("Lock file %s exists, sleeping %f seconds", lock_fn, sleep)
                time.sleep(sleep)
            else:
                # Write the lock file
                with os.fdopen(fh_, "w"):
                    pass
                # Lock successfully acquired
                log.trace("Write lock %s obtained", lock_fn)
                obtained_lock = True
                # Transfer control back to the code inside the with block
                yield
                # Exit the loop
                break

        else:
            _raise_error(
                "Timeout of {} seconds exceeded waiting for lock_fn {} "
                "to be released".format(timeout, lock_fn)
            )

    except FileLockError:
        raise

    except Exception as exc:  # pylint: disable=broad-except
        _raise_error(f"Error encountered obtaining file lock {lock_fn}: {exc}")

    finally:
        if obtained_lock:
            os.remove(lock_fn)
            log.trace("Write lock for %s (%s) released", path, lock_fn)


def get_umask():
    """
    Returns the current umask
    """
    ret = os.umask(0)  # pylint: disable=blacklisted-function
    os.umask(ret)  # pylint: disable=blacklisted-function
    return ret


@contextlib.contextmanager
def set_umask(mask):
    """
    Temporarily set the umask and restore once the contextmanager exits
    """
    if mask is None or salt.utils.platform.is_windows():
        # Don't attempt on Windows, or if no mask was passed
        yield
    else:
        orig_mask = os.umask(mask)  # pylint: disable=blacklisted-function
        try:
            yield
        finally:
            os.umask(orig_mask)  # pylint: disable=blacklisted-function


def fopen(*args, **kwargs):
    """
    Wrapper around open() built-in to set CLOEXEC on the fd.

    This flag specifies that the file descriptor should be closed when an exec
    function is invoked;

    When a file descriptor is allocated (as with open or dup), this bit is
    initially cleared on the new file descriptor, meaning that descriptor will
    survive into the new program after exec.

    NB! We still have small race condition between open and fcntl.
    """
    try:
        # Don't permit stdin/stdout/stderr to be opened. The boolean False
        # and True are treated by Python 3's open() as file descriptors 0
        # and 1, respectively.
        if args[0] in (0, 1, 2):
            raise TypeError(f"{args[0]} is not a permitted file descriptor")
    except IndexError:
        pass
    binary = None
    if kwargs.pop("binary", None):
        if len(args) > 1:
            args = list(args)
            if "b" not in args[1]:
                args[1] = args[1].replace("t", "b")
                if "b" not in args[1]:
                    args[1] += "b"
        elif kwargs.get("mode"):
            if "b" not in kwargs["mode"]:
                kwargs["mode"] = kwargs["mode"].replace("t", "b")
                if "b" not in kwargs["mode"]:
                    kwargs["mode"] += "b"
        else:
            # the default is to read
            kwargs["mode"] = "rb"
    if "encoding" not in kwargs:
        # In Python 3, if text mode is used and the encoding
        # is not specified, set the encoding to 'utf-8'.
        binary = False
        if len(args) > 1:
            args = list(args)
            if "b" in args[1]:
                binary = True
        if kwargs.get("mode", None):
            if "b" in kwargs["mode"]:
                binary = True
        if not binary:
            kwargs["encoding"] = __salt_system_encoding__

    if not binary and not kwargs.get("newline", None):
        kwargs["newline"] = ""

    # Workaround callers with bad buffering setting for binary files
    if kwargs.get("buffering") == 1 and "b" in kwargs.get("mode", ""):
        log.debug(
            "Line buffering (buffering=1) isn't supported in binary mode, "
            "the default buffer size will be used"
        )
        kwargs["buffering"] = io.DEFAULT_BUFFER_SIZE

    f_handle = open(  # pylint: disable=resource-leakage,unspecified-encoding
        *args, **kwargs
    )

    if is_fcntl_available():
        # modify the file descriptor on systems with fcntl
        # unix and unix-like systems only
        try:
            FD_CLOEXEC = fcntl.FD_CLOEXEC  # pylint: disable=C0103
        except AttributeError:
            FD_CLOEXEC = 1  # pylint: disable=C0103
        old_flags = fcntl.fcntl(f_handle.fileno(), fcntl.F_GETFD)
        fcntl.fcntl(f_handle.fileno(), fcntl.F_SETFD, old_flags | FD_CLOEXEC)

    return f_handle


@contextlib.contextmanager
def flopen(*args, **kwargs):
    """
    Shortcut for fopen with lock and context manager.
    """
    filename, args = args[0], args[1:]
    writing = "wa"
    with fopen(filename, *args, **kwargs) as f_handle:
        try:
            if is_fcntl_available(check_sunos=True):
                lock_type = fcntl.LOCK_SH
                if args and any([write in args[0] for write in writing]):
                    lock_type = fcntl.LOCK_EX
                fcntl.flock(f_handle.fileno(), lock_type)
            yield f_handle
        finally:
            if is_fcntl_available(check_sunos=True):
                fcntl.flock(f_handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def fpopen(*args, **kwargs):
    """
    Shortcut for fopen with extra uid, gid, and mode options.

    Supported optional Keyword Arguments:

    mode
        Explicit mode to set. Mode is anything os.chmod would accept
        as input for mode. Works only on unix/unix-like systems.

    uid
        The uid to set, if not set, or it is None or -1 no changes are
        made. Same applies if the path is already owned by this uid.
        Must be int. Works only on unix/unix-like systems.

    gid
        The gid to set, if not set, or it is None or -1 no changes are
        made. Same applies if the path is already owned by this gid.
        Must be int. Works only on unix/unix-like systems.

    """
    # Remove uid, gid and mode from kwargs if present
    uid = kwargs.pop("uid", -1)  # -1 means no change to current uid
    gid = kwargs.pop("gid", -1)  # -1 means no change to current gid
    mode = kwargs.pop("mode", None)
    with fopen(*args, **kwargs) as f_handle:
        path = args[0]
        d_stat = os.stat(path)

        if hasattr(os, "chown"):
            # if uid and gid are both -1 then go ahead with
            # no changes at all
            if (d_stat.st_uid != uid or d_stat.st_gid != gid) and [
                i for i in (uid, gid) if i != -1
            ]:
                os.chown(path, uid, gid)

        if mode is not None:
            mode_part = stat.S_IMODE(d_stat.st_mode)
            if mode_part != mode:
                os.chmod(path, (d_stat.st_mode ^ mode_part) | mode)

        yield f_handle


def safe_walk(top, topdown=True, onerror=None, followlinks=True, _seen=None):
    """
    A clone of the python os.walk function with some checks for recursive
    symlinks. Unlike os.walk this follows symlinks by default.
    """
    if _seen is None:
        _seen = set()

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.path.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        # Note that listdir and error are globals in this module due
        # to earlier import-*.
        names = os.listdir(top)
    except OSError as err:
        if onerror is not None:
            onerror(err)
        return

    if followlinks:
        status = os.stat(top)
        # st_ino is always 0 on some filesystems (FAT, NTFS); ignore them
        if status.st_ino != 0:
            node = (status.st_dev, status.st_ino)
            if node in _seen:
                return
            _seen.add(node)

    dirs, nondirs = [], []
    for name in names:
        full_path = os.path.join(top, name)
        if os.path.isdir(full_path):
            dirs.append(name)
        else:
            nondirs.append(name)

    if topdown:
        yield top, dirs, nondirs
    for name in dirs:
        new_path = os.path.join(top, name)
        if followlinks or not os.path.islink(new_path):
            yield from safe_walk(new_path, topdown, onerror, followlinks, _seen)
    if not topdown:
        yield top, dirs, nondirs


def safe_rm(tgt):
    """
    Safely remove a file
    """
    try:
        os.remove(tgt)
    except OSError:
        pass


def rm_rf(path):
    """
    Platform-independent recursive delete. Includes code from
    http://stackoverflow.com/a/2656405
    """

    def _onerror(func, path, exc_info):
        """
        Error handler for `shutil.rmtree`.

        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.

        If the error is for another reason it re-raises the error.

        Usage : `shutil.rmtree(path, onerror=onerror)`
        """
        if salt.utils.platform.is_windows() and not os.access(path, os.W_OK):
            # Is the error an access error ?
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise  # pylint: disable=E0704

    if os.path.islink(path) or not os.path.isdir(path):
        os.remove(path)
    else:
        if salt.utils.platform.is_windows():
            try:
                path = salt.utils.stringutils.to_unicode(path)
            except TypeError:
                pass
        shutil.rmtree(path, onerror=_onerror)


@jinja_filter("is_empty")
def is_empty(filename):
    """
    Is a file empty?
    """
    try:
        return os.stat(filename).st_size == 0
    except OSError:
        # Non-existent file or permission denied to the parent dir
        return False


def is_fcntl_available(check_sunos=False):
    """
    Simple function to check if the ``fcntl`` module is available or not.

    If ``check_sunos`` is passed as ``True`` an additional check to see if host is
    SunOS is also made. For additional information see: http://goo.gl/159FF8
    """
    if check_sunos and salt.utils.platform.is_sunos():
        return False
    return HAS_FCNTL


def safe_filename_leaf(file_basename):
    """
    Input the basename of a file, without the directory tree, and returns a safe name to use
    i.e. only the required characters are converted by urllib.parse.quote
    If the input is a PY2 String, output a PY2 String. If input is Unicode output Unicode.
    For consistency all platforms are treated the same. Hard coded to utf8 as its ascii compatible
    windows is \\ / : * ? " < > | posix is /

    .. versionadded:: 2017.7.2

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    """

    def _replace(re_obj):
        return urllib.parse.quote(re_obj.group(0), safe="")

    if not isinstance(file_basename, str):
        # the following string is not prefixed with u
        return re.sub(
            '[\\\\:/*?"<>|]',
            _replace,
            str(file_basename, "utf8").encode("ascii", "backslashreplace"),
        )
    # the following string is prefixed with u
    return re.sub('[\\\\:/*?"<>|]', _replace, file_basename, flags=re.UNICODE)


def safe_filepath(file_path_name, dir_sep=None):
    """
    Input the full path and filename, splits on directory separator and calls safe_filename_leaf for
    each part of the path. dir_sep allows coder to force a directory separate to a particular character

    .. versionadded:: 2017.7.2

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    """
    if not dir_sep:
        dir_sep = os.sep
    # Normally if file_path_name or dir_sep is Unicode then the output will be Unicode
    # This code ensure the output type is the same as file_path_name
    if not isinstance(file_path_name, str) and isinstance(dir_sep, str):
        dir_sep = dir_sep.encode("ascii")  # This should not be executed under PY3
    # splitdrive only set drive on windows platform
    (drive, path) = os.path.splitdrive(file_path_name)
    path = dir_sep.join(
        [safe_filename_leaf(file_section) for file_section in path.rsplit(dir_sep)]
    )
    if drive:
        path = dir_sep.join([drive, path])
    return path


@jinja_filter("is_text_file")
def is_text(fp_, blocksize=512):
    """
    Uses heuristics to guess whether the given file is text or binary,
    by reading a single block of bytes from the file.
    If more than 30% of the chars in the block are non-text, or there
    are NUL ('\x00') bytes in the block, assume this is a binary file.
    """

    def int2byte(x):
        return bytes((x,))

    text_characters = b"".join(int2byte(i) for i in range(32, 127)) + b"\n\r\t\f\b"
    try:
        block = fp_.read(blocksize)
    except AttributeError:
        # This wasn't an open filehandle, so treat it as a file path and try to
        # open the file
        try:
            with fopen(fp_, "rb") as fp2_:
                block = fp2_.read(blocksize)
        except OSError:
            # Unable to open file, bail out and return false
            return False
    if b"\x00" in block:
        # Files with null bytes are binary
        return False
    elif not block:
        # An empty file is considered a valid text file
        return True
    try:
        block.decode("utf-8")
        return True
    except UnicodeDecodeError:
        pass

    nontext = block.translate(None, text_characters)
    return float(len(nontext)) / len(block) <= 0.30


@jinja_filter("is_bin_file")
def is_binary(path):
    """
    Detects if the file is a binary, returns bool. Returns True if the file is
    a bin, False if the file is not and None if the file is not available.
    """
    if not os.path.isfile(path):
        return False
    try:
        with fopen(path, "rb") as fp_:
            try:
                data = fp_.read(2048)
                data = data.decode(__salt_system_encoding__)
                return salt.utils.stringutils.is_binary(data)
            except UnicodeDecodeError:
                return True
    except OSError:
        return False


def remove(path):
    """
    Runs os.remove(path) and suppresses the OSError if the file doesn't exist
    """
    try:
        os.remove(path)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise


@jinja_filter("list_files")
def list_files(directory):
    """
    Return a list of all files found under directory (and its subdirectories)
    """
    ret = set()
    ret.add(directory)
    for root, dirs, files in safe_walk(directory):
        for name in files:
            ret.add(os.path.join(root, name))
        for name in dirs:
            ret.add(os.path.join(root, name))

    return list(ret)


def st_mode_to_octal(mode):
    """
    Convert the st_mode value from a stat(2) call (as returned from os.stat())
    to an octal mode.
    """
    try:
        return oct(mode)[-4:]
    except (TypeError, IndexError):
        return ""


def normalize_mode(mode):
    """
    Return a mode value, normalized to a string and containing a leading zero
    if it does not have one.

    Allow "keep" as a valid mode (used by file state/module to preserve mode
    from the Salt fileserver in file states).
    """
    if mode is None:
        return None
    if not isinstance(mode, str):
        mode = str(mode)
    mode = mode.replace("0o", "0")
    # Strip any quotes any initial zeroes, then though zero-pad it up to 4.
    # This ensures that somethign like '00644' is normalized to '0644'
    return mode.strip('"').strip("'").lstrip("0").zfill(4)


def human_size_to_bytes(human_size):
    """
    Convert human-readable units to bytes
    """
    size_exp_map = {"K": 1, "M": 2, "G": 3, "T": 4, "P": 5}
    human_size_str = str(human_size)
    match = re.match(r"^(\d+)([KMGTP])?$", human_size_str)
    if not match:
        raise ValueError(
            "Size must be all digits, with an optional unit type (K, M, G, T, or P)"
        )
    size_num = int(match.group(1))
    unit_multiplier = 1024 ** size_exp_map.get(match.group(2), 0)
    return size_num * unit_multiplier


def backup_minion(path, bkroot):
    """
    Backup a file on the minion
    """
    dname, bname = os.path.split(path)
    if salt.utils.platform.is_windows():
        src_dir = dname.replace(":", "_")
    else:
        src_dir = dname[1:]
    if not salt.utils.platform.is_windows():
        fstat = os.stat(path)
    msecs = str(int(time.time() * 1000000))[-6:]
    if salt.utils.platform.is_windows():
        # ':' is an illegal filesystem path character on Windows
        stamp = time.strftime("%a_%b_%d_%H-%M-%S_%Y")
    else:
        stamp = time.strftime("%a_%b_%d_%H:%M:%S_%Y")
    stamp = f"{stamp[:-4]}{msecs}_{stamp[-4:]}"
    bkpath = os.path.join(bkroot, src_dir, f"{bname}_{stamp}")
    if not os.path.isdir(os.path.dirname(bkpath)):
        os.makedirs(os.path.dirname(bkpath))
    shutil.copyfile(path, bkpath)
    if not salt.utils.platform.is_windows():
        os.chown(bkpath, fstat.st_uid, fstat.st_gid)
        os.chmod(bkpath, fstat.st_mode)


def case_insensitive_filesystem(path=None):
    """
    Detect case insensitivity on a system.

    Returns:
        bool: Flag to indicate case insensitivity

    .. versionadded:: 3004

    """
    with tempfile.NamedTemporaryFile(prefix="TmP", dir=path, delete=True) as tmp_file:
        return os.path.exists(tmp_file.name.lower())


def get_encoding(path):
    """
    Detect a file's encoding using the following:
    - Check for Byte Order Marks (BOM)
    - Check for UTF-8 Markers
    - Check System Encoding
    - Check for ascii

    Args:

        path (str): The path to the file to check

    Returns:
        str: The encoding of the file

    Raises:
        CommandExecutionError: If the encoding cannot be detected
    """

    def check_ascii(_data):
        # If all characters can be decoded to ASCII, then it's ASCII
        try:
            _data.decode("ASCII")
            log.debug("Found ASCII")
        except UnicodeDecodeError:
            return False
        else:
            return True

    def check_bom(_data):
        # Supported Python Codecs
        # https://docs.python.org/2/library/codecs.html
        # https://docs.python.org/3/library/codecs.html
        boms = [
            ("UTF-32-BE", salt.utils.stringutils.to_bytes(codecs.BOM_UTF32_BE)),
            ("UTF-32-LE", salt.utils.stringutils.to_bytes(codecs.BOM_UTF32_LE)),
            ("UTF-16-BE", salt.utils.stringutils.to_bytes(codecs.BOM_UTF16_BE)),
            ("UTF-16-LE", salt.utils.stringutils.to_bytes(codecs.BOM_UTF16_LE)),
            ("UTF-8", salt.utils.stringutils.to_bytes(codecs.BOM_UTF8)),
            ("UTF-7", salt.utils.stringutils.to_bytes("\x2b\x2f\x76\x38\x2D")),
            ("UTF-7", salt.utils.stringutils.to_bytes("\x2b\x2f\x76\x38")),
            ("UTF-7", salt.utils.stringutils.to_bytes("\x2b\x2f\x76\x39")),
            ("UTF-7", salt.utils.stringutils.to_bytes("\x2b\x2f\x76\x2b")),
            ("UTF-7", salt.utils.stringutils.to_bytes("\x2b\x2f\x76\x2f")),
        ]
        for _encoding, bom in boms:
            if _data.startswith(bom):
                log.debug("Found BOM for %s", _encoding)
                return _encoding
        return False

    def check_utf8_markers(_data):
        try:
            decoded = _data.decode("UTF-8")
        except UnicodeDecodeError:
            return False
        else:
            return True

    def check_system_encoding(_data):
        try:
            _data.decode(__salt_system_encoding__)
        except UnicodeDecodeError:
            return False
        else:
            return True

    if not os.path.isfile(path):
        raise CommandExecutionError("Not a file")
    try:
        with fopen(path, "rb") as fp_:
            data = fp_.read(2048)
    except OSError:
        raise CommandExecutionError("Failed to open file")

    # Check for Unicode BOM
    encoding = check_bom(data)
    if encoding:
        return encoding

    # Check for UTF-8 markers
    if check_utf8_markers(data):
        return "UTF-8"

    # Check system encoding
    if check_system_encoding(data):
        return __salt_system_encoding__

    # Check for ASCII first
    if check_ascii(data):
        return "ASCII"

    raise CommandExecutionError("Could not detect file encoding")
