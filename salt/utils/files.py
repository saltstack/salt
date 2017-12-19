# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import Python libs
import contextlib
import errno
import logging
import os
import re
import shutil
import subprocess
import time
import urllib

# Import salt libs
import salt.utils
import salt.modules.selinux
from salt.exceptions import CommandExecutionError, FileLockError, MinionError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

LOCAL_PROTOS = ('', 'file')
REMOTE_PROTOS = ('http', 'https', 'ftp', 'swift', 's3')
VALID_PROTOS = ('salt', 'file') + REMOTE_PROTOS
TEMPFILE_PREFIX = '__salt.tmp.'

HASHES = {
    'sha512': 128,
    'sha384': 96,
    'sha256': 64,
    'sha224': 56,
    'sha1': 40,
    'md5': 32,
}
HASHES_REVMAP = dict([(y, x) for x, y in six.iteritems(HASHES)])


def __clean_tmp(tmp):
    '''
    Remove temporary files
    '''
    try:
        salt.utils.rm_rf(tmp)
    except Exception:
        pass


def guess_archive_type(name):
    '''
    Guess an archive type (tar, zip, or rar) by its file extension
    '''
    name = name.lower()
    for ending in ('tar', 'tar.gz', 'tgz',
                   'tar.bz2', 'tbz2', 'tbz',
                   'tar.xz', 'txz',
                   'tar.lzma', 'tlz'):
        if name.endswith('.' + ending):
            return 'tar'
    for ending in ('zip', 'rar'):
        if name.endswith('.' + ending):
            return ending
    return None


def mkstemp(*args, **kwargs):
    '''
    Should eventually reside here, but for now point back at old location in
    salt.utils
    '''
    return salt.utils.mkstemp(*args, **kwargs)


def recursive_copy(source, dest):
    '''
    Recursively copy the source directory to the destination,
    leaving files with the source does not explicitly overwrite.

    (identical to cp -r on a unix machine)
    '''
    for root, _, files in os.walk(source):
        path_from_source = root.replace(source, '').lstrip(os.sep)
        target_directory = os.path.join(dest, path_from_source)
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
        for name in files:
            file_path_from_source = os.path.join(source, path_from_source, name)
            target_path = os.path.join(target_directory, name)
            shutil.copyfile(file_path_from_source, target_path)


def copyfile(source, dest, backup_mode='', cachedir=''):
    '''
    Copy files from a source to a destination in an atomic way, and if
    specified cache the file.
    '''
    if not os.path.isfile(source):
        raise IOError(
            '[Errno 2] No such file or directory: {0}'.format(source)
        )
    if not os.path.isdir(os.path.dirname(dest)):
        raise IOError(
            '[Errno 2] No such file or directory: {0}'.format(dest)
        )
    bname = os.path.basename(dest)
    dname = os.path.dirname(os.path.abspath(dest))
    tgt = mkstemp(prefix=bname, dir=dname)
    shutil.copyfile(source, tgt)
    bkroot = ''
    if cachedir:
        bkroot = os.path.join(cachedir, 'file_backup')
    if backup_mode == 'minion' or backup_mode == 'both' and bkroot:
        if os.path.exists(dest):
            salt.utils.backup_minion(dest, bkroot)
    if backup_mode == 'master' or backup_mode == 'both' and bkroot:
        # TODO, backup to master
        pass
    # Get current file stats to they can be replicated after the new file is
    # moved to the destination path.
    fstat = None
    if not salt.utils.is_windows():
        try:
            fstat = os.stat(dest)
        except OSError:
            pass

    # The move could fail if the dest has xattr protections, so delete the
    # temp file in this case
    try:
        shutil.move(tgt, dest)
    except Exception:
        __clean_tmp(tgt)
        raise

    if fstat is not None:
        os.chown(dest, fstat.st_uid, fstat.st_gid)
        os.chmod(dest, fstat.st_mode)
    # If SELINUX is available run a restorecon on the file
    rcon = salt.utils.which('restorecon')
    if rcon:
        policy = False
        try:
            policy = salt.modules.selinux.getenforce()
        except (ImportError, CommandExecutionError):
            pass
        if policy == 'Enforcing':
            with salt.utils.fopen(os.devnull, 'w') as dev_null:
                cmd = [rcon, dest]
                subprocess.call(cmd, stdout=dev_null, stderr=dev_null)
    if os.path.isfile(tgt):
        # The temp file failed to move
        __clean_tmp(tgt)


def rename(src, dst):
    '''
    On Windows, os.rename() will fail with a WindowsError exception if a file
    exists at the destination path. This function checks for this error and if
    found, it deletes the destination path first.
    '''
    try:
        os.rename(src, dst)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        try:
            os.remove(dst)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise MinionError(
                    'Error: Unable to remove {0}: {1}'.format(
                        dst,
                        exc.strerror
                    )
                )
        os.rename(src, dst)


