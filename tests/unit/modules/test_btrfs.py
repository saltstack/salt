# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import pytest

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.utils.files
import salt.utils.fsutils
import salt.utils.platform
import salt.modules.btrfs as btrfs
from salt.exceptions import CommandExecutionError


class BtrfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.btrfs
    '''
    def setup_loader_modules(self):
        return {btrfs: {'__salt__': {}}}

    # 'version' function tests: 1
    def test_version(self):
        '''
        Test if it return BTRFS version.
        '''
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(btrfs.version(), {'version': 'Salt'})

    # 'info' function tests: 1

    def test_info(self):
        '''
        Test if it get BTRFS filesystem information.
        '''
        with patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'Salt': 'salt'})
                with patch.object(btrfs, '_parse_btrfs_info', mock):
                    self.assertDictEqual(btrfs.info('/dev/sda1'),
                                         {'Salt': 'salt'})

    # 'devices' function tests: 1

    def test_devices(self):
        '''
        Test if it get known BTRFS formatted devices on the system.
        '''
        with patch('salt.utils.fsutils._blkid_output',
                   MagicMock(return_value='Salt')):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                self.assertEqual(btrfs.devices(), 'Salt')

    # 'defragment' function tests: 2

    def test_defragment(self):
        '''
        Test if it defragment mounted BTRFS filesystem.
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=False)):
            with patch('os.path.exists', MagicMock(return_value=True)):
                ret = [{'range': '/dev/sda1',
                        'mount_point': False,
                        'log': False, 'passed': True}]
                mock_run = MagicMock(return_value={'retcode': 1,
                                                   'stderr': '',
                                                   'stdout': 'Salt'})
                with patch.dict(btrfs.__salt__, {'cmd.run_all': mock_run}):
                    mock_file = mock_open(read_data='/dev/sda1 / ext4 rw,data=ordered 0 0')
                    with patch.object(salt.utils.files, 'fopen', mock_file):
                        self.assertListEqual(btrfs.defragment('/dev/sda1'), ret)

    def test_defragment_error(self):
        '''
        Test if it gives device not mount error
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=True)):
            mock_run = MagicMock(return_value={'retcode': 1,
                                               'stderr': '',
                                               'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock_run}):
                mock_file = mock_open(read_data='/dev/sda1 / ext4 rw,data=ordered 0 0')
                with patch.object(salt.utils.files, 'fopen', mock_file):
                    self.assertRaises(CommandExecutionError, btrfs.defragment,
                                      '/dev/sda1')

    # 'features' function tests: 1

    def test_features(self):
        '''
        Test if it list currently available BTRFS features.
        '''
        with patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                self.assertDictEqual(btrfs.features(), {})

    # 'usage' function tests: 1

    def test_usage(self):
        '''
        Test if it shows in which disk the chunks are allocated.
        '''
        with patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'Salt': 'salt'})
                with patch.object(btrfs, '_usage_specific', mock):
                    self.assertDictEqual(btrfs.usage('/dev/sda1'),
                                         {'Salt': 'salt'})

            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Unallocated:\n'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'/dev/sda1': True})
                with patch.object(btrfs, '_usage_unallocated', mock):
                    self.assertDictEqual(btrfs.usage('/dev/sda1'),
                                         {'unallocated': {'/dev/sda1': True}})

            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Overall:\n'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'/dev/sda1': True})
                with patch.object(btrfs, '_usage_overall', mock):
                    self.assertDictEqual(btrfs.usage('/dev/sda1'),
                                         {'overall': {'/dev/sda1': True}})

    # 'mkfs' function tests: 3

    def test_mkfs(self):
        '''
        Test if it create a file system on the specified device.
        '''
        mock_cmd = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
        mock_info = MagicMock(return_value=[])
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock_cmd,
                                         'btrfs.info': mock_info}):
            mock_file = mock_open(read_data='/dev/sda1 / ext4 rw,data=ordered 0 0')
            with patch.object(salt.utils.files, 'fopen', mock_file):
                self.assertDictEqual(btrfs.mkfs('/dev/sda1'), {'log': 'Salt'})

    def test_mkfs_error(self):
        '''
        Test if it No devices specified error
        '''
        self.assertRaises(CommandExecutionError, btrfs.mkfs)

    def test_mkfs_mount_error(self):
        '''
        Test if it device mount error
        '''
        mock = MagicMock(return_value={'/dev/sda1': True})
        with patch.object(salt.utils.fsutils, '_get_mounts', mock):
            self.assertRaises(CommandExecutionError, btrfs.mkfs, '/dev/sda1')

    # 'resize' function tests: 4

    def test_resize(self):
        '''
        Test if it resize filesystem.
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            mock_info = MagicMock(return_value=[])
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock,
                                             'btrfs.info': mock_info}):
                mock = MagicMock(return_value={'/dev/sda1': True})
                with patch.object(salt.utils.fsutils, '_get_mounts', mock):
                    self.assertDictEqual(btrfs.resize('/dev/sda1', 'max'),
                                         {'log': 'Salt'})

    def test_resize_valid_error(self):
        '''
        Test if it gives device should be mounted error
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=False)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(CommandExecutionError, btrfs.resize,
                                  '/dev/sda1', 'max')

    def test_resize_mount_error(self):
        '''
        Test if it gives mount point error
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'/dev/sda1': False})
            with patch.object(salt.utils.fsutils, '_get_mounts', mock):
                self.assertRaises(CommandExecutionError, btrfs.resize,
                                  '/dev/sda1', 'max')

    def test_resize_size_error(self):
        '''
        Test if it gives unknown size error
        '''
        self.assertRaises(CommandExecutionError, btrfs.resize,
                          '/dev/sda1', '250m')

    # 'convert' function tests: 5

    def test_convert(self):
        '''
        Test if it convert ext2/3/4 to BTRFS
        '''
        with patch('os.path.exists', MagicMock(return_value=True)):
            ret = {'after': {'balance_log': 'Salt',
                             'ext4_image': 'removed',
                             'ext4_image_info': 'N/A',
                             'fsck_status': 'N/A',
                             'mount_point': None,
                             'type': 'ext4'},
                   'before': {'fsck_status': 'Filesystem errors corrected',
                              'mount_point': None,
                              'type': 'ext4'}}
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'/dev/sda3': {'type': 'ext4'}})
                with patch.object(salt.utils.fsutils, '_blkid_output', mock):
                    mock = MagicMock(return_value={'/dev/sda3': [{'mount_point': None}]})
                    with patch.object(salt.utils.fsutils, '_get_mounts', mock):
                        self.assertDictEqual(btrfs.convert('/dev/sda3', permanent=True),
                                            ret)

    def test_convert_device_error(self):
        '''
        Test if it gives device not found error
        '''
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
            mock = MagicMock(return_value={'/dev/sda1': False})
            with patch.object(salt.utils.fsutils, '_blkid_output', mock):
                self.assertRaises(CommandExecutionError, btrfs.convert,
                                  '/dev/sda1')

    def test_convert_filesystem_error(self):
        '''
        Test if it gives file system error
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'/dev/sda1': {'type': 'ext'}})
                with patch.object(salt.utils.fsutils, '_blkid_output', mock):
                    self.assertRaises(CommandExecutionError, btrfs.convert,
                                      '/dev/sda1')

    def test_convert_error(self):
        '''
        Test if it gives error cannot convert root
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'/dev/sda1': {'type': 'ext4',
                                                             'mount_point': '/'}})
                with patch.object(salt.utils.fsutils, '_blkid_output', mock):
                    mock = MagicMock(return_value={'/dev/sda1':
                                                   [{'mount_point': '/'}]})
                    with patch.object(salt.utils.fsutils, '_get_mounts', mock):
                        self.assertRaises(CommandExecutionError, btrfs.convert,
                                          '/dev/sda1')

    def test_convert_migration_error(self):
        '''
        Test if it gives migration error
        '''
        with patch('salt.utils.fsutils._is_device', MagicMock(return_value=True)):
            mock_run = MagicMock(return_value={'retcode': 1,
                                               'stderr': '',
                                               'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock_run}):
                mock_blk = MagicMock(return_value={'/dev/sda1': {'type': 'ext4'}})
                with patch.object(salt.utils.fsutils, '_blkid_output', mock_blk):
                    mock_file = mock_open(read_data='/dev/sda1 / ext4 rw,data=ordered 0 0')
                    with patch.object(salt.utils.files, 'fopen', mock_file):
                        self.assertRaises(CommandExecutionError, btrfs.convert,
                                          '/dev/sda1')

    # 'add' function tests: 1

    def test_add(self):
        '''
        Test if it add a devices to a BTRFS filesystem.
        '''
        with patch('salt.modules.btrfs._restripe', MagicMock(return_value={})):
            self.assertDictEqual(btrfs.add('/mountpoint', '/dev/sda1', '/dev/sda2'), {})

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test if it delete a devices to a BTRFS filesystem.
        '''
        with patch('salt.modules.btrfs._restripe', MagicMock(return_value={})):
            self.assertDictEqual(btrfs.delete('/mountpoint', '/dev/sda1',
                                              '/dev/sda2'), {})

    # 'properties' function tests: 1

    def test_properties(self):
        '''
        Test if list properties for given btrfs object
        '''
        with patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True)):
            mock = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
            with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
                self.assertDictEqual(btrfs.properties('/dev/sda1', 'subvol'), {})

    def test_properties_unknown_error(self):
        '''
        Test if it gives unknown property error
        '''
        self.assertRaises(CommandExecutionError, btrfs.properties,
                          '/dev/sda1', 'a')

    def test_properties_error(self):
        '''
        Test if it gives exception error
        '''
        self.assertRaises(CommandExecutionError, btrfs.properties,
                          '/dev/sda1', 'subvol', True)

    def test_subvolume_exists(self):
        '''
        Test subvolume_exists
        '''
        salt_mock = {
            'cmd.retcode': MagicMock(return_value=0),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_exists('/mnt/one')

    def test_subvolume_not_exists(self):
        '''
        Test subvolume_exists
        '''
        salt_mock = {
            'cmd.retcode': MagicMock(return_value=1),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert not btrfs.subvolume_exists('/mnt/nowhere')

    def test_subvolume_create_fails_parameters(self):
        '''
        Test btrfs subvolume create
        '''
        # Fails when qgroupids is not a list
        with pytest.raises(CommandExecutionError):
            btrfs.subvolume_create('var', qgroupids='1')

    @patch('salt.modules.btrfs.subvolume_exists')
    def test_subvolume_create_already_exists(self, subvolume_exists):
        '''
        Test btrfs subvolume create
        '''
        subvolume_exists.return_value = True
        assert not btrfs.subvolume_create('var', dest='/mnt')

    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows')
    @patch('salt.modules.btrfs.subvolume_exists')
    def test_subvolume_create(self, subvolume_exists):
        '''
        Test btrfs subvolume create
        '''
        subvolume_exists.return_value = False
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={'recode': 0}),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_create('var', dest='/mnt')
            subvolume_exists.assert_called_once()
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'create', '/mnt/var'])

    def test_subvolume_delete_fails_parameters(self):
        '''
        Test btrfs subvolume delete
        '''
        # We need to provide name or names
        with pytest.raises(CommandExecutionError):
            btrfs.subvolume_delete()

        with pytest.raises(CommandExecutionError):
            btrfs.subvolume_delete(names='var')

    def test_subvolume_delete_fails_parameter_commit(self):
        '''
        Test btrfs subvolume delete
        '''
        # Parameter commit can be 'after' or 'each'
        with pytest.raises(CommandExecutionError):
            btrfs.subvolume_delete(name='var', commit='maybe')

    @patch('salt.modules.btrfs.subvolume_exists')
    def test_subvolume_delete_already_missing(self, subvolume_exists):
        '''
        Test btrfs subvolume delete
        '''
        subvolume_exists.return_value = False
        assert not btrfs.subvolume_delete(name='var', names=['tmp'])

    @patch('salt.modules.btrfs.subvolume_exists')
    def test_subvolume_delete_already_missing_name(self, subvolume_exists):
        '''
        Test btrfs subvolume delete
        '''
        subvolume_exists.return_value = False
        assert not btrfs.subvolume_delete(name='var')

    @patch('salt.modules.btrfs.subvolume_exists')
    def test_subvolume_delete_already_missing_names(self, subvolume_exists):
        '''
        Test btrfs subvolume delete
        '''
        subvolume_exists.return_value = False
        assert not btrfs.subvolume_delete(names=['tmp'])

    @patch('salt.modules.btrfs.subvolume_exists')
    def test_subvolume_delete(self, subvolume_exists):
        '''
        Test btrfs subvolume delete
        '''
        subvolume_exists.return_value = True
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={'recode': 0}),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_delete('var', names=['tmp'])
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'delete', 'var', 'tmp'])

    def test_subvolume_find_new_empty(self):
        '''
        Test btrfs subvolume find-new
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={
                'recode': 0,
                'stdout': 'transid marker was 1024'
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_find_new('var', '2000') == {
                'files': [],
                'transid': '1024'
            }
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'find-new', 'var', '2000'])

    def test_subvolume_find_new(self):
        '''
        Test btrfs subvolume find-new
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={
                'recode': 0,
                'stdout': '''inode 185148 ... gen 2108 flags NONE var/log/audit/audit.log
inode 187390 ... INLINE etc/openvpn/openvpn-status.log
transid marker was 1024'''
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_find_new('var', '1023') == {
                'files': ['var/log/audit/audit.log',
                          'etc/openvpn/openvpn-status.log'],
                'transid': '1024'
            }
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'find-new', 'var', '1023'])

    def test_subvolume_get_default_free(self):
        '''
        Test btrfs subvolume get-default
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={
                'recode': 0,
                'stdout': 'ID 5 (FS_TREE)',
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_get_default('/mnt') == {
                'id': '5',
                'name': '(FS_TREE)',
            }
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'get-default', '/mnt'])

    def test_subvolume_get_default(self):
        '''
        Test btrfs subvolume get-default
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={
                'recode': 0,
                'stdout': 'ID 257 gen 8 top level 5 path var',
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_get_default('/mnt') == {
                'id': '257',
                'name': 'var',
            }
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'get-default', '/mnt'])

    def test_subvolume_list_fails_parameters(self):
        '''
        Test btrfs subvolume list
        '''
        # Fails when sort is not a list
        with pytest.raises(CommandExecutionError):
            btrfs.subvolume_list('/mnt', sort='-rootid')

        # Fails when sort is not recognized
        with pytest.raises(CommandExecutionError):
            btrfs.subvolume_list('/mnt', sort=['-root'])

    def test_subvolume_list_simple(self):
        '''
        Test btrfs subvolume list
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={
                'recode': 0,
                'stdout': '''ID 257 gen 8 top level 5 path one
ID 258 gen 10 top level 5 path another one
''',
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_list('/mnt') == [
                {
                    'id': '257',
                    'gen': '8',
                    'top level': '5',
                    'path': 'one',
                },
                {
                    'id': '258',
                    'gen': '10',
                    'top level': '5',
                    'path': 'another one',
                },
            ]
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'list', '/mnt'])

    def test_subvolume_list(self):
        '''
        Test btrfs subvolume list
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={
                'recode': 0,
                'stdout': '''\
