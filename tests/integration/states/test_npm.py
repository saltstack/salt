# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson (erik@saltstack.com)`
    tests.integration.states.npm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, requires_network
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils


@skipIf(salt.utils.which('npm') is None, 'npm not installed')
class NpmStateTest(integration.ModuleCase, SaltReturnAssertsMixin):

    @requires_network()
    @destructiveTest
    def test_npm_installed_removed(self):
        '''
        Basic test to determine if NPM module was successfully installed and
        removed.
        '''
        ret = self.run_state('npm.installed', name='pm2')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('npm.removed', name='pm2')
        self.assertSaltTrueReturn(ret)

    @requires_network()
    @destructiveTest
    def test_npm_install_url_referenced_package(self):
        '''
        Determine if URL-referenced NPM module can be successfully installed.
        '''
        ret = self.run_state('npm.installed', name='git://github.com/request/request')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('npm.removed', name='git://github.com/request/request')
        self.assertSaltTrueReturn(ret)

    @requires_network()
    @destructiveTest
    def test_npm_installed_pkgs(self):
        '''
        Basic test to determine if NPM module successfully installs multiple
        packages.
        '''
        ret = self.run_state('npm.installed', name=None, pkgs=['pm2', 'grunt'])
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    def test_npm_cache_clean(self):
        '''
        Basic test to determine if NPM successfully cleans its cached packages.
        '''
        ret = self.run_state('npm.cache_cleaned', name=None)
        self.assertSaltTrueReturn(ret)
