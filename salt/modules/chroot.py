# -*- coding: utf-8 -*-
#
# Author: Alberto Planas <aplanas@suse.com>
#
# Copyright 2018 SUSE LINUX GmbH, Nuernberg, Germany.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

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


def exist(name):
    '''
    Return True if the chroot environment is present.
    '''
    dev = os.path.join(name, 'dev')
    proc = os.path.join(name, 'proc')
    return all(os.path.isdir(i) for i in (name, dev, proc))


def create(name):
    '''
    Create a basic chroot environment.

    Note that this environment is not functional. The caller needs to
    install the minimal required binaries, including Python if
    chroot.call is called.

    name
        Path to the chroot environment

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.create /chroot

    '''
    if not exist(name):
        dev = os.path.join(name, 'dev')
        proc = os.path.join(name, 'proc')
        try:
            os.makedirs(dev, mode=0o755)
            os.makedirs(proc, mode=0o555)
        except OSError as e:
            log.error('Error when trying to create chroot directories: %s', e)
            return False
    return True


def call(name, function, *args, **kwargs):
    '''
    Executes a Salt function inside a chroot environment.

    The chroot does not need to have Salt installed, but Python is
    required.

    name
        Path to the chroot environment

    function
        Salt execution module function

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.call /chroot test.ping

    '''

    if not function:
        raise CommandExecutionError('Missing function parameter')

    if not exist(name):
        raise CommandExecutionError('Chroot environment not found')

    # Create a temporary directory inside the chroot where we can
    # untar salt-thin
    thin_dest_path = tempfile.mkdtemp(dir=name)
    thin_path = __utils__['thin.gen_thin'](
        __opts__['cachedir'],
        extra_mods=__salt__['config.option']('thin_extra_mods', ''),
        so_mods=__salt__['config.option']('thin_so_mods', '')
    )
    stdout = __salt__['archive.tar']('xzf', thin_path, dest=thin_dest_path)
    if stdout:
        __utils__['files.rm_rf'](thin_dest_path)
        return {'result': False, 'comment': stdout}

    chroot_path = os.path.join(os.path.sep,
                               os.path.relpath(thin_dest_path, name))
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
        ] + list(args) + ['{}={}'.format(k, v) for (k, v) in safe_kwargs]
        ret = __salt__['cmd.run_chroot'](name, [str(x) for x in salt_argv])
        if ret['retcode'] != EX_OK:
            raise CommandExecutionError(ret['stderr'])

        # Process "real" result in stdout
        try:
            data = __utils__['json.find_json'](ret['stdout'])
            local = data.get('local', data)
            if isinstance(local, dict) and 'retcode' in local:
                __context__['retcode'] = local['retcode']
            return local.get('return', data)
        except ValueError:
            return {
                'result': False,
                'comment': "Can't parse container command output"
            }
    finally:
        __utils__['files.rm_rf'](thin_dest_path)
