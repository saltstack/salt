# -*- coding: utf-8 -*-
'''
    tests.unit.modules.virtualenv_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libraries
import sys
import warnings

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath, TestsLoggingHandler
ensure_in_syspath('../../')

# Import 3rd party libs
try:
    import virtualenv
except ImportError:
    # Let's create a fake virtualenv with what we need to run these tests
    import new
    virtualenv = new.module('virtualenv')
    virtualenv.__version__ = '1.9.1'
    sys.modules['virtualenv'] = virtualenv

try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False
    patch = lambda x: lambda y: None


# Import salt libs
from salt.modules import virtualenv_mod
from salt.exceptions import CommandExecutionError

virtualenv_mod.__salt__ = {'cmd.which_bin': lambda _: 'virtualenv'}


@skipIf(has_mock is False, 'mock python module is unavailable')
class VirtualenvTestCase(TestCase):

    def test_issue_6029_deprecated_distribute(self):
        VIRTUALENV_VERSION_INFO = virtualenv_mod.VIRTUALENV_VERSION_INFO

        virtualenv_mod.VIRTUALENV_VERSION_INFO = (1, 9, 1)
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})

        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            virtualenv_mod.create(
                '/tmp/foo', system_site_packages=True, distribute=True
            )
            mock.assert_called_once_with(
                'virtualenv --distribute --system-site-packages /tmp/foo',
                runas=None
            )

        with TestsLoggingHandler() as handler:
            virtualenv_mod.VIRTUALENV_VERSION_INFO = (1, 10)
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                virtualenv_mod.create(
                    '/tmp/foo', system_site_packages=True, distribute=True
                )
                mock.assert_called_once_with(
                    'virtualenv --system-site-packages /tmp/foo', runas=None
                )

            # Are we logging the deprecation information?
            self.assertIn(
                'INFO:The virtualenv \'--distribute\' option has been '
                'deprecated in virtualenv(>=1.10), as such, the '
                '\'distribute\' option to `virtualenv.create()` has '
                'also been deprecated and it\'s not necessary anymore.',
                handler.messages
            )

        virtualenv_mod.VIRTUALENV_VERSION_INFO = VIRTUALENV_VERSION_INFO

    def test_issue_6030_deprecated_never_download(self):
        VIRTUALENV_VERSION_INFO = virtualenv_mod.VIRTUALENV_VERSION_INFO

        virtualenv_mod.VIRTUALENV_VERSION_INFO = (1, 9, 1)
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
            virtualenv_mod.VIRTUALENV_VERSION_INFO = (1, 10)
            mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
                virtualenv_mod.create(
                    '/tmp/foo', never_download=True
                )
                mock.assert_called_once_with('virtualenv /tmp/foo', runas=None)

            # Are we logging the deprecation information?
            self.assertIn(
                'INFO:The virtualenv \'--never-download\' option has been '
                'deprecated in virtualenv(>=1.10), as such, the '
                '\'never_download\' option to `virtualenv.create()` has '
                'also been deprecated and it\'s not necessary anymore.',
                handler.messages
            )
        virtualenv_mod.VIRTUALENV_VERSION_INFO = VIRTUALENV_VERSION_INFO

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
        # NOTE: If this test starts failing it might be because the deprecation
        # warning was removed, or because some other test in this module is
        # passing 'no_site_packages' to 'virtualenv_mod.create'. The
        # deprecation warning is shown only once.

        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(virtualenv_mod.__salt__, {'cmd.run_all': mock}):
            with warnings.catch_warnings(record=True) as w:
                virtualenv_mod.create(
                    '/tmp/foo', no_site_packages=True
                )
                self.assertEqual(
                    '\'no_site_packages\' has been deprecated. Please start '
                    'using \'system_site_packages=False\' which means exactly '
                    'the same as \'no_site_packages=True\'', str(w[-1].message)
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtualenvTestCase, needs_daemon=False)
