# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.modules.virtualenv_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import sys

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.helpers import TstSuiteLoggingHandler, ForceImportErrorOn
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.virtualenv_mod as virtualenv_mod
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class VirtualenvTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        base_virtualenv_mock = MagicMock()
        base_virtualenv_mock.__version__ = '1.9.1'
        patcher = patch('salt.utils.path.which', lambda exe: exe)
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            virtualenv_mod: {
                '__opts__': {'venv_bin': 'virtualenv'},
                '_install_script': MagicMock(return_value={'retcode': 0,
                                                           'stdout': 'Installed script!',
                                                           'stderr': ''}),
                'sys.modules': {'virtualenv': base_virtualenv_mock}
            }
        }

    def test_issue_6029_deprecated_distribute(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', system_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                ['virtualenv', '--distribute', '--system-site-packages', '/tmp/foo'],
                runas=None,
                python_shell=False
            )

        with TstSuiteLoggingHandler() as handler:
            # Let's fake a higher virtualenv version
            virtualenv_mock = MagicMock()
            virtualenv_mock.__version__ = '1.10rc1'
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                with patch.dict('sys.modules', {'virtualenv': virtualenv_mock}):
                    virtualenv_mod.create(
                        '/tmp/foo', system_site_packages=True, distribute=True
                    )
                    mock.assert_called_once_with(
                        ['virtualenv', '--system-site-packages', '/tmp/foo'],
                        runas=None,
                        python_shell=False
                    )

                # Are we logging the deprecation information?
                self.assertIn(
                    'INFO:The virtualenv \'--distribute\' option has been '
                    'deprecated in virtualenv(>=1.10), as such, the '
                    '\'distribute\' option to `virtualenv.create()` has '
                    'also been deprecated and it\'s not necessary anymore.',
                    handler.messages
                )

    def test_issue_6030_deprecated_never_download(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', never_download=True
            )
            mock.assert_called_once_with(
                ['virtualenv', '--never-download', '/tmp/foo'],
                runas=None,
                python_shell=False
            )

        with TstSuiteLoggingHandler() as handler:
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            # Let's fake a higher virtualenv version
            virtualenv_mock = MagicMock()
            virtualenv_mock.__version__ = '1.10rc1'
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                with patch.dict('sys.modules',
                                {'virtualenv': virtualenv_mock}):
                    virtualenv_mod.create(
                        '/tmp/foo', never_download=True
                    )
                    mock.assert_called_once_with(['virtualenv', '/tmp/foo'],
                                                 runas=None,
                                                 python_shell=False)

                # Are we logging the deprecation information?
                self.assertIn(
                    'INFO:--never-download was deprecated in 1.10.0, '
                    'but reimplemented in 14.0.0. If this feature is needed, '
                    'please install a supported virtualenv version.',
                    handler.messages
                )

    def test_issue_6031_multiple_extra_search_dirs(self):
        extra_search_dirs = [
            '/tmp/bar-1',
            '/tmp/bar-2',
            '/tmp/bar-3'
        ]

        # Passing extra_search_dirs as a list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', extra_search_dir=extra_search_dirs
            )
            mock.assert_called_once_with(
                ['virtualenv',
                '--extra-search-dir=/tmp/bar-1',
                '--extra-search-dir=/tmp/bar-2',
                '--extra-search-dir=/tmp/bar-3',
                '/tmp/foo'],
                runas=None,
                python_shell=False
            )

        # Passing extra_search_dirs as comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', extra_search_dir=','.join(extra_search_dirs)
            )
            mock.assert_called_once_with(
                ['virtualenv',
                '--extra-search-dir=/tmp/bar-1',
                '--extra-search-dir=/tmp/bar-2',
                '--extra-search-dir=/tmp/bar-3',
                '/tmp/foo'],
                runas=None,
                python_shell=False
            )

    def test_unapplicable_options(self):
        # ----- Virtualenv using pyvenv options ----------------------------->
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                venv_bin='virtualenv',
                upgrade=True
            )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                venv_bin='virtualenv',
                symlinks=True
            )
        # <---- Virtualenv using pyvenv options ------------------------------

        # ----- pyvenv using virtualenv options ----------------------------->
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock,
                                                  'cmd.which_bin': lambda _: 'pyvenv'}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                venv_bin='pyvenv',
                python='python2.7'
            )

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                venv_bin='pyvenv',
                prompt='PY Prompt'
            )

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                venv_bin='pyvenv',
                never_download=True
            )

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                venv_bin='pyvenv',
                extra_search_dir='/tmp/bar'
            )
        # <---- pyvenv using virtualenv options ------------------------------

    def test_get_virtualenv_version_from_shell(self):
        with ForceImportErrorOn('virtualenv'):

            # ----- virtualenv binary not available ------------------------->
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(
                    CommandExecutionError,
                    virtualenv_mod.create,
                    '/tmp/foo',
                )
            # <---- virtualenv binary not available --------------------------

            # ----- virtualenv binary present but > 0 exit code ------------->
            mock = MagicMock(side_effect=[
                {'retcode': 1, 'stdout': '', 'stderr': 'This is an error'},
                {'retcode': 0, 'stdout': ''}
            ])
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(
                    CommandExecutionError,
                    virtualenv_mod.create,
                    '/tmp/foo',
                    venv_bin='virtualenv',
                )
            # <---- virtualenv binary present but > 0 exit code --------------

            # ----- virtualenv binary returns 1.9.1 as its version --------->
            mock = MagicMock(side_effect=[
                {'retcode': 0, 'stdout': '1.9.1'},
                {'retcode': 0, 'stdout': ''}
            ])
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                virtualenv_mod.create(
                    '/tmp/foo', never_download=True
                )
                mock.assert_called_with(
                    ['virtualenv', '--never-download', '/tmp/foo'],
                    runas=None,
                    python_shell=False
                )
            # <---- virtualenv binary returns 1.9.1 as its version ----------

            # ----- virtualenv binary returns 1.10rc1 as its version ------->
            mock = MagicMock(side_effect=[
                {'retcode': 0, 'stdout': '1.10rc1'},
                {'retcode': 0, 'stdout': ''}
            ])
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                virtualenv_mod.create(
                    '/tmp/foo', never_download=True
                )
                mock.assert_called_with(
                    ['virtualenv', '/tmp/foo'],
                    runas=None,
                    python_shell=False
                )
            # <---- virtualenv binary returns 1.10rc1 as its version --------

    def test_python_argument(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', python=sys.executable,
            )
            mock.assert_called_once_with(
                ['virtualenv', '--python={0}'.format(sys.executable), '/tmp/foo'],
                runas=None,
                python_shell=False
            )

    def test_prompt_argument(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', prompt='PY Prompt')
            mock.assert_called_once_with(
                ['virtualenv', '--prompt=\'PY Prompt\'', '/tmp/foo'],
                runas=None,
                python_shell=False
            )

        # Now with some quotes on the mix
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', prompt='\'PY\' Prompt')
            mock.assert_called_once_with(
                ['virtualenv', "--prompt=''PY' Prompt'", '/tmp/foo'],
                runas=None,
                python_shell=False
            )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', prompt='"PY" Prompt')
            mock.assert_called_once_with(
                ['virtualenv', '--prompt=\'"PY" Prompt\'', '/tmp/foo'],
                runas=None,
                python_shell=False
            )

    def test_clear_argument(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', clear=True)
            mock.assert_called_once_with(
                ['virtualenv', '--clear', '/tmp/foo'],
                runas=None,
                python_shell=False
            )

    def test_upgrade_argument(self):
        # We test for pyvenv only because with virtualenv this is un
        # unsupported option.
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', venv_bin='pyvenv', upgrade=True)
            mock.assert_called_once_with(
                ['pyvenv', '--upgrade', '/tmp/foo'],
                runas=None,
                python_shell=False
            )

    def test_symlinks_argument(self):
        # We test for pyvenv only because with virtualenv this is un
        # unsupported option.
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', venv_bin='pyvenv', symlinks=True)
            mock.assert_called_once_with(
                ['pyvenv', '--symlinks', '/tmp/foo'],
                runas=None,
                python_shell=False
            )

    def test_venv_bin_binary_missing(self):
        '''
        test when none of the venv binaries
        exist on the system
        '''
        venv_cmd = ['--distribute', '--system-site-packages', '/tmp/foo']
        if sys.version_info >= (3, 6):
            venv_cmd = ['python3', '-m', 'venv'] + venv_cmd
        else:
            venv_cmd = ['virtualenv'] + venv_cmd

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}), \
            patch.dict(virtualenv_mod.__opts__, {'venv_bin': None}):
            virtualenv_mod.create(
                '/tmp/foo', system_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                venv_cmd,
                runas=None,
                python_shell=False
            )

    def test_venv_bin_from_pillar(self):
        '''
        test when venv_bin is set in pillar
        '''
        venv_bin = 'venv_from_pillar'
        venv_cmd = [venv_bin, '--distribute', '--system-site-packages', '/tmp/foo']

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}), \
            patch.dict(virtualenv_mod.__opts__, {'venv_bin': 'virtualenv'}), \
            patch.dict(virtualenv_mod.__pillar__, {'venv_bin':
                                                   venv_bin}):
            virtualenv_mod.create(
                '/tmp/foo', system_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                venv_cmd,
                runas=None,
                python_shell=False
            )

    def test_venv_bin_from_opts(self):
        '''
        test when venv_bin is set in opts
        '''
        venv_bin = 'virtualenv_from_opts'
        venv_cmd = [venv_bin, '--distribute', '--system-site-packages', '/tmp/foo']

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}), \
            patch.dict(virtualenv_mod.__opts__, {'venv_bin': venv_bin}), \
            patch.dict(virtualenv_mod.__pillar__, {'venv_bin': None}):

            virtualenv_mod.create(
                '/tmp/foo', system_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                venv_cmd,
                runas=None,
                python_shell=False
            )
