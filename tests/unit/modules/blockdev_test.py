# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting.unit import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import Salt Libs
import salt.modules.blockdev as blockdev
import salt.utils

blockdev.__salt__ = {
    'cmd.has_exec': MagicMock(return_value=True),
    'config.option': MagicMock(return_value=None)
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestBlockdevModule(TestCase):
    def test_dump(self):
        device = '/dev/sdX'
        cmd = ['blockdev',
               '--getro',
               '--getsz',
               '--getss',
               '--getpbsz',
               '--getiomin',
               '--getioopt',
               '--getalignoff',
               '--getmaxsect',
               '--getsize',
               '--getsize64',
               '--getra',
               '--getfra',
               device]
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(blockdev.__salt__, {'cmd.run_all': mock}):
            blockdev.dump(device)
            mock.assert_called_once_with(cmd, python_shell=False)

    @skipIf(not salt.utils.which('wipefs'), 'Wipefs not found')
    def test_wipe(self):
        device = '/dev/sdX'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(blockdev.__salt__, {'cmd.run_all': mock}):
            blockdev.wipe(device)
            mock.assert_called_once_with(
                'wipefs {0}'.format(device),
                python_shell=False
            )

    def test_tune(self):
        device = '/dev/sdX'
        mock = MagicMock(return_value='712971264\n512\n512\n512\n0\n0\n88\n712971264\n365041287168\n512\n512')
        with patch.dict(blockdev.__salt__, {'cmd.run': mock}):
            mock_dump = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch('salt.modules.blockdev.dump', mock_dump):
                kwargs = {'read-ahead': 512, 'filesystem-read-ahead': 512}
                blockdev.tune(device, **kwargs)
                mock.assert_called_once_with(
                    'blockdev --setra 512 --setfra 512 {0}'.format(device),
                    python_shell=False
                )

    def test_format(self):
        '''
        unit tests for blockdev.format
        '''
        device = '/dev/sdX1'
        fs_type = 'ext4'
        mock = MagicMock(return_value=0)
        with patch.dict(blockdev.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(blockdev.format_(device), True)

    def test_fstype(self):
        '''
        unit tests for blockdev.fstype
        '''
        device = '/dev/sdX1'
        fs_type = 'ext4'
        mock = MagicMock(return_value='FSTYPE\n{0}'.format(fs_type))
        with patch.dict(blockdev.__salt__, {'cmd.run': mock}):
            self.assertEqual(blockdev.fstype(device), fs_type)

    def test_resize2fs(self):
        '''
        unit tests for blockdev.resize2fs
        '''
        device = '/dev/sdX1'
        mock = MagicMock()
        with patch.dict(blockdev.__salt__, {'cmd.run_all': mock}):
            blockdev.resize2fs(device)
            mock.assert_called_once_with('resize2fs {0}'.format(device), python_shell=False)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestBlockdevModule, needs_daemon=False)
