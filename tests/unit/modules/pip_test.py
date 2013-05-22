try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False
    patch = lambda x: lambda y: None

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

    @patch('salt.modules.pip._get_cached_requirements')
    def test_failed_cached_requirements(self, get_cached_requirements):
        get_cached_requirements.return_value = False
        ret = pip.install(requirements='salt://my_test_reqs')
        self.assertEqual(False, ret['result'])
        self.assertIn('my_test_reqs', ret['comment'])

    @patch('salt.modules.pip._get_cached_requirements')
    def test_cached_requirements_used(self, get_cached_requirements):
        get_cached_requirements.return_value = 'my_cached_reqs'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements="salt://requirements.txt")
            expected_cmd = 'pip install --requirement "my_cached_reqs" '
            mock.assert_called_once_with(expected_cmd, runas=None, cwd=None)
    @patch('os.path')
    def test_fix_activate_env(self, mock_path):
        mock_path.is_file.return_value = True
        mock_path.isdir.return_value = True
        def join(*args):
            return '/'.join(args)
        mock_path.join = join
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('mock', bin_env='/test_env', activate=True)
            expected_cmd = '. /test_env/bin/activate && /test_env/bin/pip install mock '
            mock.assert_called_once_with(expected_cmd, runas=None, cwd=None)
