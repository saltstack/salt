# -*- coding: utf-8 -*-

# Import python libs

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import pip
from salt.exceptions import CommandExecutionError

pip.__salt__ = {'cmd.which_bin': lambda _: 'pip'}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PipTestCase(TestCase):

    def test_fix4361(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements='requirements.txt')
            expected_cmd = 'pip install --requirement=\'requirements.txt\''
            mock.assert_called_once_with(
                expected_cmd,
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_editable_withough_egg_fails(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install,
                editable='git+https://github.com/saltstack/salt-testing.git'
            )
            #mock.assert_called_once_with('', cwd=None, use_vt=False)

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
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing editables as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(editable=','.join(editables))
            mock.assert_called_once_with(
                'pip install '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker '
                '--editable=git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
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
                'pip install \'pep8\' \'salt\' '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker '
                '--editable=git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing editables as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkgs=','.join(pkgs), editable=','.join(editables))
            mock.assert_called_once_with(
                'pip install \'pep8\' \'salt\' '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker '
                '--editable=git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # As a single string
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkgs=pkgs[0], editable=editables[0])
            mock.assert_called_once_with(
                'pip install \'pep8\' '
                '--editable=git+https://github.com/jek/blinker.git#egg=Blinker',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_issue5940_install_multiple_pip_mirrors(self):
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
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
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
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # As a single string
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(mirrors=mirrors[0])
            mock.assert_called_once_with(
                'pip install --use-mirrors '
                '--mirrors=http://g.pypi.python.org',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
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
                'pip install '
                '--find-links=http://g.pypi.python.org '
                '--find-links=http://c.pypi.python.org '
                '--find-links=http://pypi.crate.io \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', find_links=','.join(find_links))
            mock.assert_called_once_with(
                'pip install '
                '--find-links=http://g.pypi.python.org '
                '--find-links=http://c.pypi.python.org '
                '--find-links=http://pypi.crate.io \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a single string entry
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', find_links=find_links[0])
            mock.assert_called_once_with(
                'pip install --find-links=http://g.pypi.python.org \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Invalid proto raises exception
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install,
                '\'pep8\'',
                find_links='sftp://pypi.crate.io'
            )

        # Valid protos work?
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(
                'pep8', find_links=[
                    'ftp://g.pypi.python.org',
                    'http://c.pypi.python.org',
                    'https://pypi.crate.io'
                ]
            )
            mock.assert_called_once_with(
                'pip install '
                '--find-links=ftp://g.pypi.python.org '
                '--find-links=http://c.pypi.python.org '
                '--find-links=https://pypi.crate.io \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_index_with_index_url_or_extra_index_url_raises(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install, no_index=True, index_url='http://foo.tld'
            )
            #mock.assert_called_once_with('', cwd=None)

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install, no_index=True, extra_index_url='http://foo.tld'
            )
            #mock.assert_called_once_with('', cwd=None)

    @patch('salt.modules.pip._get_cached_requirements')
    def test_install_failed_cached_requirements(self, get_cached_requirements):
        get_cached_requirements.return_value = False
        ret = pip.install(requirements='salt://my_test_reqs')
        self.assertEqual(False, ret['result'])
        self.assertIn('my_test_reqs', ret['comment'])

    @patch('salt.modules.pip._get_cached_requirements')
    def test_install_cached_requirements_used(self, get_cached_requirements):
        get_cached_requirements.return_value = 'my_cached_reqs'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements='salt://requirements.txt')
            expected_cmd = 'pip install --requirement=\'my_cached_reqs\''
            mock.assert_called_once_with(
                expected_cmd,
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    @patch('os.path')
    def test_install_venv(self, mock_path):
        mock_path.is_file.return_value = True
        mock_path.isdir.return_value = True

        def join(*args):
            return '/'.join(args)
        mock_path.join = join
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('mock', bin_env='/test_env')
            mock.assert_called_once_with(
                '/test_env/bin/pip install '
                '\'mock\'',
                env={'VIRTUAL_ENV': '/test_env'},
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    @patch('os.path')
    def test_install_log_argument_in_resulting_command(self, mock_path):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', log='/tmp/pip-install.log')
            mock.assert_called_once_with(
                'pip install --log=/tmp/pip-install.log \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Let's fake a non-writable log file
        mock_path.exists.side_effect = IOError('Fooo!')
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                IOError,
                pip.install,
                'pep8',
                log='/tmp/pip-install.log'
            )

    def test_install_timeout_argument_in_resulting_command(self):
        # Passing an int
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', timeout=10)
            mock.assert_called_once_with(
                'pip install --timeout=10 \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing an int as a string
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', timeout='10')
            mock.assert_called_once_with(
                'pip install --timeout=10 \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing a non-int to timeout
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                ValueError,
                pip.install,
                'pep8',
                timeout='a'
            )

    def test_install_index_url_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', index_url='http://foo.tld')
            mock.assert_called_once_with(
                'pip install --index-url=\'http://foo.tld\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_extra_index_url_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', extra_index_url='http://foo.tld')
            mock.assert_called_once_with(
                'pip install --extra-index-url=\'http://foo.tld\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_index_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', no_index=True)
            mock.assert_called_once_with(
                'pip install --no-index \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_build_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', build='/tmp/foo')
            mock.assert_called_once_with(
                'pip install --build=/tmp/foo \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_target_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', target='/tmp/foo')
            mock.assert_called_once_with(
                'pip install --target=/tmp/foo \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_download_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', download='/tmp/foo')
            mock.assert_called_once_with(
                'pip install --download=/tmp/foo \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_download_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', no_download=True)
            mock.assert_called_once_with(
                'pip install --no-download \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_download_cache_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', download_cache='/tmp/foo')
            mock.assert_called_once_with(
                'pip install --download-cache=/tmp/foo \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_source_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', source='/tmp/foo')
            mock.assert_called_once_with(
                'pip install --source=/tmp/foo \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_exists_action_argument_in_resulting_command(self):
        for action in ('s', 'i', 'w', 'b'):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install('pep8', exists_action=action)
                mock.assert_called_once_with(
                    'pip install --exists-action={0} \'pep8\''.format(action),
                    saltenv='base',
                    runas=None,
                    cwd=None,
                    use_vt=False,
                    python_shell=False,
                )

        # Test for invalid action
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install,
                'pep8',
                exists_action='d'
            )

    def test_install_install_options_argument_in_resulting_command(self):
        install_options = [
            '--exec-prefix=/foo/bar',
            '--install-scripts=/foo/bar/bin'
        ]

        # Passing options as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', install_options=install_options)
            mock.assert_called_once_with(
                'pip install '
                '--install-option=\'--exec-prefix=/foo/bar\' '
                '--install-option=\'--install-scripts=/foo/bar/bin\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', install_options=','.join(install_options))
            mock.assert_called_once_with(
                'pip install '
                '--install-option=\'--exec-prefix=/foo/bar\' '
                '--install-option=\'--install-scripts=/foo/bar/bin\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a single string entry
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', install_options=install_options[0])
            mock.assert_called_once_with(
                'pip install --install-option=\'--exec-prefix=/foo/bar\' '
                '\'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_global_options_argument_in_resulting_command(self):
        global_options = [
            '--quiet',
            '--no-user-cfg'
        ]

        # Passing options as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', global_options=global_options)
            mock.assert_called_once_with(
                'pip install '
                '--global-option=\'--quiet\' '
                '--global-option=\'--no-user-cfg\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', global_options=','.join(global_options))
            mock.assert_called_once_with(
                'pip install '
                '--global-option=\'--quiet\' '
                '--global-option=\'--no-user-cfg\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a single string entry
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', global_options=global_options[0])
            mock.assert_called_once_with(
                'pip install --global-option=\'--quiet\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_upgrade_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', upgrade=True)
            mock.assert_called_once_with(
                'pip install --upgrade \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_force_reinstall_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', force_reinstall=True)
            mock.assert_called_once_with(
                'pip install --force-reinstall \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_ignore_installed_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', ignore_installed=True)
            mock.assert_called_once_with(
                'pip install --ignore-installed \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_deps_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', no_deps=True)
            mock.assert_called_once_with(
                'pip install --no-deps \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_install_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', no_install=True)
            mock.assert_called_once_with(
                'pip install --no-install \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_proxy_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install('pep8', proxy='salt-user:salt-passwd@salt-proxy:3128')
            mock.assert_called_once_with(
                'pip install '
                '--proxy=\'salt-user:salt-passwd@salt-proxy:3128\' \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    @patch('salt.modules.pip._get_cached_requirements')
    def test_install_multiple_requirements_arguments_in_resulting_command(self, get_cached_requirements):
        get_cached_requirements.side_effect = [
            'my_cached_reqs-1', 'my_cached_reqs-2'
        ]
        requirements = [
            'salt://requirements-1.txt', 'salt://requirements-2.txt'
        ]

        # Passing option as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements=requirements)
            mock.assert_called_once_with(
                'pip install '
                '--requirement=\'my_cached_reqs-1\' '
                '--requirement=\'my_cached_reqs-2\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a comma separated list
        get_cached_requirements.side_effect = [
            'my_cached_reqs-1', 'my_cached_reqs-2'
        ]
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements=','.join(requirements))
            mock.assert_called_once_with(
                'pip install '
                '--requirement=\'my_cached_reqs-1\' '
                '--requirement=\'my_cached_reqs-2\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a single string entry
        get_cached_requirements.side_effect = ['my_cached_reqs-1']
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements=requirements[0])
            mock.assert_called_once_with(
                'pip install --requirement=\'my_cached_reqs-1\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    @patch('salt.modules.pip._get_cached_requirements')
    def test_uninstall_multiple_requirements_arguments_in_resulting_command(self, get_cached_requirements):
        get_cached_requirements.side_effect = [
            'my_cached_reqs-1', 'my_cached_reqs-2'
        ]
        requirements = [
            'salt://requirements-1.txt', 'salt://requirements-2.txt'
        ]

        # Passing option as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall(requirements=requirements)
            mock.assert_called_once_with(
                'pip uninstall -y '
                '--requirement=\'my_cached_reqs-1\' '
                '--requirement=\'my_cached_reqs-2\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a comma separated list
        get_cached_requirements.side_effect = [
            'my_cached_reqs-1', 'my_cached_reqs-2'
        ]
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall(requirements=','.join(requirements))
            mock.assert_called_once_with(
                'pip uninstall -y '
                '--requirement=\'my_cached_reqs-1\' '
                '--requirement=\'my_cached_reqs-2\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a single string entry
        get_cached_requirements.side_effect = ['my_cached_reqs-1']
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall(requirements=requirements[0])
            mock.assert_called_once_with(
                'pip uninstall -y --requirement=\'my_cached_reqs-1\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    def test_uninstall_proxy_argument_in_resulting_command(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall(
                'pep8', proxy='salt-user:salt-passwd@salt-proxy:3128'
            )
            mock.assert_called_once_with(
                'pip uninstall -y '
                '--proxy=\'salt-user:salt-passwd@salt-proxy:3128\' pep8',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

    @patch('os.path')
    def test_uninstall_log_argument_in_resulting_command(self, mock_path):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall('pep8', log='/tmp/pip-install.log')
            mock.assert_called_once_with(
                'pip uninstall -y --log=/tmp/pip-install.log pep8',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Let's fake a non-writable log file
        mock_path.exists.side_effect = IOError('Fooo!')
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                IOError,
                pip.uninstall,
                'pep8',
                log='/tmp/pip-install.log'
            )

    def test_uninstall_timeout_argument_in_resulting_command(self):
        # Passing an int
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall('pep8', timeout=10)
            mock.assert_called_once_with(
                'pip uninstall -y --timeout=10 pep8',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing an int as a string
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall('pep8', timeout='10')
            mock.assert_called_once_with(
                'pip uninstall -y --timeout=10 pep8',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing a non-int to timeout
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                ValueError,
                pip.uninstall,
                'pep8',
                timeout='a'
            )

    def test_freeze_command(self):
        eggs = [
            'M2Crypto==0.21.1',
            '-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev',
            'bbfreeze==1.1.0',
            'bbfreeze-loader==1.1.0',
            'pycrypto==2.6'
        ]
        mock = MagicMock(
            return_value={
                'retcode': 0,
                'stdout': '\n'.join(eggs)
            }
        )
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            ret = pip.freeze()
            mock.assert_called_once_with(
                'pip freeze',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )
            self.assertEqual(ret, eggs)

        # Non zero returncode raises exception?
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'CABOOOOMMM!'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.freeze,
            )

    def test_list_command(self):
        eggs = [
            'M2Crypto==0.21.1',
            '-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev',
            'bbfreeze==1.1.0',
            'bbfreeze-loader==1.1.0',
            'pycrypto==2.6'
        ]
        mock = MagicMock(
            side_effect=[
                {'retcode': 0, 'stdout': 'pip MOCKED_VERSION'},
                {'retcode': 0, 'stdout': '\n'.join(eggs)}
            ]
        )
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            ret = pip.list_()
            mock.assert_called_with(
                'pip freeze',
                runas=None,
                cwd=None,
                python_shell=False,
            )
            self.assertEqual(
                ret, {
                    'SaltTesting-dev': 'git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8',
                    'M2Crypto': '0.21.1',
                    'bbfreeze-loader': '1.1.0',
                    'bbfreeze': '1.1.0',
                    'pip': 'MOCKED_VERSION',
                    'pycrypto': '2.6'
                }
            )

        # Non zero returncode raises exception?
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'CABOOOOMMM!'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.list_,
            )

    def test_list_command_with_prefix(self):
        eggs = [
            'M2Crypto==0.21.1',
            '-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev',
            'bbfreeze==1.1.0',
            'bbfreeze-loader==1.1.0',
            'pycrypto==2.6'
        ]
        mock = MagicMock(
            return_value={
                'retcode': 0,
                'stdout': '\n'.join(eggs)
            }
        )
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            ret = pip.list_(prefix='bb')
            mock.assert_called_with(
                'pip freeze',
                runas=None,
                cwd=None,
                python_shell=False,
            )
            self.assertEqual(
                ret, {
                    'bbfreeze-loader': '1.1.0',
                    'bbfreeze': '1.1.0',
                }
            )

    def test_install_pre_argument_in_resulting_command(self):
        # Lower than 1.4 versions don't end-up with `--pre` in the resulting
        # output
        mock = MagicMock(side_effect=[
            {'retcode': 0, 'stdout': 'pip 1.2.0 /path/to/site-packages/pip'},
            {'retcode': 0, 'stdout': ''}
        ])
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(
                'pep8', pre_releases=True
            )
            mock.assert_called_with(
                'pip install \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )

        mock = MagicMock(side_effect=[
            {'retcode': 0, 'stdout': 'pip 1.4.0 /path/to/site-packages/pip'},
            {'retcode': 0, 'stdout': ''}
        ])
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(
                'pep8', pre_releases=True
            )
            mock.assert_called_with(
                'pip install --pre \'pep8\'',
                saltenv='base',
                runas=None,
                cwd=None,
                use_vt=False,
                python_shell=False,
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PipTestCase, needs_daemon=False)
