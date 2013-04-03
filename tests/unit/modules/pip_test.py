try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False

from saltunittest import TestCase, skipIf
from salt.modules import pip

pip.__salt__ = {"cmd.which_bin":lambda _:"pip"}

@skipIf(has_mock is False, "mock python module is unavailable")
class PipTestCase(TestCase):
    def test_fix4361(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all':mock}):
            pip.install(requirements="requirements.txt")
            expected_cmd = 'pip install --requirement "requirements.txt" '
            mock.assert_called_once_with(expected_cmd, runas=None, cwd=None)
