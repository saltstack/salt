# -*- coding: utf-8 -*-
'''
Wrapper for rsync

.. versionadded:: 2014.1.0

This data can also be passed into :ref:`pillar <pillar-walk-through>`.
Options passed into opts will overwrite options passed into pillar.
'''
from __future__ import absolute_import

# Import python libs
import errno
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = 'rsync'


def __virtual__():
    '''
    Only load module if rsync binary is present
    '''
    if salt.utils.which('rsync'):
        return __virtualname__
    return (False, 'The rsync execution module cannot be loaded: '
            'the rsync binary is not in the path.')


def _check(delete, force, update, passwordfile, exclude, excludefrom, dryrun):
    '''
    Generate rsync options
    '''
    options = ['-avz']

    if delete:
        options.append('--delete')
    if force:
        options.append('--force')
    if update:
        options.append('--update')
    if passwordfile:
        options.extend(['--password-file', passwordfile])
    if excludefrom:
        options.extend(['--exclude-from', excludefrom])
        if exclude:
            exclude = False
    if exclude:
        options.extend(['--exclude', exclude])
    if dryrun:
        options.append('--dry-run')
    return options


def rsync(src,
          dst,
          delete=False,
          force=False,
          update=False,
          passwordfile=None,
          exclude=None,
          excludefrom=None,
          dryrun=False):
    '''
    .. versionchanged:: 2016.3.0
        Return data now contains just the output of the rsync command, instead
        of a dictionary as returned from :py:func:`cmd.run_all
        <salt.modules.cmdmod.run_all>`.

    Rsync files from src to dst

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.rsync {src} {dst} {delete=True} {update=True} {passwordfile=/etc/pass.crt} {exclude=xx}
        salt '*' rsync.rsync {src} {dst} {delete=True} {excludefrom=/xx.ini}
    '''
    if not src:
        src = __salt__['config.option']('rsync.src')
    if not dst:
        dst = __salt__['config.option']('rsync.dst')
    if not delete:
        delete = __salt__['config.option']('rsync.delete')
    if not force:
        force = __salt__['config.option']('rsync.force')
    if not update:
        update = __salt__['config.option']('rsync.update')
    if not passwordfile:
        passwordfile = __salt__['config.option']('rsync.passwordfile')
    if not exclude:
        exclude = __salt__['config.option']('rsync.exclude')
    if not excludefrom:
        excludefrom = __salt__['config.option']('rsync.excludefrom')
    if not dryrun:
        dryrun = __salt__['config.option']('rsync.dryrun')
    if not src or not dst:
        raise SaltInvocationError('src and dst cannot be empty')

    option = _check(delete, force, update, passwordfile, exclude, excludefrom, dryrun)
    cmd = ['rsync'] + option + [src, dst]
    log.debug('Running rsync command: {0}'.format(cmd))
    try:
        return __salt__['cmd.run_all'](cmd, python_shell=False)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)


def version():
    '''
    .. versionchanged:: 2016.3.0
        Return data now contains just the version number as a string, instead
        of a dictionary as returned from :py:func:`cmd.run_all
        <salt.modules.cmdmod.run_all>`.

    Returns rsync version

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.version
    '''
    try:
        out = __salt__['cmd.run_stdout'](
            ['rsync', '--version'],
            python_shell=False)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)
    try:
        return out.split('\n')[0].split()[2]
    except IndexError:
        raise CommandExecutionError('Unable to determine rsync version')


def config(conf_path='/etc/rsyncd.conf'):
    '''
    .. versionchanged:: 2016.3.0
        Return data now contains just the contents of the rsyncd.conf as a
        string, instead of a dictionary as returned from :py:func:`cmd.run_all
        <salt.modules.cmdmod.run_all>`.

    Returns the contents of the rsync config file

    conf_path : /etc/rsyncd.conf
        Path to the config file

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.config
    '''
    ret = ''
    try:
        with salt.utils.fopen(conf_path, 'r') as fp_:
            for line in fp_:
                ret += line
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            raise CommandExecutionError('{0} does not exist'.format(conf_path))
        elif exc.errno == errno.EACCES:
            raise CommandExecutionError(
                'Unable to read {0}, access denied'.format(conf_path)
            )
        elif exc.errno == errno.EISDIR:
            raise CommandExecutionError(
                'Unable to read {0}, path is a directory'.format(conf_path)
            )
        else:
            raise CommandExecutionError(
                'Error {0}: {1}'.format(exc.errno, exc.strerror)
            )
    else:
        return ret
