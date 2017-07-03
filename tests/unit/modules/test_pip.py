# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.pip as pip
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PipTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {pip: {'__salt__': {'cmd.which_bin': lambda _: 'pip'}}}

    def test_fix4361(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(requirements='requirements.txt')
            expected_cmd = ['pip', 'install', '--requirement',
                            'requirements.txt']
            mock.assert_called_once_with(
                expected_cmd,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_editable_without_egg_fails(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install,
                editable='git+https://github.com/saltstack/salt-testing.git'
            )

    def test_install_multiple_editable(self):
        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        expected = ['pip', 'install']
        for item in editables:
            expected.extend(['--editable', item])

        # Passing editables as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(editable=editables)
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing editables as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(editable=','.join(editables))
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_multiple_pkgs_and_editables(self):
        pkgs = ['pep8', 'salt']
        editables = [
            'git+https://github.com/jek/blinker.git#egg=Blinker',
            'git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting'
        ]

        expected = ['pip', 'install'] + pkgs
        for item in editables:
            expected.extend(['--editable', item])

        # Passing editables as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkgs=pkgs, editable=editables)
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing editables as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkgs=','.join(pkgs), editable=','.join(editables))
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # As single string (just use the first element from pkgs and editables)
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkgs=pkgs[0], editable=editables[0])
            mock.assert_called_once_with(
                ['pip', 'install', pkgs[0], '--editable', editables[0]],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_issue5940_install_multiple_pip_mirrors(self):
        '''
        test multiple pip mirrors.  This test only works with pip < 7.0.0
        '''
        with patch.object(pip, 'version', MagicMock(return_value='1.4')):
            mirrors = [
                'http://g.pypi.python.org',
                'http://c.pypi.python.org',
                'http://pypi.crate.io'
            ]

            expected = ['pip', 'install', '--use-mirrors']
            for item in mirrors:
                expected.extend(['--mirrors', item])

            # Passing mirrors as a list
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(mirrors=mirrors)
                mock.assert_called_once_with(
                    expected,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

            # Passing mirrors as a comma separated list
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(mirrors=','.join(mirrors))
                mock.assert_called_once_with(
                    expected,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

            # As single string (just use the first element from mirrors)
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(mirrors=mirrors[0])
                mock.assert_called_once_with(
                    ['pip', 'install', '--use-mirrors', '--mirrors', mirrors[0]],
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

    def test_install_with_multiple_find_links(self):
        find_links = [
            'http://g.pypi.python.org',
            'http://c.pypi.python.org',
            'http://pypi.crate.io'
        ]
        pkg = 'pep8'

        expected = ['pip', 'install']
        for item in find_links:
            expected.extend(['--find-links', item])
        expected.append(pkg)

        # Passing mirrors as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, find_links=find_links)
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, find_links=','.join(find_links))
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # As single string (just use the first element from find_links)
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, find_links=find_links[0])
            mock.assert_called_once_with(
                ['pip', 'install', '--find-links', find_links[0], pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Invalid proto raises exception
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install,
                '\'' + pkg + '\'',
                find_links='sftp://pypi.crate.io'
            )

        # Valid protos work?
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, find_links=find_links)
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
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

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install, no_index=True, extra_index_url='http://foo.tld'
            )

    def test_install_failed_cached_requirements(self):
        with patch('salt.modules.pip._get_cached_requirements') as get_cached_requirements:
            get_cached_requirements.return_value = False
            ret = pip.install(requirements='salt://my_test_reqs')
            self.assertEqual(False, ret['result'])
            self.assertIn('my_test_reqs', ret['comment'])

    def test_install_cached_requirements_used(self):
        with patch('salt.modules.pip._get_cached_requirements') as get_cached_requirements:
            get_cached_requirements.return_value = 'my_cached_reqs'
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(requirements='salt://requirements.txt')
                expected = ['pip', 'install', '--requirement', 'my_cached_reqs']
                mock.assert_called_once_with(
                    expected,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

    def test_install_venv(self):
        with patch('os.path') as mock_path:
            mock_path.is_file.return_value = True
            mock_path.isdir.return_value = True

            pkg = 'mock'
            venv_path = '/test_env'

            def join(*args):
                return '/'.join(args)
            mock_path.join = join
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(pkg, bin_env=venv_path)
                mock.assert_called_once_with(
                    [os.path.join(venv_path, 'bin', 'pip'), 'install', pkg],
                    env={'VIRTUAL_ENV': '/test_env'},
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

    def test_install_log_argument_in_resulting_command(self):
        with patch('os.access') as mock_path:
            pkg = 'pep8'
            log_path = '/tmp/pip-install.log'
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(pkg, log=log_path)
                mock.assert_called_once_with(
                    ['pip', 'install', '--log', log_path, pkg],
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

    def test_non_writeable_log(self):
        with patch('os.path') as mock_path:
            # Let's fake a non-writable log file
            pkg = 'pep8'
            log_path = '/tmp/pip-install.log'
            mock_path.exists.side_effect = IOError('Fooo!')
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(
                    IOError,
                    pip.install,
                    pkg,
                    log=log_path
                )

    def test_install_timeout_argument_in_resulting_command(self):
        # Passing an int
        pkg = 'pep8'
        expected_prefix = ['pip', 'install', '--timeout']
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, timeout=10)
            mock.assert_called_once_with(
                expected_prefix + [10, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing an int as a string
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, timeout='10')
            mock.assert_called_once_with(
                expected_prefix + ['10', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing a non-int to timeout
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                ValueError,
                pip.install,
                pkg,
                timeout='a'
            )

    def test_install_index_url_argument_in_resulting_command(self):
        pkg = 'pep8'
        index_url = 'http://foo.tld'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, index_url=index_url)
            mock.assert_called_once_with(
                ['pip', 'install', '--index-url', index_url, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_extra_index_url_argument_in_resulting_command(self):
        pkg = 'pep8'
        extra_index_url = 'http://foo.tld'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, extra_index_url=extra_index_url)
            mock.assert_called_once_with(
                ['pip', 'install', '--extra-index-url', extra_index_url, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_index_argument_in_resulting_command(self):
        pkg = 'pep8'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, no_index=True)
            mock.assert_called_once_with(
                ['pip', 'install', '--no-index', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_build_argument_in_resulting_command(self):
        pkg = 'pep8'
        build = '/tmp/foo'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, build=build)
            mock.assert_called_once_with(
                ['pip', 'install', '--build', build, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_target_argument_in_resulting_command(self):
        pkg = 'pep8'
        target = '/tmp/foo'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, target=target)
            mock.assert_called_once_with(
                ['pip', 'install', '--target', target, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_download_argument_in_resulting_command(self):
        pkg = 'pep8'
        download = '/tmp/foo'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, download=download)
            mock.assert_called_once_with(
                ['pip', 'install', '--download', download, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_download_argument_in_resulting_command(self):
        pkg = 'pep8'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, no_download=True)
            mock.assert_called_once_with(
                ['pip', 'install', '--no-download', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_download_cache_dir_arguments_in_resulting_command(self):
        pkg = 'pep8'
        cache_dir_arg_mapping = {
            '1.5.6': '--download-cache',
            '6.0': '--cache-dir',
        }
        download_cache = '/tmp/foo'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})

        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            for pip_version, cmd_arg in cache_dir_arg_mapping.items():
                with patch('salt.modules.pip.version',
                           MagicMock(return_value=pip_version)):
                    # test `download_cache` kwarg
                    pip.install(pkg, download_cache='/tmp/foo')
                    mock.assert_called_with(
                        ['pip', 'install', cmd_arg, download_cache, pkg],
                        saltenv='base',
                        runas=None,
                        use_vt=False,
                        python_shell=False,
                    )

                    # test `cache_dir` kwarg
                    pip.install(pkg, cache_dir='/tmp/foo')
                    mock.assert_called_with(
                        ['pip', 'install', cmd_arg, download_cache, pkg],
                        saltenv='base',
                        runas=None,
                        use_vt=False,
                        python_shell=False,
                    )

    def test_install_source_argument_in_resulting_command(self):
        pkg = 'pep8'
        source = '/tmp/foo'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, source=source)
            mock.assert_called_once_with(
                ['pip', 'install', '--source', source, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_exists_action_argument_in_resulting_command(self):
        pkg = 'pep8'
        for action in ('s', 'i', 'w', 'b'):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install('pep8', exists_action=action)
                mock.assert_called_once_with(
                    ['pip', 'install', '--exists-action', action, pkg],
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

        # Test for invalid action
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                pip.install,
                pkg,
                exists_action='d'
            )

    def test_install_install_options_argument_in_resulting_command(self):
        install_options = [
            '--exec-prefix=/foo/bar',
            '--install-scripts=/foo/bar/bin'
        ]
        pkg = 'pep8'

        expected = ['pip', 'install']
        for item in install_options:
            expected.extend(['--install-option', item])
        expected.append(pkg)

        # Passing options as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, install_options=install_options)
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, install_options=','.join(install_options))
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a single string entry
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, install_options=install_options[0])
            mock.assert_called_once_with(
                ['pip', 'install', '--install-option',
                 install_options[0], pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_global_options_argument_in_resulting_command(self):
        global_options = [
            '--quiet',
            '--no-user-cfg'
        ]
        pkg = 'pep8'

        expected = ['pip', 'install']
        for item in global_options:
            expected.extend(['--global-option', item])
        expected.append(pkg)

        # Passing options as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, global_options=global_options)
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, global_options=','.join(global_options))
            mock.assert_called_once_with(
                expected,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a single string entry
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, global_options=global_options[0])
            mock.assert_called_once_with(
                ['pip', 'install', '--global-option', global_options[0], pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_upgrade_argument_in_resulting_command(self):
        pkg = 'pep8'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, upgrade=True)
            mock.assert_called_once_with(
                ['pip', 'install', '--upgrade', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_force_reinstall_argument_in_resulting_command(self):
        pkg = 'pep8'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, force_reinstall=True)
            mock.assert_called_once_with(
                ['pip', 'install', '--force-reinstall', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_ignore_installed_argument_in_resulting_command(self):
        pkg = 'pep8'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, ignore_installed=True)
            mock.assert_called_once_with(
                ['pip', 'install', '--ignore-installed', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_deps_argument_in_resulting_command(self):
        pkg = 'pep8'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, no_deps=True)
            mock.assert_called_once_with(
                ['pip', 'install', '--no-deps', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_no_install_argument_in_resulting_command(self):
        pkg = 'pep8'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, no_install=True)
            mock.assert_called_once_with(
                ['pip', 'install', '--no-install', pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_proxy_argument_in_resulting_command(self):
        pkg = 'pep8'
        proxy = 'salt-user:salt-passwd@salt-proxy:3128'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.install(pkg, proxy=proxy)
            mock.assert_called_once_with(
                ['pip', 'install', '--proxy', proxy, pkg],
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_install_multiple_requirements_arguments_in_resulting_command(self):
        with patch('salt.modules.pip._get_cached_requirements') as get_cached_requirements:
            cached_reqs = [
                'my_cached_reqs-1', 'my_cached_reqs-2'
            ]
            get_cached_requirements.side_effect = cached_reqs
            requirements = [
                'salt://requirements-1.txt', 'salt://requirements-2.txt'
            ]

            expected = ['pip', 'install']
            for item in cached_reqs:
                expected.extend(['--requirement', item])

            # Passing option as a list
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(requirements=requirements)
                mock.assert_called_once_with(
                    expected,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

            # Passing option as a comma separated list
            get_cached_requirements.side_effect = cached_reqs
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(requirements=','.join(requirements))
                mock.assert_called_once_with(
                    expected,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

            # Passing option as a single string entry
            get_cached_requirements.side_effect = [cached_reqs[0]]
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.install(requirements=requirements[0])
                mock.assert_called_once_with(
                    ['pip', 'install', '--requirement', cached_reqs[0]],
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

    def test_uninstall_multiple_requirements_arguments_in_resulting_command(self):
        with patch('salt.modules.pip._get_cached_requirements') as get_cached_requirements:
            cached_reqs = [
                'my_cached_reqs-1', 'my_cached_reqs-2'
            ]
            get_cached_requirements.side_effect = cached_reqs
            requirements = [
                'salt://requirements-1.txt', 'salt://requirements-2.txt'
            ]

            expected = ['pip', 'uninstall', '-y']
            for item in cached_reqs:
                expected.extend(['--requirement', item])

            # Passing option as a list
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.uninstall(requirements=requirements)
                mock.assert_called_once_with(
                    expected,
                    cwd=None,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

            # Passing option as a comma separated list
            get_cached_requirements.side_effect = cached_reqs
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.uninstall(requirements=','.join(requirements))
                mock.assert_called_once_with(
                    expected,
                    cwd=None,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

            # Passing option as a single string entry
            get_cached_requirements.side_effect = [cached_reqs[0]]
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.uninstall(requirements=requirements[0])
                mock.assert_called_once_with(
                    ['pip', 'uninstall', '-y', '--requirement', cached_reqs[0]],
                    cwd=None,
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

    def test_uninstall_proxy_argument_in_resulting_command(self):
        pkg = 'pep8'
        proxy = 'salt-user:salt-passwd@salt-proxy:3128'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall(pkg, proxy=proxy)
            mock.assert_called_once_with(
                ['pip', 'uninstall', '-y', '--proxy', proxy, pkg],
                saltenv='base',
                cwd=None,
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    def test_uninstall_log_argument_in_resulting_command(self):
        with patch('os.path') as mock_path:
            pkg = 'pep8'
            log_path = '/tmp/pip-install.log'
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
                pip.uninstall(pkg, log=log_path)
                mock.assert_called_once_with(
                    ['pip', 'uninstall', '-y', '--log', log_path, pkg],
                    saltenv='base',
                    cwd=None,
                    runas=None,
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
                    pkg,
                    log=log_path
                )

    def test_uninstall_timeout_argument_in_resulting_command(self):
        pkg = 'pep8'
        expected_prefix = ['pip', 'uninstall', '-y', '--timeout']
        # Passing an int
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall(pkg, timeout=10)
            mock.assert_called_once_with(
                expected_prefix + [10, pkg],
                cwd=None,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing an int as a string
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            pip.uninstall(pkg, timeout='10')
            mock.assert_called_once_with(
                expected_prefix + ['10', pkg],
                cwd=None,
                saltenv='base',
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing a non-int to timeout
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                ValueError,
                pip.uninstall,
                pkg,
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
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='6.1.1')):
                ret = pip.freeze()
                mock.assert_called_once_with(
                    ['pip', 'freeze'],
                    cwd=None,
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )
                self.assertEqual(ret, eggs)

        # Non zero returncode raises exception?
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'CABOOOOMMM!'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='6.1.1')):
                self.assertRaises(
                    CommandExecutionError,
                    pip.freeze,
                )

    def test_freeze_command_with_all(self):
        eggs = [
            'M2Crypto==0.21.1',
            '-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev',
            'bbfreeze==1.1.0',
            'bbfreeze-loader==1.1.0',
            'pip==0.9.1',
            'pycrypto==2.6',
            'setuptools==20.10.1'
        ]
        mock = MagicMock(
            return_value={
                'retcode': 0,
                'stdout': '\n'.join(eggs)
            }
        )
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='9.0.1')):
                ret = pip.freeze()
                mock.assert_called_once_with(
                    ['pip', 'freeze', '--all'],
                    cwd=None,
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )
                self.assertEqual(ret, eggs)

        # Non zero returncode raises exception?
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'CABOOOOMMM!'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='9.0.1')):
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
        mock_version = '6.1.1'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': '\n'.join(eggs)})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value=mock_version)):
                ret = pip.list_()
                mock.assert_called_with(
                    ['pip', 'freeze'],
                    cwd=None,
                    runas=None,
                    python_shell=False,
                    use_vt=False,
                )
                self.assertEqual(
                    ret, {
                        'SaltTesting-dev': 'git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8',
                        'M2Crypto': '0.21.1',
                        'bbfreeze-loader': '1.1.0',
                        'bbfreeze': '1.1.0',
                        'pip': mock_version,
                        'pycrypto': '2.6'
                    }
                )

        # Non zero returncode raises exception?
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'CABOOOOMMM!'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='6.1.1')):
                self.assertRaises(
                    CommandExecutionError,
                    pip.list_,
                )

    def test_list_command_with_all(self):
        eggs = [
            'M2Crypto==0.21.1',
            '-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev',
            'bbfreeze==1.1.0',
            'bbfreeze-loader==1.1.0',
            'pip==9.0.1',
            'pycrypto==2.6',
            'setuptools==20.10.1'
        ]
        # N.B.: this is deliberately different from the "output" of pip freeze.
        # This is to demonstrate that the version reported comes from freeze
        # instead of from the pip.version function.
        mock_version = '9.0.0'
        mock = MagicMock(return_value={'retcode': 0, 'stdout': '\n'.join(eggs)})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value=mock_version)):
                ret = pip.list_()
                mock.assert_called_with(
                    ['pip', 'freeze', '--all'],
                    cwd=None,
                    runas=None,
                    python_shell=False,
                    use_vt=False,
                )
                self.assertEqual(
                    ret, {
                        'SaltTesting-dev': 'git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8',
                        'M2Crypto': '0.21.1',
                        'bbfreeze-loader': '1.1.0',
                        'bbfreeze': '1.1.0',
                        'pip': '9.0.1',
                        'pycrypto': '2.6',
                        'setuptools': '20.10.1'
                    }
                )

        # Non zero returncode raises exception?
        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'CABOOOOMMM!'})
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='6.1.1')):
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
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='6.1.1')):
                ret = pip.list_(prefix='bb')
                mock.assert_called_with(
                    ['pip', 'freeze'],
                    cwd=None,
                    runas=None,
                    python_shell=False,
                    use_vt=False,
                )
                self.assertEqual(
                    ret, {
                        'bbfreeze-loader': '1.1.0',
                        'bbfreeze': '1.1.0',
                    }
                )

    def test_install_pre_argument_in_resulting_command(self):
        pkg = 'pep8'
        # Lower than 1.4 versions don't end-up with `--pre` in the resulting
        # output
        mock = MagicMock(side_effect=[
            {'retcode': 0, 'stdout': 'pip 1.2.0 /path/to/site-packages/pip'},
            {'retcode': 0, 'stdout': ''}
        ])
        with patch.dict(pip.__salt__, {'cmd.run_all': mock}):
            with patch('salt.modules.pip.version',
                       MagicMock(return_value='1.3')):
                pip.install(pkg, pre_releases=True)
                mock.assert_called_with(
                    ['pip', 'install', pkg],
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

        mock_run = MagicMock(return_value='pip 1.4.1 /path/to/site-packages/pip')
        mock_run_all = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(pip.__salt__, {'cmd.run_stdout': mock_run,
                                       'cmd.run_all': mock_run_all}):
            with patch('salt.modules.pip._get_pip_bin',
                       MagicMock(return_value='pip')):
                pip.install(pkg, pre_releases=True)
                mock_run_all.assert_called_with(
                    ['pip', 'install', '--pre', pkg],
                    saltenv='base',
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )
