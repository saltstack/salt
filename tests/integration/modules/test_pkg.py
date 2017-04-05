# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.helpers import (
    destructiveTest,
    requires_network,
    requires_salt_modules,
)


class PkgModuleTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the pkg module
    '''
    def test_list(self):
        '''
        verify that packages are installed
        '''
        ret = self.run_function('pkg.list_pkgs')
        self.assertNotEqual(len(ret.keys()), 0)

    def test_version_cmp(self):
        '''
        test package version comparison on supported platforms
        '''
        func = 'pkg.version_cmp'
        os_family = self.run_function('grains.item', ['os_family'])['os_family']
        if os_family == 'Debian':
            lt = ['0.2.4-0ubuntu1', '0.2.4.1-0ubuntu1']
            eq = ['0.2.4-0ubuntu1', '0.2.4-0ubuntu1']
            gt = ['0.2.4.1-0ubuntu1', '0.2.4-0ubuntu1']

            self.assertEqual(self.run_function(func, lt), -1)
            self.assertEqual(self.run_function(func, eq), 0)
            self.assertEqual(self.run_function(func, gt), 1)
        elif os_family == 'Suse':
            lt = ['2.3.0-1', '2.3.1-15.1']
            eq = ['2.3.1-15.1', '2.3.1-15.1']
            gt = ['2.3.2-15.1', '2.3.1-15.1']

            self.assertEqual(self.run_function(func, lt), -1)
            self.assertEqual(self.run_function(func, eq), 0)
            self.assertEqual(self.run_function(func, gt), 1)
        else:
            self.skipTest('{0} is unavailable on {1}'.format(func, os_family))

    @requires_network()
    @destructiveTest
    def test_mod_del_repo(self):
        '''
        test modifying and deleting a software repository
        '''
        os_grain = self.run_function('grains.item', ['os'])['os']

        try:
            repo = None
            if os_grain == 'Ubuntu':
                repo = 'ppa:otto-kesselgulasch/gimp-edge'
                uri = 'http://ppa.launchpad.net/otto-kesselgulasch/gimp-edge/ubuntu'
                ret = self.run_function('pkg.mod_repo', [repo, 'comps=main'])
                self.assertNotEqual(ret, {})
                ret = self.run_function('pkg.get_repo', [repo])
                self.assertEqual(ret['uri'], uri)
            elif os_grain == 'CentOS':
                major_release = int(
                    self.run_function(
                        'grains.item',
                        ['osmajorrelease']
                    )['osmajorrelease']
                )
                repo = 'saltstack'
                name = 'SaltStack repo for RHEL/CentOS {0}'.format(major_release)
                baseurl = 'http://repo.saltstack.com/yum/redhat/{0}/x86_64/latest/'.format(major_release)
                gpgkey = 'https://repo.saltstack.com/yum/rhel{0}/SALTSTACK-GPG-KEY.pub'.format(major_release)
                gpgcheck = 1
                enabled = 1
                ret = self.run_function(
                    'pkg.mod_repo',
                    [repo],
                    name=name,
                    baseurl=baseurl,
                    gpgkey=gpgkey,
                    gpgcheck=gpgcheck,
                    enabled=enabled,
                )
                # return data from pkg.mod_repo contains the file modified at
                # the top level, so use next(iter(ret)) to get that key
                self.assertNotEqual(ret, {})
                repo_info = ret[next(iter(ret))]
                self.assertIn(repo, repo_info)
                self.assertEqual(repo_info[repo]['baseurl'], baseurl)
                ret = self.run_function('pkg.get_repo', [repo])
                self.assertEqual(ret['baseurl'], baseurl)
        finally:
            if repo is not None:
                self.run_function('pkg.del_repo', [repo])

    def test_owner(self):
        '''
        test finding the package owning a file
        '''
        func = 'pkg.owner'
        available = self.run_function('sys.doc', [func])

        if available:
            ret = self.run_function(func, ['/bin/ls'])
            self.assertNotEqual(len(ret), 0)
        else:
            os_grain = self.run_function('grains.item', ['os'])['os']
            self.skipTest('{0} is unavailable on {1}'.format(func, os_grain))

    @requires_network()
    @destructiveTest
    def test_install_remove(self):
        '''
        successfully install and uninstall a package
        '''
        pkg = 'htop'
        version = self.run_function('pkg.version', [pkg])
        os_grain = self.run_function('grains.item', ['os'])['os']
        os_release = self.run_function('grains.item', ['osrelease'])['osrelease']

        if os_grain == 'Ubuntu':
            if os_release.startswith('12.'):
                self.skipTest('pkg.install and pkg.remove do not work on ubuntu '
                              '12 when run from the test suite')

        def test_install():
            install_ret = self.run_function('pkg.install', [pkg])
            self.assertIn(pkg, install_ret)

        def test_remove():
            remove_ret = self.run_function('pkg.remove', [pkg])
            self.assertIn(pkg, remove_ret)

        if version:
            test_remove()
            test_install()
        else:
            test_install()
            test_remove()

    @requires_salt_modules('pkg.hold')
    @requires_network()
    @destructiveTest
    def test_hold_unhold(self):
        '''
        test holding and unholding a package
        '''
        pkg = 'htop'
        os_family = self.run_function('grains.item', ['os_family'])['os_family']
        os_major_release = self.run_function('grains.item', ['osmajorrelease'])['osmajorrelease']
        available = self.run_function('sys.doc', ['pkg.hold'])

        if os_family == 'RedHat':
            if os_major_release == '5':
                self.skipTest('`yum versionlock` does not seem to work on RHEL/CentOS 5')

        if available:
            if os_family == 'RedHat':
                lock_pkg = 'yum-versionlock' if os_major_release == '5' else 'yum-plugin-versionlock'
                versionlock = self.run_function('pkg.version', [lock_pkg])
                if not versionlock:
                    self.run_function('pkg.install', [lock_pkg])

            hold_ret = self.run_function('pkg.hold', [pkg])
            self.assertIn(pkg, hold_ret)
            self.assertTrue(hold_ret[pkg]['result'])

            unhold_ret = self.run_function('pkg.unhold', [pkg])
            self.assertIn(pkg, unhold_ret)
            self.assertTrue(hold_ret[pkg]['result'])

            if os_family == 'RedHat':
                if not versionlock:
                    self.run_function('pkg.remove', [lock_pkg])

        else:
            os_grain = self.run_function('grains.item', ['os'])['os']
            self.skipTest('{0} is unavailable on {1}'.format('pkg.hold', os_grain))

    @requires_network()
    @destructiveTest
    def test_refresh_db(self):
        '''
        test refreshing the package database
        '''
        func = 'pkg.refresh_db'
        os_family = self.run_function('grains.item', ['os_family'])['os_family']

        if os_family == 'RedHat':
            ret = self.run_function(func)
            self.assertIn(ret, (True, None))
        elif os_family == 'Suse':
            ret = self.run_function(func)
            if not isinstance(ret, dict):
                self.skipTest('Upstream repo did not return coherent results. Skipping test.')
            self.assertNotEqual(ret, {})
        elif os_family == 'Debian':
            ret = self.run_function(func)
            if not isinstance(ret, dict):
                self.skipTest('{0} encountered an error: {1}'.format(func, ret))
            self.assertNotEqual(ret, {})
            if not isinstance(ret, dict):
                self.skipTest('Upstream repo did not return coherent results. Skipping test.')
            for source, state in ret.items():
                self.assertIn(state, (True, False, None))
        else:
            os_grain = self.run_function('grains.item', ['os'])['os']
            self.skipTest('{0} is unavailable on {1}'.format(func, os_grain))

    @requires_salt_modules('pkg.info_installed')
    def test_pkg_info(self):
        '''
        Test returning useful information on Ubuntu systems.
        '''
        func = 'pkg.info_installed'
        os_family = self.run_function('grains.item', ['os_family'])['os_family']

        if os_family == 'Debian':
            ret = self.run_function(func, ['bash-completion', 'dpkg'])
            keys = ret.keys()
            self.assertIn('bash-completion', keys)
            self.assertIn('dpkg', keys)
        elif os_family == 'RedHat':
            ret = self.run_function(func, ['rpm', 'yum'])
            keys = ret.keys()
            self.assertIn('rpm', keys)
            self.assertIn('yum', keys)
        elif os_family == 'SUSE':
            ret = self.run_function(func, ['less', 'zypper'])
            keys = ret.keys()
            self.assertIn('less', keys)
            self.assertIn('zypper', keys)

    @requires_network()
    @destructiveTest
    def test_pkg_upgrade_has_pending_upgrades(self):
        '''
        Test running a system upgrade when there are packages that need upgrading
        '''
        func = 'pkg.upgrade'
        os_family = self.run_function('grains.item', ['os_family'])['os_family']

        # First make sure that an up-to-date copy of the package db is available
        self.run_function('pkg.refresh_db')

        if os_family == 'Suse':
            # pkg.latest version returns empty if the latest version is already installed
            vim_version_dict = self.run_function('pkg.latest_version', ['vim'])
            vim_info = self.run_function('pkg.info_available', ['vim'])['vim']
            if vim_version_dict == {}:
                # Latest version is installed, get its version and construct
                # a version selector so the immediately previous version is selected
                vim_version = 'version=<'+vim_info['version']
            else:
                # Vim was not installed, so pkg.latest_version returns the latest one.
                # Construct a version selector so immediately previous version is selected
                vim_version = 'version=<'+vim_version_dict

            # Only install a new version of vim if vim is up-to-date, otherwise we don't
            # need this check. (And the test will fail when we check for the empty dict
            # since vim gets upgraded in the install step.)
            if 'out-of-date' not in vim_info['status']:
                # Install a version of vim that should need upgrading
                ret = self.run_function('pkg.install', ['vim', vim_version])
                if not isinstance(ret, dict):
                    if ret.startswith('ERROR'):
                        self.skipTest('Could not install earlier vim to complete test.')
                else:
                    self.assertNotEqual(ret, {})

            # Run a system upgrade, which should catch the fact that Vim needs upgrading, and upgrade it.
            ret = self.run_function(func)

            # The changes dictionary should not be empty.
            if 'changes' in ret:
                self.assertIn('vim', ret['changes'])
            else:
                self.assertIn('vim', ret)
        else:
            ret = self.run_function('pkg.list_upgrades')
            if ret == '' or ret == {}:
                self.skipTest('No updates available for this machine.  Skipping pkg.upgrade test.')
            else:
                ret = self.run_function(func)

                if 'Problem encountered' in ret:
                    self.skipTest('A problem was encountered when running pkg.upgrade. This test is '
                                  'meant to catch no-ops or problems with the salt function itself, '
                                  'not problems with actual package installation. Skipping.')

                # The changes dictionary should not be empty.
                self.assertNotEqual(ret, {})
                if 'changes' in ret:
                    self.assertNotEqual(ret['changes'], {})
