# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.modules.alternatives_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.alternatives as alternatives


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AlternativesTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {alternatives: {}}

    def test_display(self):
        with patch.dict(alternatives.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': 'salt'})
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.display('better-world')
                self.assertEqual('salt', solution)
                mock.assert_called_once_with(
                    ['alternatives', '--display', 'better-world'],
                    python_shell=False
                )

        with patch.dict(alternatives.__grains__, {'os_family': 'Suse'}):
            mock = MagicMock(
                return_value={'retcode': 0, 'stdout': 'undoubtedly-salt'}
            )
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.display('better-world')
                self.assertEqual('undoubtedly-salt', solution)
                mock.assert_called_once_with(
                    ['update-alternatives', '--display', 'better-world'],
                    python_shell=False
                )

        with patch.dict(alternatives.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(
                return_value={
                    'retcode': 1,
                    'stdout': 'salt-out',
                    'stderr': 'salt-err'
                }
            )
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.display('better-world')
                self.assertEqual('salt-err', solution)
                mock.assert_called_once_with(
                    ['alternatives', '--display', 'better-world'],
                    python_shell=False
                )

    def test_show_current(self):
        mock = MagicMock(return_value='/etc/alternatives/salt')
        with patch('salt.utils.path.readlink', mock):
            ret = alternatives.show_current('better-world')
            self.assertEqual('/etc/alternatives/salt', ret)
            mock.assert_called_once_with('/etc/alternatives/better-world')

            with TstSuiteLoggingHandler() as handler:
                mock.side_effect = OSError('Hell was not found!!!')
                self.assertFalse(alternatives.show_current('hell'))
                mock.assert_called_with('/etc/alternatives/hell')
                self.assertIn('ERROR:alternative: hell does not exist',
                              handler.messages)

    def test_check_installed(self):
        mock = MagicMock(return_value='/etc/alternatives/salt')
        with patch('salt.utils.path.readlink', mock):
            self.assertTrue(
                alternatives.check_installed(
                    'better-world', '/etc/alternatives/salt'
                )
            )
            mock.return_value = False
            self.assertFalse(
                alternatives.check_installed(
                    'help', '/etc/alternatives/salt'
                )
            )

    def test_install(self):
        with patch.dict(alternatives.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': 'salt'})
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.install(
                    'better-world',
                    '/usr/bin/better-world',
                    '/usr/bin/salt',
                    100
                )
                self.assertEqual('salt', solution)
                mock.assert_called_once_with(
                    ['alternatives', '--install', '/usr/bin/better-world',
                     'better-world', '/usr/bin/salt', '100'],
                    python_shell=False
                )

        with patch.dict(alternatives.__grains__, {'os_family': 'Debian'}):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': 'salt'})
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.install(
                    'better-world',
                    '/usr/bin/better-world',
                    '/usr/bin/salt',
                    100
                )
                self.assertEqual('salt', solution)
                mock.assert_called_once_with(
                    ['update-alternatives', '--install', '/usr/bin/better-world',
                     'better-world', '/usr/bin/salt', '100'],
                    python_shell=False
                )

        with patch.dict(alternatives.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(
                return_value={
                    'retcode': 1,
                    'stdout': 'salt-out',
                    'stderr': 'salt-err'
                }
            )
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                ret = alternatives.install(
                    'better-world',
                    '/usr/bin/better-world',
                    '/usr/bin/salt',
                    100
                )
                self.assertEqual('salt-err', ret)
                mock.assert_called_once_with(
                    ['alternatives', '--install', '/usr/bin/better-world',
                     'better-world', '/usr/bin/salt', '100'],
                    python_shell=False
                )

    def test_remove(self):
        with patch.dict(alternatives.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': 'salt'})
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.remove(
                    'better-world',
                    '/usr/bin/better-world',
                )
                self.assertEqual('salt', solution)
                mock.assert_called_once_with(
                    ['alternatives', '--remove', 'better-world',
                     '/usr/bin/better-world'], python_shell=False
                )

        with patch.dict(alternatives.__grains__, {'os_family': 'Debian'}):
            mock = MagicMock(return_value={'retcode': 0, 'stdout': 'salt'})
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.remove(
                    'better-world',
                    '/usr/bin/better-world',
                )
                self.assertEqual('salt', solution)
                mock.assert_called_once_with(
                    ['update-alternatives', '--remove', 'better-world',
                     '/usr/bin/better-world'], python_shell=False
                )

        with patch.dict(alternatives.__grains__, {'os_family': 'RedHat'}):
            mock = MagicMock(
                return_value={
                    'retcode': 1,
                    'stdout': 'salt-out',
                    'stderr': 'salt-err'
                }
            )
            with patch.dict(alternatives.__salt__, {'cmd.run_all': mock}):
                solution = alternatives.remove(
                    'better-world',
                    '/usr/bin/better-world',
                )
                self.assertEqual('salt-err', solution)
                mock.assert_called_once_with(
                    ['alternatives', '--remove', 'better-world',
                     '/usr/bin/better-world'], python_shell=False
                )
