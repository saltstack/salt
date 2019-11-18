# -*- coding: utf-8 -*-

'''
:maintainer:    Alberto Planas <aplanas@suse.com>
:maturity:      new
:depends:       None
:platform:      Linux
'''
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import sys
import tempfile

from salt.defaults.exitcodes import EX_OK
from salt.exceptions import CommandExecutionError
from salt.utils.args import clean_kwargs

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Chroot command is required.
    '''
    if __utils__['path.which']('chroot') is not None:
        return True
    else:
        return (False, 'Module chroot requires the command chroot')


def exist(root):
    '''
    Return True if the chroot environment is present.
    '''
    dev = os.path.join(root, 'dev')
    proc = os.path.join(root, 'proc')
    sys = os.path.join(root, 'sys')
    return all(os.path.isdir(i) for i in (root, dev, proc, sys))


def create(root):
    '''
    Create a basic chroot environment.

    Note that this environment is not functional. The caller needs to
    install the minimal required binaries, including Python if
    chroot.call is called.

    root
        Path to the chroot environment

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.create /chroot

    '''
    if not exist(root):
        dev = os.path.join(root, 'dev')
        proc = os.path.join(root, 'proc')
        sys = os.path.join(root, 'sys')
        try:
            os.makedirs(dev, mode=0o755)
            os.makedirs(proc, mode=0o555)
            os.makedirs(sys, mode=0o555)
        except OSError as e:
            log.error('Error when trying to create chroot directories: %s', e)
            return False
    return True


def call(root, function, *args, **kwargs):
    '''
    Executes a Salt function inside a chroot environment.

    The chroot does not need to have Salt installed, but Python is
    required.

    root
        Path to the chroot environment

    function
        Salt execution module function

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.call /chroot test.ping
        salt myminion chroot.call /chroot ssh.set_auth_key user key=mykey

    '''

    if not function:
        raise CommandExecutionError('Missing function parameter')

    if not exist(root):
        raise CommandExecutionError('Chroot environment not found')

    # Create a temporary directory inside the chroot where we can
    # untar salt-thin
    thin_dest_path = tempfile.mkdtemp(dir=root)
    thin_path = __utils__['thin.gen_thin'](
        __opts__['cachedir'],
        extra_mods=__salt__['config.option']('thin_extra_mods', ''),
        so_mods=__salt__['config.option']('thin_so_mods', '')
    )
    # Some bug in Salt is preventing us to use `archive.tar` here. A
    # AsyncZeroMQReqChannel is not closed at the end os the salt-call,
    # and makes the client never exit.
    #
    # stdout = __salt__['archive.tar']('xzf', thin_path, dest=thin_dest_path)
    #
    stdout = __salt__['cmd.run'](['tar', 'xzf', thin_path,
                                  '-C', thin_dest_path])
    if stdout:
        __utils__['files.rm_rf'](thin_dest_path)
        return {'result': False, 'comment': stdout}

    chroot_path = os.path.join(os.path.sep,
                               os.path.relpath(thin_dest_path, root))
    try:
        safe_kwargs = clean_kwargs(**kwargs)
        salt_argv = [
            'python{}'.format(sys.version_info[0]),
            os.path.join(chroot_path, 'salt-call'),
            '--metadata',
            '--local',
            '--log-file', os.path.join(chroot_path, 'log'),
            '--cachedir', os.path.join(chroot_path, 'cache'),
            '--out', 'json',
            '-l', 'quiet',
            '--',
            function
        ] + list(args) + ['{}={}'.format(k, v) for (k, v) in safe_kwargs.items()]
        ret = __salt__['cmd.run_chroot'](root, [str(x) for x in salt_argv])

        # Process "real" result in stdout
        try:
            data = __utils__['json.find_json'](ret['stdout'])
            local = data.get('local', data)
            if isinstance(local, dict) and 'retcode' in local:
                __context__['retcode'] = local['retcode']
            return local.get('return', data)
        except (KeyError, ValueError):
            return {
                'result': False,
                'comment': "Can't parse container command output"
            }
    finally:
        __utils__['files.rm_rf'](thin_dest_path)
