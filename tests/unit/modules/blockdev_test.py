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

blockdev.__salt__ = {
    'cmd.has_exec': MagicMock(return_value=True),
    'config.option': MagicMock(return_value=None)
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestBlockdevModule(TestCase):
    def test_dump(self):
        with patch.dict(blockdev.__salt__, {'disk.dump': MagicMock(return_value=True)}):
            self.assertTrue(blockdev.dump('/dev/sda'))

    def test_wipe(self):
        with patch.dict(blockdev.__salt__, {'disk.wipe': MagicMock(return_value=True)}):
            self.assertTrue(blockdev.wipe('/dev/sda'))

    def test_tune(self):
        mock_run = MagicMock(return_value='712971264\n512\n512\n512\n0\n0\n88\n712971264\n365041287168\n512\n512')
        with patch.dict(blockdev.__salt__, {'disk.tune': MagicMock(return_value=True)}):
            kwargs = {'read-ahead': 512, 'filesystem-read-ahead': 512}
            ret = blockdev.tune('/dev/sda', **kwargs)
            self.assertTrue(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestBlockdevModule, needs_daemon=False)
