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
import functools
import logging
import os.path
import tempfile

from salt.exceptions import CommandExecutionError
from salt.ext import six

log = logging.getLogger(__name__)

__virtualname__ = 'btrfs'


def _mount(device):
    '''
    Mount the device in a temporary place.
    '''
    dest = tempfile.mkdtemp()
    res = __states__['mount.mounted'](dest, device=device, fstype='btrfs',
                                      opts='subvol=/', persist=False)
    if not res['result']:
        log.error('Cannot mount device %s in %s', device, dest)
        _umount(dest)
        return None
    return dest


def _umount(path):
    '''
    Umount and clean the temporary place.
    '''
    __states__['mount.unmounted'](path)
    __utils__['files.rm_rf'](path)


def _is_default(path, dest, name):
    '''
    Check if the subvolume is the current default.
    '''
    subvol_id = __salt__['btrfs.subvolume_show'](path)[name]['subvolume id']
    def_id = __salt__['btrfs.subvolume_get_default'](dest)['id']
    return subvol_id == def_id


def _set_default(path, dest, name):
    '''
    Set the subvolume as the current default.
    '''
    subvol_id = __salt__['btrfs.subvolume_show'](path)[name]['subvolume id']
    return __salt__['btrfs.subvolume_set_default'](subvol_id, dest)


def _is_cow(path):
    '''
    Check if the subvolume is copy on write
    '''
    dirname = os.path.dirname(path)
    return 'C' not in __salt__['file.lsattr'](dirname)[path]


def _unset_cow(path):
    '''
    Disable the copy on write in a subvolume
    '''
    return __salt__['file.chattr'](path, operator='add', attributes='C')


def __mount_device(action):
    '''
    Small decorator to makes sure that the mount and umount happends in
    a transactional way.
    '''
    @functools.wraps(action)
    def wrapper(*args, **kwargs):
        name = kwargs['name']
        device = kwargs['device']

        ret = {
            'name': name,
            'result': False,
            'changes': {},
            'comment': ['Some error happends during the operation.'],
        }
        try:
            dest = _mount(device)
            if not dest:
                msg = 'Device {} cannot be mounted'.format(device)
                ret['comment'].append(msg)
            kwargs['__dest'] = dest
            ret = action(*args, **kwargs)
        except Exception as e:
            log.exception('Encountered error mounting %s', device)
            ret['comment'].append(six.text_type(e))
        finally:
            _umount(dest)
        return ret
    return wrapper


@__mount_device
def subvolume_created(name, device, qgroupids=None, set_default=False,
                      copy_on_write=True, force_set_default=True,
                      __dest=None):
    '''
    Makes sure that a btrfs subvolume is present.

    name
        Name of the subvolume to add

    device
        Device where to create the subvolume

    qgroupids
         Add the newly created subcolume to a qgroup. This parameter
         is a list

    set_default
        If True, this new subvolume will be set as default when
        mounted, unless subvol option in mount is used

    copy_on_write
        If false, set the subvolume with chattr +C

    force_set_default
        If false and the subvolume is already present, it will not
        force it as default if ``set_default`` is True

    '''
    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': [],
    }
    path = os.path.join(__dest, name)

    exists = __salt__['btrfs.subvolume_exists'](path)
    if exists:
        ret['comment'].append('Subvolume {} already present'.format(name))

    # Resolve first the test case. The check is not complete, but at
    # least we will report if a subvolume needs to be created. Can
    # happend that the subvolume is there, but we also need to set it
    # as default, or persist in fstab.
    if __opts__['test']:
        ret['result'] = None
        if not exists:
            ret['comment'].append('Subvolume {} will be created'.format(name))
        return ret

    if not exists:
        # Create the directories where the subvolume lives
        _path = os.path.dirname(path)
        res = __states__['file.directory'](_path, makedirs=True)
        if not res['result']:
            ret['comment'].append('Error creating {} directory'.format(_path))
            return ret

        try:
            __salt__['btrfs.subvolume_create'](name, dest=__dest,
                                               qgroupids=qgroupids)
        except CommandExecutionError:
            ret['comment'].append('Error creating subvolume {}'.format(name))
            return ret

        ret['changes'][name] = 'Created subvolume {}'.format(name)

    # If the volume was already present, we can opt-out the check for
    # default subvolume.
    if (not exists or (exists and force_set_default)) and \
       set_default and not _is_default(path, __dest, name):
        ret['changes'][name + '_default'] = _set_default(path, __dest, name)

    if not copy_on_write and _is_cow(path):
        ret['changes'][name + '_no_cow'] = _unset_cow(path)

    ret['result'] = True
    return ret


@__mount_device
def subvolume_deleted(name, device, commit=False, __dest=None):
    '''
    Makes sure that a btrfs subvolume is removed.

    name
        Name of the subvolume to remove

    device
        Device where to remove the subvolume

    commit
        Wait until the transaction is over

    '''
    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': [],
    }

    path = os.path.join(__dest, name)

    exists = __salt__['btrfs.subvolume_exists'](path)
    if not exists:
        ret['comment'].append('Subvolume {} already missing'.format(name))

    if __opts__['test']:
        ret['result'] = None
        if exists:
            ret['comment'].append('Subvolume {} will be removed'.format(name))
        return ret

    # If commit is set, we wait until all is over
    commit = 'after' if commit else None

    if not exists:
        try:
            __salt__['btrfs.subvolume_delete'](path, commit=commit)
        except CommandExecutionError:
            ret['comment'].append('Error removing subvolume {}'.format(name))
            return ret

        ret['changes'][name] = 'Removed subvolume {}'.format(name)

    ret['result'] = True
    return ret
