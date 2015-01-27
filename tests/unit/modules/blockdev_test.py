# -*- coding: utf-8 -*-

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
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(blockdev.__salt__, {'cmd.run_all': mock}):
            blockdev.dump('/dev/sda')
            mock.assert_called_once_with(
                'blockdev --getro --getsz --getss --getpbsz --getiomin '
                '--getioopt --getalignoff  --getmaxsect --getsize '
                '--getsize64 --getra --getfra /dev/sda',
                python_shell=False
            )

    def test_wipe(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(blockdev.__salt__, {'cmd.run_all': mock}):
            blockdev.wipe('/dev/sda')
            mock.assert_called_once_with(
                'wipefs /dev/sda',
                python_shell=False
            )

    def test_tune(self):
        mock = MagicMock(return_value='712971264\n512\n512\n512\n0\n0\n88\n712971264\n365041287168\n512\n512')
        with patch.dict(blockdev.__salt__, {'cmd.run': mock}):
            mock_dump = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch('salt.modules.blockdev.dump', mock_dump):
                kwargs = {'read-ahead': 512, 'filesystem-read-ahead': 512}
                blockdev.tune('/dev/sda', **kwargs)
                mock.assert_called_once_with(
                    'blockdev --setra 512 --setfra 512 /dev/sda',
                    python_shell=False
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestBlockdevModule, needs_daemon=False)