ID 257 gen 8 cgen 8 parent 5 top level 5 parent_uuid -     received_uuid - \
             uuid 777...-..05 path one
ID 258 gen 10 cgen 10 parent 5 top level 5 parent_uuid -     received_uuid - \
             uuid a90...-..01 path another one
''',
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_list('/mnt', parent_id=True,
                                        absolute=True,
                                        ogeneration=True,
                                        generation=True,
                                        subvolumes=True, uuid=True,
                                        parent_uuid=True,
                                        sent_subvolume_uuid=True,
                                        generation_cmp='-100',
                                        ogeneration_cmp='+5',
                                        sort=['-rootid', 'gen']) == [
                {
                    'id': '257',
                    'gen': '8',
                    'cgen': '8',
                    'parent': '5',
                    'top level': '5',
                    'parent_uuid': '-',
                    'received_uuid': '-',
                    'uuid': '777...-..05',
                    'path': 'one',
                },
                {
                    'id': '258',
                    'gen': '10',
                    'cgen': '10',
                    'parent': '5',
                    'top level': '5',
                    'parent_uuid': '-',
                    'received_uuid': '-',
                    'uuid': 'a90...-..01',
                    'path': 'another one',
                },
            ]
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'list', '-p', '-a', '-c', '-g',
                 '-o', '-u', '-q', '-R', '-G', '-100', '-C', '+5',
                 '--sort=-rootid,gen', '/mnt'])

    def test_subvolume_set_default(self):
        '''
        Test btrfs subvolume set-default
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={'recode': 0}),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_set_default('257', '/mnt')
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'set-default', '257', '/mnt'])

    def test_subvolume_show(self):
        '''
        Test btrfs subvolume show
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={
                'recode': 0,
                'stdout': '''@/var
        Name:                   var
        UUID:                   7a14...-...04
        Parent UUID:            -
        Received UUID:          -
        Creation time:          2018-10-01 14:33:12 +0200
        Subvolume ID:           258
        Generation:             82479
        Gen at creation:        10
        Parent ID:              256
        Top level ID:           256
        Flags:                  -
        Snapshot(s):
''',
            }),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_show('/var') == {
                '@/var': {
                    'name': 'var',
                    'uuid': '7a14...-...04',
                    'parent uuid': '-',
                    'received uuid': '-',
                    'creation time': '2018-10-01 14:33:12 +0200',
                    'subvolume id': '258',
                    'generation': '82479',
                    'gen at creation': '10',
                    'parent id': '256',
                    'top level id': '256',
                    'flags': '-',
                    'snapshot(s)': '',
                },
            }
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'show', '/var'])

    def test_subvolume_sync_fail_parameters(self):
        '''
        Test btrfs subvolume sync
        '''
        # Fails when subvolids is not a list
        with pytest.raises(CommandExecutionError):
            btrfs.subvolume_sync('/mnt', subvolids='257')

    def test_subvolume_sync(self):
        '''
        Test btrfs subvolume sync
        '''
        salt_mock = {
            'cmd.run_all': MagicMock(return_value={'recode': 0}),
        }
        with patch.dict(btrfs.__salt__, salt_mock):
            assert btrfs.subvolume_sync('/mnt', subvolids=['257'],
                                        sleep='1')
            salt_mock['cmd.run_all'].assert_called_once()
            salt_mock['cmd.run_all'].assert_called_with(
                ['btrfs', 'subvolume', 'sync', '-s', '1', '/mnt', '257'])
