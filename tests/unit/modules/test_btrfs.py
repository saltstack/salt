# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt
import salt.utils.fsutils
import salt.modules.btrfs as btrfs
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BtrfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.btrfs
    '''
    loader_module = btrfs
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

    @patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True))
    def test_info(self):
        '''
        Test if it get BTRFS filesystem information.
        '''
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
            mock = MagicMock(return_value={'Salt': 'salt'})
            with patch.object(btrfs, '_parse_btrfs_info', mock):
                self.assertDictEqual(btrfs.info('/dev/sda1'),
                                     {'Salt': 'salt'})

    # 'devices' function tests: 1

    @patch('salt.utils.fsutils._blkid_output',
           MagicMock(return_value='Salt'))
    def test_devices(self):
        '''
        Test if it get known BTRFS formatted devices on the system.
        '''
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(btrfs.devices(), 'Salt')

    # 'defragment' function tests: 2

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    def test_defragment(self):
        '''
        Test if it defragment mounted BTRFS filesystem.
        '''
        ret = [{'range': '/dev/sda1',
                'mount_point': False,
                'log': False, 'passed': True}]
        mock_run = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock_run}):
            mock_file = mock_open(read_data='/dev/sda1 / ext4 rw,data=ordered 0 0')
            with patch.object(salt.utils, 'fopen', mock_file):
                self.assertListEqual(btrfs.defragment('/dev/sda1'), ret)

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=True))
    def test_defragment_error(self):
        '''
        Test if it gives device not mount error
        '''
        mock_run = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock_run}):
            mock_file = mock_open(read_data='/dev/sda1 / ext4 rw,data=ordered 0 0')
            with patch.object(salt.utils, 'fopen', mock_file):
                self.assertRaises(CommandExecutionError, btrfs.defragment,
                                  '/dev/sda1')

    # 'features' function tests: 1

    @patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True))
    def test_features(self):
        '''
        Test if it list currently available BTRFS features.
        '''
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(btrfs.features(), {})

    # 'usage' function tests: 1

    @patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True))
    def test_usage(self):
        '''
        Test if it shows in which disk the chunks are allocated.
        '''
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
            with patch.object(salt.utils, 'fopen', mock_file):
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

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=True))
    def test_resize(self):
        '''
        Test if it resize filesystem.
        '''
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

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=False))
    def test_resize_valid_error(self):
        '''
        Test if it gives device should be mounted error
        '''
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, btrfs.resize,
                              '/dev/sda1', 'max')

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=True))
    def test_resize_mount_error(self):
        '''
        Test if it gives mount point error
        '''
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

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_convert(self):
        '''
        Test if it convert ext2/3/4 to BTRFS
        '''
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

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=True))
    def test_convert_filesystem_error(self):
        '''
        Test if it gives file system error
        '''
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock}):
            mock = MagicMock(return_value={'/dev/sda1': {'type': 'ext'}})
            with patch.object(salt.utils.fsutils, '_blkid_output', mock):
                self.assertRaises(CommandExecutionError, btrfs.convert,
                                  '/dev/sda1')

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=True))
    def test_convert_error(self):
        '''
        Test if it gives error cannot convert root
        '''
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

    @patch('salt.utils.fsutils._is_device', MagicMock(return_value=True))
    def test_convert_migration_error(self):
        '''
        Test if it gives migration error
        '''
        mock_run = MagicMock(return_value={'retcode': 1,
                                           'stderr': '',
                                           'stdout': 'Salt'})
        with patch.dict(btrfs.__salt__, {'cmd.run_all': mock_run}):
            mock_blk = MagicMock(return_value={'/dev/sda1': {'type': 'ext4'}})
            with patch.object(salt.utils.fsutils, '_blkid_output', mock_blk):
                mock_file = mock_open(read_data='/dev/sda1 / ext4 rw,data=ordered 0 0')
                with patch.object(salt.utils, 'fopen', mock_file):
                    self.assertRaises(CommandExecutionError, btrfs.convert,
                                      '/dev/sda1')

    # 'add' function tests: 1

    @patch('salt.modules.btrfs._restripe', MagicMock(return_value={}))
    def test_add(self):
        '''
        Test if it add a devices to a BTRFS filesystem.
        '''
        self.assertDictEqual(btrfs.add('/mountpoint', '/dev/sda1', '/dev/sda2'),
                             {})

    # 'delete' function tests: 1

    @patch('salt.modules.btrfs._restripe', MagicMock(return_value={}))
    def test_delete(self):
        '''
        Test if it delete a devices to a BTRFS filesystem.
        '''
        self.assertDictEqual(btrfs.delete('/mountpoint', '/dev/sda1',
                                          '/dev/sda2'), {})

    # 'properties' function tests: 1

    @patch('salt.utils.fsutils._verify_run', MagicMock(return_value=True))
    def test_properties(self):
        '''
        Test if list properties for given btrfs object
        '''
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
