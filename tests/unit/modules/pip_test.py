# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import pip
from salt.exceptions import CommandExecutionError

try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False
    patch = lambda x: lambda y: None


pip.__salt__ = {'cmd.which_bin': lambda _: 'pip'}


@skipIf(has_mock is False, 'mock python module is unavailable')
class PipTestCase(TestCase):

    def test_fix4361(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements='requirements.txt')
            expected_cmd = 'pip install --requirement=\'requirements.txt\''
            mock.assert_called_once_with(expected_cmd, runas=None, cwd=None)

    def test_install_editable_withough_egg_fails(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install,
                editable='git+https://github.com/saltstack/salt-testing.git'
            )
            #mock.assert_called_once_with('', runas=None, cwd=None)

    def test_install_multiple_editable(self):
        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        # Passing editables as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(editable=editables)
            mock.assert_called_once_with(
                'pip install '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker '
                '--editable=git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting',
                runas=None,
                cwd=None
            )

        # Passing editables as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(editable=','.join(editables))
            mock.assert_called_once_with(
                'pip install '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker '
                '--editable=git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting',
                runas=None,
                cwd=None
            )

    def test_install_multiple_pkgs_and_editables(self):
        pkgs = [
            'pep8',
            'salt'
        ]

        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        # Passing editables as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkgs=pkgs, editable=editables)
            mock.assert_called_once_with(
                'pip install pep8 salt '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker '
                '--editable=git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting',
                runas=None,
                cwd=None
            )

        # Passing editables as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkgs=','.join(pkgs), editable=','.join(editables))
            mock.assert_called_once_with(
                'pip install pep8 salt '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker '
                '--editable=git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting',
                runas=None,
                cwd=None
            )

    def test_issue5940_multiple_pip_mirrors(self):
        mirrors = [
            'http://g.pypi.python.org',
            'http://c.pypi.python.org',
            'http://pypi.crate.io'
        ]

        # Passing mirrors as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(mirrors=mirrors)
            mock.assert_called_once_with(
                'pip install --use-mirrors '
                '--mirrors=http://g.pypi.python.org '
                '--mirrors=http://c.pypi.python.org '
                '--mirrors=http://pypi.crate.io',
                runas=None,
                cwd=None
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(mirrors=','.join(mirrors))
            mock.assert_called_once_with(
                'pip install --use-mirrors '
                '--mirrors=http://g.pypi.python.org '
                '--mirrors=http://c.pypi.python.org '
                '--mirrors=http://pypi.crate.io',
                runas=None,
                cwd=None
            )

    def test_install_with_multiple_find_links(self):
        find_links = [
            'http://g.pypi.python.org',
            'http://c.pypi.python.org',
            'http://pypi.crate.io'
        ]

        # Passing mirrors as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', find_links=find_links)
            mock.assert_called_once_with(
                'pip install pep8 '
                '--find-links=http://g.pypi.python.org '
                '--find-links=http://c.pypi.python.org '
                '--find-links=http://pypi.crate.io',
                runas=None,
                cwd=None
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', find_links=','.join(find_links))
            mock.assert_called_once_with(
                'pip install pep8 '
                '--find-links=http://g.pypi.python.org '
                '--find-links=http://c.pypi.python.org '
                '--find-links=http://pypi.crate.io',
                runas=None,
                cwd=None
            )

    def test_install_no_index_with_index_url_or_extra_index_url_raises(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install, no_index=True, index_url='http://foo.tld'
            )
            #mock.assert_called_once_with('', runas=None, cwd=None)

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install, no_index=True, extra_index_url='http://foo.tld'
            )
            #mock.assert_called_once_with('', runas=None, cwd=None)

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
            pip.install(requirements='salt://requirements.txt')
            expected_cmd = 'pip install --requirement=\'my_cached_reqs\''
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
            mock.assert_called_once_with(
                '. /test_env/bin/activate && /test_env/bin/pip install mock',
                env={'VIRTUAL_ENV': '/test_env'},
                runas=None,
                cwd=None)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PipTestCase, needs_daemon=False)