def process_read_exception(exc, path):
    '''
    Common code for raising exceptions when reading a file fails
    '''
    if exc.errno == errno.ENOENT:
        raise CommandExecutionError('{0} does not exist'.format(path))
    elif exc.errno == errno.EACCES:
        raise CommandExecutionError(
            'Permission denied reading from {0}'.format(path)
        )
    else:
        raise CommandExecutionError(
            'Error {0} encountered reading from {1}: {2}'.format(
                exc.errno, path, exc.strerror
            )
        )


@contextlib.contextmanager
def wait_lock(path, lock_fn=None, timeout=5, sleep=0.1, time_start=None):
    '''
    Obtain a write lock. If one exists, wait for it to release first
    '''
    if not isinstance(path, six.string_types):
        raise FileLockError('path must be a string')
    if lock_fn is None:
        lock_fn = path + '.w'
    if time_start is None:
        time_start = time.time()
    obtained_lock = False

    def _raise_error(msg, race=False):
        '''
        Raise a FileLockError
        '''
        raise FileLockError(msg, time_start=time_start)

    try:
        if os.path.exists(lock_fn) and not os.path.isfile(lock_fn):
            _raise_error(
                'lock_fn {0} exists and is not a file'.format(lock_fn)
            )

        open_flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        while time.time() - time_start < timeout:
            try:
                # Use os.open() to obtain filehandle so that we can force an
                # exception if the file already exists. Concept found here:
                # http://stackoverflow.com/a/10979569
                fh_ = os.open(lock_fn, open_flags)
            except (IOError, OSError) as exc:
                if exc.errno != errno.EEXIST:
                    _raise_error(
                        'Error {0} encountered obtaining file lock {1}: {2}'
                        .format(exc.errno, lock_fn, exc.strerror)
                    )
                log.trace(
                    'Lock file %s exists, sleeping %f seconds', lock_fn, sleep
                )
                time.sleep(sleep)
            else:
                # Write the lock file
                with os.fdopen(fh_, 'w'):
                    pass
                # Lock successfully acquired
                log.trace('Write lock %s obtained', lock_fn)
                obtained_lock = True
                # Transfer control back to the code inside the with block
                yield
                # Exit the loop
                break

        else:
            _raise_error(
                'Timeout of {0} seconds exceeded waiting for lock_fn {1} '
                'to be released'.format(timeout, lock_fn)
            )

    except FileLockError:
        raise

    except Exception as exc:
        _raise_error(
            'Error encountered obtaining file lock {0}: {1}'.format(
                lock_fn,
                exc
            )
        )

    finally:
        if obtained_lock:
            os.remove(lock_fn)
            log.trace('Write lock for %s (%s) released', path, lock_fn)


@contextlib.contextmanager
def set_umask(mask):
    '''
    Temporarily set the umask and restore once the contextmanager exits
    '''
    if salt.utils.is_windows():
        # Don't attempt on Windows
        yield
    else:
        try:
            orig_mask = os.umask(mask)
            yield
        finally:
            os.umask(orig_mask)


def safe_filename_leaf(file_basename):
    '''
    Input the basename of a file, without the directory tree, and returns a safe name to use
    i.e. only the required characters are converted by urllib.quote
    If the input is a PY2 String, output a PY2 String. If input is Unicode output Unicode.
    For consistency all platforms are treated the same. Hard coded to utf8 as its ascii compatible
    windows is \\ / : * ? " < > | posix is /

    .. versionadded:: 2017.7.2

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    '''
    def _replace(re_obj):
        return urllib.quote(re_obj.group(0), safe=u'')
    if not isinstance(file_basename, six.text_type):
        # the following string is not prefixed with u
        return re.sub('[\\\\:/*?"<>|]',
                      _replace,
                      six.text_type(file_basename, 'utf8').encode('ascii', 'backslashreplace'))
    # the following string is prefixed with u
    return re.sub(u'[\\\\:/*?"<>|]', _replace, file_basename, flags=re.UNICODE)


def safe_filepath(file_path_name, dir_sep=None):
    '''
    Input the full path and filename, splits on directory separator and calls safe_filename_leaf for
    each part of the path. dir_sep allows coder to force a directory separate to a particular character

    .. versionadded:: 2017.7.2

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    '''
    if not dir_sep:
        dir_sep = os.sep
    # Normally if file_path_name or dir_sep is Unicode then the output will be Unicode
    # This code ensure the output type is the same as file_path_name
    if not isinstance(file_path_name, six.text_type) and isinstance(dir_sep, six.text_type):
        dir_sep = dir_sep.encode('ascii')  # This should not be executed under PY3
    # splitdrive only set drive on windows platform
    (drive, path) = os.path.splitdrive(file_path_name)
    path = dir_sep.join([safe_filename_leaf(file_section) for file_section in path.rsplit(dir_sep)])
    if drive:
        path = dir_sep.join([drive, path])
    return path


def remove(path):
    '''
    Runs os.remove(path) and suppresses the OSError if the file doesn't exist
    '''
    try:
        os.remove(path)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise
