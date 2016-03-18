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
        with patch.dict(blockdev.__salt__, {'disk.dump': MagicMock(return_value=True)}):
            self.assertTrue(blockdev.dump('/dev/sda'))

    @skipIf(not salt.utils.which('wipefs'), 'Wipefs not found')
    def test_wipe(self):
        with patch.dict(blockdev.__salt__, {'disk.wipe': MagicMock(return_value=True)}):
            self.assertTrue(blockdev.wipe('/dev/sda'))

    def test_tune(self):
        mock_run = MagicMock(return_value='712971264\n512\n512\n512\n0\n0\n88\n712971264\n365041287168\n512\n512')
        with patch.dict(blockdev.__salt__, {'disk.tune': MagicMock(return_value=True)}):
            kwargs = {'read-ahead': 512, 'filesystem-read-ahead': 512}
            ret = blockdev.tune('/dev/sda', **kwargs)
            self.assertTrue(ret)

    @skipIf(not salt.utils.which('sync'), 'sync not found')
    @skipIf(not salt.utils.which('mkfs'), 'mkfs not found')
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestBlockdevModule, needs_daemon=False)
