# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.modules.alternatives_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath, TestsLoggingHandler
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

ensure_in_syspath('../../')

# Import salt libs
from salt.modules import alternatives

alternatives.__salt__ = alternatives.__grains__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AlternativesTestCase(TestCase):

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

        with patch.dict(alternatives.__grains__, {'os_family': 'Ubuntu'}):
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

    @patch('os.readlink')
    def test_show_current(self, os_readlink_mock):
        os_readlink_mock.return_value = '/etc/alternatives/salt'
        ret = alternatives.show_current('better-world')
        self.assertEqual('/etc/alternatives/salt', ret)
        os_readlink_mock.assert_called_once_with(
            '/etc/alternatives/better-world'
        )

        with TestsLoggingHandler() as handler:
            os_readlink_mock.side_effect = OSError('Hell was not found!!!')
            self.assertFalse(alternatives.show_current('hell'))
            os_readlink_mock.assert_called_with('/etc/alternatives/hell')
            self.assertIn('ERROR:alternatives: path /etc/alternatives/hell '
                          'does not exist',
                          handler.messages)

    @patch('os.readlink')
    def test_check_installed(self, os_readlink_mock):
        os_readlink_mock.return_value = '/etc/alternatives/salt'
        self.assertTrue(
            alternatives.check_installed(
                'better-world', '/etc/alternatives/salt'
            )
        )
        os_readlink_mock.return_value = False
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AlternativesTestCase, needs_daemon=False)
