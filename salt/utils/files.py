# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import Python libs
import os
import shutil
import subprocess

# Import salt libs
import salt.utils
import salt.modules.selinux
from salt.exceptions import CommandExecutionError


def recursive_copy(source, dest):
    '''
    Recursively copy the source directory to the destination,
    leaving files with the source does not explicitly overwrite.

    (identical to cp -r on a unix machine)
    '''
    for root, _, files in os.walk(source):
        path_from_source = root.replace(source, '').lstrip('/')
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
    tgt = salt.utils.mkstemp(prefix=bname, dir=dname)
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
    shutil.move(tgt, dest)
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
        try:
            os.remove(tgt)
        except Exception:
            pass
