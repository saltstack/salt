# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.modules.virtualenv_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libraries
import warnings

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import (
    ensure_in_syspath,
    TestsLoggingHandler,
    ForceImportErrorOn
)
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import virtualenv_mod
from salt.exceptions import CommandExecutionError

virtualenv_mod.__salt__ = {}
base_virtualenv_mock = MagicMock()
base_virtualenv_mock.__version__ = '1.9.1'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.utils.which', lambda bin_name: bin_name)
@patch.dict('sys.modules', {'virtualenv': base_virtualenv_mock})
class VirtualenvTestCase(TestCase):

    def test_issue_6029_deprecated_distribute(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod._install_script = MagicMock(
                return_value={
                    'retcode': 0,
                    'stdout': 'Installed script!',
                    'stderr': ''
                }
            )
            virtualenv_mod.create(
                '/tmp/foo', system_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                'virtualenv --distribute --system-site-packages /tmp/foo',
                runas=None
            )

        with TestsLoggingHandler() as handler:
            # Let's fake a higher virtualenv version
            virtualenv_mock = MagicMock()
            virtualenv_mock.__version__ = '1.10rc1'
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                with patch.dict('sys.modules',
                                {'virtualenv': virtualenv_mock}):
                    virtualenv_mod.create(
                        '/tmp/foo', system_site_packages=True, distribute=True
                    )
                    mock.assert_called_once_with(
                        'virtualenv --system-site-packages /tmp/foo',
                        runas=None
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
                'virtualenv --never-download /tmp/foo',
                runas=None
            )

        with TestsLoggingHandler() as handler:
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
                    mock.assert_called_once_with('virtualenv /tmp/foo',
                                                 runas=None)

                # Are we logging the deprecation information?
                self.assertIn(
                    'INFO:The virtualenv \'--never-download\' option has been '
                    'deprecated in virtualenv(>=1.10), as such, the '
                    '\'never_download\' option to `virtualenv.create()` has '
                    'also been deprecated and it\'s not necessary anymore.',
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
                'virtualenv '
                '--extra-search-dir=/tmp/bar-1 '
                '--extra-search-dir=/tmp/bar-2 '
                '--extra-search-dir=/tmp/bar-3 '
                '/tmp/foo',
                runas=None
            )

        # Passing extra_search_dirs as comma separated list
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', extra_search_dir=','.join(extra_search_dirs)
            )
            mock.assert_called_once_with(
                'virtualenv '
                '--extra-search-dir=/tmp/bar-1 '
                '--extra-search-dir=/tmp/bar-2 '
                '--extra-search-dir=/tmp/bar-3 '
                '/tmp/foo',
                runas=None
            )

    def test_system_site_packages_and_no_site_packages_mutual_exclusion(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                no_site_packages=True,
                system_site_packages=True
            )

    def test_no_site_packages_deprecation(self):
        # We *always* want *all* warnings thrown on this module
        warnings.resetwarnings()
        warnings.filterwarnings('always', '', DeprecationWarning, __name__)

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            with warnings.catch_warnings(record=True) as w:
                virtualenv_mod.create(
                    '/tmp/foo', no_site_packages=True
                )
                self.assertEqual(
                    '\'no_site_packages\' has been deprecated. Please '
                    'start using \'system_site_packages=False\' which '
                    'means exactly the same as \'no_site_packages=True\'',
                    str(w[-1].message)
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
        virtualenv_mod.__salt__ = {'cmd.which_bin': lambda _: 'pyvenv'}

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(
                CommandExecutionError,
                virtualenv_mod.create,
                '/tmp/foo',
                venv_bin='pyvenv',
                no_site_packages=True
            )

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
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

            # ----- virtualenv binary returns 1.9.1 as it's version --------->
            mock = MagicMock(side_effect=[
                {'retcode': 0, 'stdout': '1.9.1'},
                {'retcode': 0, 'stdout': ''}
            ])
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                virtualenv_mod.create(
                    '/tmp/foo', never_download=True
                )
                mock.assert_called_with(
                    'virtualenv --never-download /tmp/foo',
                    runas=None
                )
            # <---- virtualenv binary returns 1.9.1 as it's version ----------

            # ----- virtualenv binary returns 1.10rc1 as it's version ------->
            mock = MagicMock(side_effect=[
                {'retcode': 0, 'stdout': '1.10rc1'},
                {'retcode': 0, 'stdout': ''}
            ])
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                virtualenv_mod.create(
                    '/tmp/foo', never_download=True
                )
                mock.assert_called_with(
                    'virtualenv /tmp/foo',
                    runas=None
                )
            # <---- virtualenv binary returns 1.10rc1 as it's version --------

    def test_python_argument(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', python='/usr/bin/python2.7',
            )
            mock.assert_called_once_with(
                'virtualenv --python=/usr/bin/python2.7 /tmp/foo',
                runas=None
            )

    def test_prompt_argument(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', prompt='PY Prompt')
            mock.assert_called_once_with(
                'virtualenv --prompt=\'PY Prompt\' /tmp/foo',
                runas=None
            )

        # Now with some quotes on the mix
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', prompt='\'PY\' Prompt')
            mock.assert_called_once_with(
                'virtualenv --prompt="\'PY\' Prompt" /tmp/foo',
                runas=None
            )

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', prompt='"PY" Prompt')
            mock.assert_called_once_with(
                'virtualenv --prompt=\'"PY" Prompt\' /tmp/foo',
                runas=None
            )

    def test_clear_argument(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', clear=True)
            mock.assert_called_once_with(
                'virtualenv --clear /tmp/foo', runas=None
            )

    def test_upgrade_argument(self):
        # We test for pyvenv only because with virtualenv this is un
        # unsupported option.
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', venv_bin='pyvenv', upgrade=True)
            mock.assert_called_once_with(
                'pyvenv --upgrade /tmp/foo', runas=None
            )

    def test_symlinks_argument(self):
        # We test for pyvenv only because with virtualenv this is un
        # unsupported option.
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create('/tmp/foo', venv_bin='pyvenv', symlinks=True)
            mock.assert_called_once_with(
                'pyvenv --symlinks /tmp/foo', runas=None
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtualenvTestCase, needs_daemon=False)
