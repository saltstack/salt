# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch
ensure_in_syspath('../../')

# Import Salt libs
from salt.modules import disk
import salt.utils

STUB_DISK_USAGE = {
                   '/': {'filesystem': None, '1K-blocks': 10000, 'used': 10000, 'available': 10000, 'capacity': 10000},
                   '/dev': {'filesystem': None, '1K-blocks': 10000, 'used': 10000, 'available': 10000, 'capacity': 10000},
                   '/run': {'filesystem': None, '1K-blocks': 10000, 'used': 10000, 'available': 10000, 'capacity': 10000},
                   '/run/lock': {'filesystem': None, '1K-blocks': 10000, 'used': 10000, 'available': 10000, 'capacity': 10000},
                   '/run/shm': {'filesystem': None, '1K-blocks': 10000, 'used': 10000, 'available': 10000, 'capacity': 10000},
                   '/run/user': {'filesystem': None, '1K-blocks': 10000, 'used': 10000, 'available': 10000, 'capacity': 10000},
                   '/sys/fs/cgroup': {'filesystem': None, '1K-blocks': 10000, 'used': 10000, 'available': 10000, 'capacity': 10000}
                   }


STUB_DISK_INODEUSAGE = {
                   '/': {'inodes': 10000, 'used': 10000, 'free': 10000, 'use': 10000, 'filesystem': None},
                   '/dev': {'inodes': 10000, 'used': 10000, 'free': 10000, 'use': 10000, 'filesystem': None},
                   '/run': {'inodes': 10000, 'used': 10000, 'free': 10000, 'use': 10000, 'filesystem': None},
                   '/run/lock': {'inodes': 10000, 'used': 10000, 'free': 10000, 'use': 10000, 'filesystem': None},
                   '/run/shm': {'inodes': 10000, 'used': 10000, 'free': 10000, 'use': 10000, 'filesystem': None},
                   '/run/user': {'inodes': 10000, 'used': 10000, 'free': 10000, 'use': 10000, 'filesystem': None},
                   '/sys/fs/cgroup': {'inodes': 10000, 'used': 10000, 'free': 10000, 'use': 10000, 'filesystem': None}
                   }

STUB_DISK_PERCENT = {
                   '/': 50,
                   '/dev': 10,
                   '/run': 10,
                   '/run/lock': 10,
                   '/run/shm': 10,
                   '/run/user': 10,
                   '/sys/fs/cgroup': 10
                   }

STUB_DISK_BLKID = {'/dev/sda': {'TYPE': 'ext4', 'UUID': None}}

disk.__grains__ = {}

disk.__salt__ = {}  # {'cmd.run': salt.modules.cmdmod._run_quiet}


class DiskTestCase(TestCase):
    '''
    TestCase for salt.modules.disk module
    '''

    @patch('salt.modules.disk.usage', MagicMock(return_value=STUB_DISK_USAGE))
    def test_usage_dict(self):
        with patch.dict(disk.__grains__, {'kernel': 'Linux'}):
            mock_cmd = MagicMock(return_value=1)
            with patch.dict(disk.__salt__, {'cmd.run': mock_cmd}):
                self.assertDictEqual(STUB_DISK_USAGE, disk.usage(args=None))

    @patch('salt.modules.disk.usage', MagicMock(return_value=''))
    def test_usage_none(self):
        with patch.dict(disk.__grains__, {'kernel': 'Linux'}):
            mock_cmd = MagicMock(return_value=1)
            with patch.dict(disk.__salt__, {'cmd.run': mock_cmd}):
                self.assertEqual('', disk.usage(args=None))

    @patch('salt.modules.disk.inodeusage', MagicMock(return_value=STUB_DISK_INODEUSAGE))
    def test_inodeusage(self):
        with patch.dict(disk.__grains__, {'kernel': 'OpenBSD'}):
            mock = MagicMock()
            with patch.dict(disk.__salt__, {'cmd.run': mock}):
                self.assertDictEqual(STUB_DISK_INODEUSAGE, disk.inodeusage(args=None))

    @patch('salt.modules.disk.percent', MagicMock(return_value=STUB_DISK_PERCENT))
    def test_percent(self):
        with patch.dict(disk.__grains__, {'kernel': 'Linux'}):
            mock = MagicMock()
            with patch.dict(disk.__salt__, {'cmd.run': mock}):
                self.assertDictEqual(STUB_DISK_PERCENT, disk.percent(args=None))

    @patch('salt.modules.disk.percent', MagicMock(return_value='/'))
    def test_percent_args(self):
        with patch.dict(disk.__grains__, {'kernel': 'Linux'}):
            mock = MagicMock()
            with patch.dict(disk.__salt__, {'cmd.run': mock}):
                self.assertEqual('/', disk.percent('/'))

    @patch('salt.modules.disk.blkid', MagicMock(return_value=STUB_DISK_BLKID))
    def test_blkid(self):
        with patch.dict(disk.__salt__, {'cmd.run_stdout': MagicMock(return_value=1)}):
            self.assertDictEqual(STUB_DISK_BLKID, disk.blkid())

    def test_dump(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(disk.__salt__, {'cmd.run_all': mock}):
            disk.dump('/dev/sda')
            mock.assert_called_once_with(
                'blockdev --getro --getsz --getss --getpbsz --getiomin '
                '--getioopt --getalignoff --getmaxsect --getsize '
                '--getsize64 --getra --getfra /dev/sda',
                python_shell=False
            )

    def test_wipe(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(disk.__salt__, {'cmd.run_all': mock}):
            disk.wipe('/dev/sda')
            mock.assert_called_once_with(
                'wipefs -a /dev/sda',
                python_shell=False
            )

    def test_tune(self):
        mock = MagicMock(return_value='712971264\n512\n512\n512\n0\n0\n88\n712971264\n365041287168\n512\n512')
        with patch.dict(disk.__salt__, {'cmd.run': mock}):
            mock_dump = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch('salt.modules.disk.dump', mock_dump):
                kwargs = {'read-ahead': 512, 'filesystem-read-ahead': 512}
                disk.tune('/dev/sda', **kwargs)
                mock.assert_called_once_with(
                    'blockdev --setra 512 --setfra 512 /dev/sda',
                    python_shell=False
                )

    @skipIf(not salt.utils.which('sync'), 'sync not found')
    @skipIf(not salt.utils.which('mkfs'), 'mkfs not found')
    def test_format(self):
        '''
        unit tests for disk.format
        '''
        device = '/dev/sdX1'
        mock = MagicMock(return_value=0)
        with patch.dict(disk.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(disk.format_(device), True)

    def test_fstype(self):
        '''
        unit tests for disk.fstype
        '''
        device = '/dev/sdX1'
        fs_type = 'ext4'
        mock = MagicMock(return_value='FSTYPE\n{0}'.format(fs_type))
        with patch.dict(disk.__grains__, {'kernel': 'Linux'}):
            with patch.dict(disk.__salt__, {'cmd.run': mock}):
                self.assertEqual(disk.fstype(device), fs_type)

    @skipIf(not salt.utils.which('resize2fs'), 'resize2fs not found')
    def test_resize2fs(self):
        '''
        unit tests for disk.resize2fs
        '''
        device = '/dev/sdX1'
        mock = MagicMock()
        with patch.dict(disk.__salt__, {'cmd.run_all': mock}):
            disk.resize2fs(device)
            mock.assert_called_once_with('resize2fs {0}'.format(device), python_shell=False)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DiskTestCase, needs_daemon=False)
