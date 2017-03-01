# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import pkgutil
from salt.exceptions import CommandExecutionError, MinionError

# Globals
pkgutil.__salt__ = {}
pkgutil.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgutilTestCase(TestCase):
    '''
    Test cases for salt.modules.pkgutil
    '''
    # 'refresh_db' function tests: 1

    def test_refresh_db(self):
        '''
        Test if it updates the pkgutil repo database (pkgutil -U).
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(pkgutil.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(pkgutil.refresh_db())

    # 'upgrade_available' function tests: 1

    def test_upgrade_available(self):
        '''
        Test if there is an upgrade available for a certain package.
        '''
        mock = MagicMock(return_value='A\n B\n SAME')
        with patch.dict(pkgutil.__salt__, {'cmd.run_stdout': mock}):
            self.assertEqual(pkgutil.upgrade_available('CSWpython'), '')

        mock = MagicMock(side_effect=['A\n B\n SALT', None])
        with patch.dict(pkgutil.__salt__, {'cmd.run_stdout': mock}):
            self.assertEqual(pkgutil.upgrade_available('CSWpython'), 'SALT')

            self.assertEqual(pkgutil.upgrade_available('CSWpython'), '')

    # 'list_upgrades' function tests: 1

    def test_list_upgrades(self):
        '''
        Test if it list all available package upgrades on this system.
        '''
        mock_run = MagicMock(return_value='A\t B\t SAME')
        mock_ret = MagicMock(return_value=0)
        with patch.dict(pkgutil.__salt__, {'cmd.run_stdout': mock_run,
                                           'cmd.retcode': mock_ret}):
            self.assertDictEqual(pkgutil.list_upgrades(), {'A': ' B'})

    # 'upgrade' function tests: 1

    def test_upgrade(self):
        '''
        Test if it upgrade all of the packages to the latest available version.
        '''
        mock_run = MagicMock(return_value='A\t B\t SAME')
        mock_ret = MagicMock(return_value=0)
        mock_pkg = MagicMock(return_value='')
        with patch.dict(pkgutil.__salt__,
                        {'cmd.run_stdout': mock_run,
                         'cmd.retcode': mock_ret,
                         'pkg_resource.stringify': mock_pkg,
                         'pkg_resource.sort_pkglist': mock_pkg,
                         'cmd.run_all': mock_ret, 'cmd.run': mock_run}):
            with patch.dict(pkgutil.__context__, {'pkg.list_pkgs': mock_ret}):
                self.assertDictEqual(pkgutil.upgrade(), {})

    # 'list_pkgs' function tests: 1

    def test_list_pkgs(self):
        '''
        Test if it list the packages currently installed as a dict.
        '''
        mock_run = MagicMock(return_value='A\t B\t SAME')
        mock_ret = MagicMock(return_value=True)
        mock_pkg = MagicMock(return_value='')
        with patch.dict(pkgutil.__salt__,
                        {'cmd.run_stdout': mock_run,
                         'cmd.retcode': mock_ret,
                         'pkg_resource.stringify': mock_pkg,
                         'pkg_resource.sort_pkglist': mock_pkg,
                         'cmd.run': mock_run}):
            with patch.dict(pkgutil.__context__, {'pkg.list_pkgs': mock_ret}):
                self.assertDictEqual(pkgutil.list_pkgs(versions_as_list=True,
                                                       removed=True), {})

            self.assertDictEqual(pkgutil.list_pkgs(), {})

        with patch.dict(pkgutil.__context__, {'pkg.list_pkgs': True}):
            self.assertTrue(pkgutil.list_pkgs(versions_as_list=True))

            mock_pkg = MagicMock(return_value=True)
            with patch.dict(pkgutil.__salt__,
                            {'pkg_resource.stringify': mock_pkg}):
                self.assertTrue(pkgutil.list_pkgs())

    # 'version' function tests: 1

    def test_version(self):
        '''
        Test if it returns a version if the package is installed.
        '''
        mock_ret = MagicMock(return_value=True)
        with patch.dict(pkgutil.__salt__, {'pkg_resource.version': mock_ret}):
            self.assertTrue(pkgutil.version('CSWpython'))

    # 'latest_version' function tests: 1

    def test_latest_version(self):
        '''
        Test if it return the latest version of the named package
        available for upgrade or installation.
        '''
        self.assertEqual(pkgutil.latest_version(), '')

        mock_run_all = MagicMock(return_value='A\t B\t SAME')
        mock_run = MagicMock(return_value={'stdout': ''})
        mock_ret = MagicMock(return_value=True)
        mock_pkg = MagicMock(return_value='')
        with patch.dict(pkgutil.__salt__,
                        {'cmd.retcode': mock_ret,
                         'pkg_resource.stringify': mock_pkg,
                         'pkg_resource.sort_pkglist': mock_pkg,
                         'cmd.run_all': mock_run, 'cmd.run': mock_run_all}):
            self.assertEqual(pkgutil.latest_version('CSWpython'), '')

            self.assertDictEqual(pkgutil.latest_version('CSWpython', 'Python'),
                                 {'Python': '', 'CSWpython': ''})

    # 'install' function tests: 1

    def test_install(self):
        '''
        Test if it install packages using the pkgutil tool.
        '''
        mock_pkg = MagicMock(side_effect=MinionError)
        with patch.dict(pkgutil.__salt__,
                        {'pkg_resource.parse_targets': mock_pkg}):
            self.assertRaises(CommandExecutionError, pkgutil.install)

        mock_ret = MagicMock(return_value=True)
        mock_pkg = MagicMock(return_value=[''])
        with patch.dict(pkgutil.__salt__,
                        {'pkg_resource.parse_targets': mock_pkg}):
            with patch.dict(pkgutil.__context__, {'pkg.list_pkgs': mock_ret}):
                self.assertDictEqual(pkgutil.install(), {})

        mock_run = MagicMock(return_value='A\t B\t SAME')
        mock_run_all = MagicMock(return_value={'stdout': ''})
        mock_pkg = MagicMock(return_value=[{"bar": "1.2.3"}])
        with patch.dict(pkgutil.__salt__,
                        {'pkg_resource.parse_targets': mock_pkg,
                         'pkg_resource.stringify': mock_pkg,
                         'pkg_resource.sort_pkglist': mock_pkg,
                         'cmd.run_all': mock_run_all, 'cmd.run': mock_run}):
            with patch.dict(pkgutil.__context__, {'pkg.list_pkgs': mock_ret}):
                self.assertDictEqual(pkgutil.install
                                     (pkgs='["foo", {"bar": "1.2.3"}]'), {})

    # 'remove' function tests: 1

    def test_remove(self):
        '''
        Test if it remove a package and all its dependencies
        which are not in use by other packages.
        '''
        mock_pkg = MagicMock(side_effect=MinionError)
        with patch.dict(pkgutil.__salt__,
                        {'pkg_resource.parse_targets': mock_pkg}):
            self.assertRaises(CommandExecutionError, pkgutil.remove)

        mock_ret = MagicMock(return_value=True)
        mock_run = MagicMock(return_value='A\t B\t SAME')
        mock_run_all = MagicMock(return_value={'stdout': ''})
        mock_pkg = MagicMock(return_value=[''])
        with patch.dict(pkgutil.__salt__,
                        {'pkg_resource.parse_targets': mock_pkg,
                         'pkg_resource.stringify': mock_pkg,
                         'pkg_resource.sort_pkglist': mock_pkg,
                         'cmd.run_all': mock_run_all, 'cmd.run': mock_run}):
            with patch.dict(pkgutil.__context__, {'pkg.list_pkgs': mock_ret}):
                self.assertDictEqual(pkgutil.remove(), {})

        mock_pkg = MagicMock(return_value=[{"bar": "1.2.3"}])
        with patch.dict(pkgutil.__salt__,
                        {'pkg_resource.parse_targets': mock_pkg,
                         'pkg_resource.stringify': mock_pkg,
                         'pkg_resource.sort_pkglist': mock_pkg,
                         'cmd.run_all': mock_run_all, 'cmd.run': mock_run}):
            with patch.dict(pkgutil.__context__, {'pkg.list_pkgs': mock_ret}):
                with patch.object(pkgutil, 'list_pkgs',
                                  return_value={"bar": "1.2.3"}):
                    self.assertDictEqual(pkgutil.remove(pkgs='["foo", "bar"]'),
                                         {})

    # 'purge' function tests: 1

    def test_purge(self):
        '''
        Test if it package purges are not supported,
        this function is identical to ``remove()``.
        '''
        mock_pkg = MagicMock(side_effect=MinionError)
        with patch.dict(pkgutil.__salt__,
                        {'pkg_resource.parse_targets': mock_pkg}):
            self.assertRaises(CommandExecutionError, pkgutil.purge)
