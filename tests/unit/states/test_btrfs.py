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
:platform:      Linux
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch,
)

from salt.exceptions import CommandExecutionError
import salt.utils.platform
import salt.states.btrfs as btrfs


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(salt.utils.platform.is_windows(), 'No BTRFS on Windows')
class BtrfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.btrfs
    '''

    def setup_loader_modules(self):
        return {
            btrfs: {
                '__salt__': {},
                '__states__': {},
                '__utils__': {},
            }
        }

    @patch('salt.states.btrfs._umount')
    @patch('tempfile.mkdtemp')
    def test__mount_fails(self, mkdtemp, umount):
        '''
        Test mounting a device in a temporary place.
        '''
        mkdtemp.return_value = '/tmp/xxx'
        states_mock = {
            'mount.mounted': MagicMock(return_value={'result': False}),
        }
        with patch.dict(btrfs.__states__, states_mock):
            assert btrfs._mount('/dev/sda1') is None
            mkdtemp.assert_called_once()
            states_mock['mount.mounted'].assert_called_with('/tmp/xxx',
                                                            device='/dev/sda1',
                                                            fstype='btrfs',
                                                            opts='subvol=/',
                                                            persist=False)
            umount.assert_called_with('/tmp/xxx')

    @patch('salt.states.btrfs._umount')
    @patch('tempfile.mkdtemp')
    def test__mount(self, mkdtemp, umount):
        '''
        Test mounting a device in a temporary place.
        '''
        mkdtemp.return_value = '/tmp/xxx'
        states_mock = {
            'mount.mounted': MagicMock(return_value={'result': True}),
        }
        with patch.dict(btrfs.__states__, states_mock):
            assert btrfs._mount('/dev/sda1') == '/tmp/xxx'
            mkdtemp.assert_called_once()
            states_mock['mount.mounted'].assert_called_with('/tmp/xxx',
                                                            device='/dev/sda1',
                                                            fstype='btrfs',
                                                            opts='subvol=/',
                                                            persist=False)
            umount.assert_not_called()

    def test__umount(self):
        '''
        Test umounting and cleanning temporary place.
        '''
        states_mock = {
            'mount.unmounted': MagicMock(),
        }
        utils_mock = {
            'files.rm_rf': MagicMock(),
        }
        with patch.dict(btrfs.__states__, states_mock), \
                patch.dict(btrfs.__utils__, utils_mock):
            btrfs._umount('/tmp/xxx')
            states_mock['mount.unmounted'].assert_called_with('/tmp/xxx')
            utils_mock['files.rm_rf'].assert_called_with('/tmp/xxx')

    def test__is_default_not_default(self):
        '''
        Test if the subvolume is the current default.
        '''
        salt_mock = {
            'btrfs.subvolume_show': MagicMock(return_value={
                '@/var': {'subvolume id': '256'},
            }),
            'btrfs.subvolume_get_default': MagicMock(return_value={
                'id': '5',
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert not btrfs._is_default('/tmp/xxx/@/var', '/tmp/xxx', '@/var')
            salt_mock['btrfs.subvolume_show'].assert_called_with('/tmp/xxx/@/var')
            salt_mock['btrfs.subvolume_get_default'].assert_called_with('/tmp/xxx')

    def test__is_default(self):
        '''
        Test if the subvolume is the current default.
        '''
        salt_mock = {
            'btrfs.subvolume_show': MagicMock(return_value={
                '@/var': {'subvolume id': '256'},
            }),
            'btrfs.subvolume_get_default': MagicMock(return_value={
                'id': '256',
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs._is_default('/tmp/xxx/@/var', '/tmp/xxx', '@/var')
            salt_mock['btrfs.subvolume_show'].assert_called_with('/tmp/xxx/@/var')
            salt_mock['btrfs.subvolume_get_default'].assert_called_with('/tmp/xxx')

    def test__set_default(self):
        '''
        Test setting a subvolume as the current default.
        '''
        salt_mock = {
            'btrfs.subvolume_show': MagicMock(return_value={
                '@/var': {'subvolume id': '256'},
            }),
            'btrfs.subvolume_set_default': MagicMock(return_value=True),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs._set_default('/tmp/xxx/@/var', '/tmp/xxx', '@/var')
            salt_mock['btrfs.subvolume_show'].assert_called_with('/tmp/xxx/@/var')
            salt_mock['btrfs.subvolume_set_default'].assert_called_with('256', '/tmp/xxx')

    def test__is_cow_not_cow(self):
        '''
        Test if the subvolume is copy on write.
        '''
        salt_mock = {
            'file.lsattr': MagicMock(return_value={
                '/tmp/xxx/@/var': ['C'],
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert not btrfs._is_cow('/tmp/xxx/@/var')
            salt_mock['file.lsattr'].assert_called_with('/tmp/xxx/@')

    def test__is_cow(self):
        '''
        Test if the subvolume is copy on write.
        '''
        salt_mock = {
            'file.lsattr': MagicMock(return_value={
                '/tmp/xxx/@/var': [],
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs._is_cow('/tmp/xxx/@/var')
            salt_mock['file.lsattr'].assert_called_with('/tmp/xxx/@')

    def test__unset_cow(self):
        '''
        Test disabling the subvolume as copy on write.
        '''
        salt_mock = {
            'file.chattr': MagicMock(return_value=True),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs._unset_cow('/tmp/xxx/@/var')
            salt_mock['file.chattr'].assert_called_with('/tmp/xxx/@/var',
                                                        operator='add',
                                                        attributes='C')

    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_exists(self, mount, umount):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=True),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1') == {
                'name': '@/var',
                'result': True,
                'changes': {},
                'comment': ['Subvolume @/var already present'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_exists_test(self, mount, umount):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=True),
        }
        opts_mock = {
            'test': True,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1') == {
                'name': '@/var',
                'result': None,
                'changes': {},
                'comment': ['Subvolume @/var already present'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._is_default')
    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_exists_was_default(self, mount, umount,
                                                  is_default):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        is_default.return_value = True
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=True),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1',
                                           set_default=True) == {
                'name': '@/var',
                'result': True,
                'changes': {},
                'comment': ['Subvolume @/var already present'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._set_default')
    @patch('salt.states.btrfs._is_default')
    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_exists_set_default(self, mount, umount,
                                                  is_default, set_default):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        is_default.return_value = False
        set_default.return_value = True
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=True),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1',
                                           set_default=True) == {
                'name': '@/var',
                'result': True,
                'changes': {
                    '@/var_default': True
                },
                'comment': ['Subvolume @/var already present'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._set_default')
    @patch('salt.states.btrfs._is_default')
    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_exists_set_default_no_force(self,
                                                           mount,
                                                           umount,
                                                           is_default,
                                                           set_default):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        is_default.return_value = False
        set_default.return_value = True
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=True),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1',
                                           set_default=True,
                                           force_set_default=False) == {
                'name': '@/var',
                'result': True,
                'changes': {},
                'comment': ['Subvolume @/var already present'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._is_cow')
    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_exists_no_cow(self, mount, umount, is_cow):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        is_cow.return_value = False
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=True),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1',
                                           copy_on_write=False) == {
                'name': '@/var',
                'result': True,
                'changes': {},
                'comment': ['Subvolume @/var already present'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._unset_cow')
    @patch('salt.states.btrfs._is_cow')
    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_exists_unset_cow(self, mount, umount,
                                                is_cow, unset_cow):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        is_cow.return_value = True
        unset_cow.return_value = True
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=True),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1',
                                           copy_on_write=False) == {
                'name': '@/var',
                'result': True,
                'changes': {
                    '@/var_no_cow': True
                },
                'comment': ['Subvolume @/var already present'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created(self, mount, umount):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=False),
            'btrfs.subvolume_create': MagicMock(),
        }
        states_mock = {
            'file.directory': MagicMock(return_value={'result': True}),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__states__, states_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1') == {
                'name': '@/var',
                'result': True,
                'changes': {
                    '@/var': 'Created subvolume @/var'
                },
                'comment': [],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            salt_mock['btrfs.subvolume_create'].assert_called_once()
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_fails_directory(self, mount, umount):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=False),
        }
        states_mock = {
            'file.directory': MagicMock(return_value={'result': False}),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__states__, states_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1') == {
                'name': '@/var',
                'result': False,
                'changes': {},
                'comment': ['Error creating /tmp/xxx/@ directory'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            mount.assert_called_once()
            umount.assert_called_once()

    @patch('salt.states.btrfs._umount')
    @patch('salt.states.btrfs._mount')
    def test_subvolume_created_fails(self, mount, umount):
        '''
        Test creating a subvolume.
        '''
        mount.return_value = '/tmp/xxx'
        salt_mock = {
            'btrfs.subvolume_exists': MagicMock(return_value=False),
            'btrfs.subvolume_create': MagicMock(side_effect=CommandExecutionError),
        }
        states_mock = {
            'file.directory': MagicMock(return_value={'result': True}),
        }
        opts_mock = {
            'test': False,
        }
        with patch.dict(btrfs.__salt__, salt_mock), \
                patch.dict(btrfs.__states__, states_mock), \
                patch.dict(btrfs.__opts__, opts_mock):
            assert btrfs.subvolume_created(name='@/var',
                                           device='/dev/sda1') == {
                'name': '@/var',
                'result': False,
                'changes': {},
                'comment': ['Error creating subvolume @/var'],
            }
            salt_mock['btrfs.subvolume_exists'].assert_called_with('/tmp/xxx/@/var')
            salt_mock['btrfs.subvolume_create'].assert_called_once()
            mount.assert_called_once()
            umount.assert_called_once()
