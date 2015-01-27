# -*- coding: utf-8 -*-
'''
Wrapper for rsync

.. versionadded:: 2014.1.0

This data can also be passed into :doc:`pillar </topics/tutorials/pillar>`.
Options passed into opts will overwrite options passed into pillar.
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import salt libs
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _check(delete, force, update, passwordfile, exclude, excludefrom):
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
        options.append('--password-file={0}'.format(passwordfile))
    if excludefrom:
        options.append('--exclude-from={0}'.format(excludefrom))
        if exclude:
            exclude = None
    if exclude:
        options.append('--exclude={0}'.format(exclude))

    return ' '.join(options)


def rsync(src,
          dst,
          delete=False,
          force=False,
          update=False,
          passwordfile=None,
          exclude=None,
          excludefrom=None,
          ):
    '''
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
    if not src or not dst:
        raise CommandExecutionError('ERROR: src and dst cannot be empty.')

    option = _check(delete, force, update, passwordfile, exclude, excludefrom)
    cmd = (
        r'''rsync {option} {src} {dst}'''
        .format(
            option=option,
            src=src,
            dst=dst,
        )
    )

    try:
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)

    return ret


def version():
    '''
    Return rsync version

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.version
    '''

    cmd = (r'''rsync --version''')

    try:
        ret = __salt__['cmd.run_all'](cmd)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)

    ret['stdout'] = ret['stdout'].split('\n')[0].split()[2]
    return ret


def config(confile='/etc/rsyncd.conf'):
    '''
    Return rsync config

    CLI Example:

    .. code-block:: bash

        salt '*' rsync.config
    '''

    if not os.path.isfile(confile):
        raise CommandExecutionError('{0!r} does not exit'.format(confile))

    cmd = (
          r'''cat {confile}'''
              .format(
                   confile=confile
               )
          )

    try:
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)

    return ret
